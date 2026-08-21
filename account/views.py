# account/views.py
from __future__ import annotations

import json
import logging
from datetime import datetime
from urllib.parse import urlencode

import pyotp
import requests
from pywebpush import WebPusher
from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login as auth_login,
    logout as auth_logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse, HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView
from django.template.loader import render_to_string
from functools import wraps
from django.db import models
import random
from django.core.cache import cache
from django.core.mail import send_mail
from django_ratelimit.decorators import ratelimit
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired

# --------------------------------------------------------------
# Local imports
# --------------------------------------------------------------
from .forms import (
    PublicRegisterForm,
    ProfileForm,
    LoginForm,
    DeleteAccountForm,
    PasswordResetConfirmForm,
    PasswordResetRequestForm,
    ChangePasswordForm,
    AddPasswordForm,
)
from .models import UserConsent, User, StudentProfile, PushSubscription
from .constants import GROUP_TEACHER, GROUP_STUDENT, GROUP_ADMIN
from .utils import user_is_in_group, add_user_to_group

# Other apps used in the dashboard
from slm.models import Module, PersonalMaterial, Subject
from forum.models import Post
from aihelper.models import Conversation, Message

log = logging.getLogger(__name__)

# Decorators
def anonymous_required(view_func=None, *, redirect_to=None):
    """
    Decorator for views that should *only* be accessed by **anonymous** users.

    If the request is from an authenticated user we redirect them to
    ``redirect_to`` (defaults to the user‑specific dashboard).

    Works with both function‑based views and class‑based view ``as_view`` callables.
    """
    redirect_target = redirect_to or "account:dashboard"

    def decorator(func):
        @wraps(func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_authenticated:
                # The user is already logged in – send them to their dashboard.
                return redirect(reverse(redirect_target))
            return func(request, *args, **kwargs)

        return _wrapped_view

    # If the decorator is used without parentheses: @anonymous_required
    if callable(view_func):
        return decorator(view_func)

    # If used with parentheses: @anonymous_required()
    return decorator


# -----------------------------------------------------------------
#   EMAIL VERIFICATION HELPERS
# -----------------------------------------------------------------
signer = TimestampSigner()  # uses settings.SECRET_KEY automatically

def _send_email_verification(request, user):
    """
    Send a one‑time verification link to the user.
    The link contains a signed timestamp that expires after 48 h.
    """
    token = signer.sign(user.pk)   # “<user_id>:<signature>”
    verify_url = request.build_absolute_uri(
        reverse("account:verify_email", kwargs={"token": token})
    )
    subject = "Verify your EduAlly e‑mail address"
    body = render_to_string(
        "account/email_verification_email.txt",
        {
            "user": user,
            "verify_url": verify_url,
            "site_name": "EduAlly",
        },
    )
    send_mail(
        subject,
        body,
        django_settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def _set_2fa_email_otp(user, otp, request=None):
    """Persist the Gmail OTP in cache when available, otherwise fall back to the session."""
    key = f"two_factor_email_otp_{user.pk}"
    try:
        cache.set(key, otp, timeout=10 * 60)
        return
    except Exception as exc:
        log.warning("Falling back to session storage for 2FA Gmail OTP for user %s: %s", user.pk, exc)

    if request is not None:
        session_store = request.session.setdefault("two_factor_email_otp_map", {})
        session_store[str(user.pk)] = otp
        request.session.modified = True


def _get_2fa_email_otp(user, request=None):
    """Get the Gmail OTP from cache, falling back to the session if the cache backend is offline."""
    key = f"two_factor_email_otp_{user.pk}"
    try:
        cached = cache.get(key)
        if cached is not None:
            return cached
    except Exception as exc:
        log.warning("Cache read failed while fetching 2FA Gmail OTP for user %s: %s", user.pk, exc)

    if request is not None:
        session_store = request.session.get("two_factor_email_otp_map", {})
        return session_store.get(str(user.pk))
    return None


def _delete_2fa_email_otp(user, request=None):
    """Delete the stored Gmail OTP from cache and session fallback when present."""
    key = f"two_factor_email_otp_{user.pk}"
    try:
        cache.delete(key)
    except Exception as exc:
        log.warning("Cache delete failed while clearing 2FA Gmail OTP for user %s: %s", user.pk, exc)

    if request is not None:
        session_store = request.session.get("two_factor_email_otp_map", {})
        session_store.pop(str(user.pk), None)
        request.session.modified = True

# -----------------------------------------------------------------
#   ROLE‑BASED LOGIN VIEW
# -----------------------------------------------------------------
class RoleBasedLoginView(TemplateView):
    template_name = "account/login.html"
    form_class = LoginForm
    redirect_authenticated_user = True

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated and self.redirect_authenticated_user:
            return redirect(self.get_success_url())
        return render(request, self.template_name, {"form": self.form_class()})

    def post(self, request, *args, **kwargs):
        form = self.form_class(request, data=request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        user = form.get_user()

        if (user.is_staff or user.is_superuser) and not user.email_verified:
            # Mark them as verified *once* so the same check never trips again.
            # (Optional – you can also just skip the whole block.)
            user.email_verified = True
            user.save(update_fields=["email_verified"])
        # -------------------------------------------------
        # NEW – block login for un‑verified accounts
        # -------------------------------------------------
        if not user.email_verified and user.two_factor_enabled:
            # 1️⃣  Store where they wanted to go after they become verified.
            request.session["post_verification_redirect"] = self.get_success_url_for_user(user)

            # 2️⃣  Show the warning toast (your UI already does this)
            messages.warning(
                request,
                "You need to verify your e‑mail address before you can log in. "
                "A verification link has been sent – please check your inbox.",
            )
            # 3️⃣  (IMPORTANT) Log the user **temporarily** so that the
            #     `login_required` decorator on the next view succeeds.
            auth_login(request, user)

            # 4️⃣  (Optional) Re‑send the e‑mail only if they missed it.
            _send_email_verification(request, user)

            # 5️⃣  Redirect to the page that tells them “check your inbox”.
            return redirect("account:email_verification_required")

        # -------------------------------------------------
        # 2FA and normal login paths (unchanged)
        # -------------------------------------------------
        if getattr(user, "two_factor_enabled", False):
            request.session["pending_2fa_user_id"] = user.pk
            request.session["pending_2fa_next"] = self.get_success_url_for_user(user)
            return redirect("account:verify_2fa")

        auth_login(request, user)
        return redirect(self.get_success_url_for_user(user))
    
    def get_success_url_for_user(self, user):
        if user.is_superuser or user.is_staff:
            return reverse("admin:index")
        if user_is_in_group(user, GROUP_TEACHER):
            return reverse("account:dashboard")
        return reverse("account:dashboard")

    def get_success_url(self):
        return self.get_success_url_for_user(self.request.user)


# -----------------------------------------------------------------
#   LANDING / DASHBOARD / PROFILE etc.
# -----------------------------------------------------------------
@anonymous_required
def landing(request):
    return render(request, "account/landing.html")


@anonymous_required
def contact_page(request):
    return render(request, "account/contact.html")


def _get_recent_module_ids(request):
    recent_module_ids = request.session.get("recent_modules", [])
    if recent_module_ids:
        return recent_module_ids

    cookie_value = request.COOKIES.get("eduallyRecentModules")
    if not cookie_value:
        return []

    try:
        parsed = json.loads(cookie_value)
    except json.JSONDecodeError:
        # Some cookie transports escape commas as octal sequences like "\054".
        cookie_value = cookie_value.replace("\\054", ",")
        try:
            parsed = json.loads(cookie_value)
        except json.JSONDecodeError:
            return []

    if not isinstance(parsed, list):
        return []

    recent_module_ids = []
    for item in parsed:
        try:
            recent_module_ids.append(int(item))
        except (TypeError, ValueError):
            continue

    if recent_module_ids:
        request.session["recent_modules"] = recent_module_ids

    return recent_module_ids


def _get_recent_personal_material_ids(request):
    """
    Mirrors ``_get_recent_module_ids`` but works for PersonalMaterial objects.
    The IDs are stored under the session key ``recent_personal_materials``
    and a cookie named ``eduallyRecentPersonalMaterials``.
    """
    recent_material_ids = request.session.get("recent_personal_materials", [])
    if recent_material_ids:
        return recent_material_ids

    cookie_value = request.COOKIES.get("eduallyRecentPersonalMaterials")
    if not cookie_value:
        return []

    try:
        parsed = json.loads(cookie_value)
    except json.JSONDecodeError:
        # Handle escaped commas (legacy format)
        cookie_value = cookie_value.replace("\\054", ",")
        try:
            parsed = json.loads(cookie_value)
        except json.JSONDecodeError:
            return []

    if not isinstance(parsed, list):
        return []

    recent_material_ids = []
    for item in parsed:
        try:
            recent_material_ids.append(int(item))
        except (TypeError, ValueError):
            continue

    if recent_material_ids:
        request.session["recent_personal_materials"] = recent_material_ids

    return recent_material_ids

@login_required(login_url='account:login')
def dashboard(request):
    if user_is_in_group(request.user, GROUP_TEACHER):
        subjects = request.user.subjects.filter(is_archived=False)[:3]
        modules = Module.objects.filter(subject__author=request.user, is_archived=False).select_related("subject")[:3]
        subject_count = request.user.subjects.filter(is_archived=False).count()
        module_count = Module.objects.filter(subject__author=request.user, is_archived=False).count()
    else:
        subjects = Subject.objects.filter(is_archived=False)[:3]
        modules = Module.objects.filter(is_archived=False, subject__is_archived=False).select_related("subject")[:3]
        subject_count = Subject.objects.filter(is_archived=False).count()
        module_count = Module.objects.filter(is_archived=False, subject__is_archived=False).count()

    recent_module_ids = _get_recent_module_ids(request)
    recent_modules = list(
        Module.objects.filter(pk__in=recent_module_ids)
        .select_related("subject")
        .order_by(
            models.Case(
                *[models.When(pk=pk, then=pos) for pos, pk in enumerate(recent_module_ids)],
                output_field=models.IntegerField(),
            )
        )
    ) if recent_module_ids else []

    # -----------------------------------------------------------------
    #  Personal materials – recent visits (new)
    # -----------------------------------------------------------------
    recent_material_ids = _get_recent_personal_material_ids(request)
    recent_personal_materials = list(
        PersonalMaterial.objects.filter(pk__in=recent_material_ids)
        .select_related("author")
        .order_by(
            models.Case(
                *[models.When(pk=pk, then=pos) for pos, pk in enumerate(recent_material_ids)],
                output_field=models.IntegerField(),
            )
        )
    ) if recent_material_ids else []

    recent_activity = [
        {
            "title": "Continue where you left off",
            "detail": "Open your latest module and pick up your progress in a few seconds.",
            "icon": "fas fa-play-circle",
        },
        {
            "title": "Ask the AI Helper",
            "detail": "Get guidance on confusing topics before they become blockers.",
            "icon": "fas fa-robot",
        },
        {
            "title": "Join the forum",
            "detail": "See what classmates are asking and share a useful insight.",
            "icon": "fas fa-comment",
        },
    ]

    onboarding_steps = [
        {
            "title": "Complete your profile",
            "detail": "Add your course details and a profile photo so your learning space feels personal.",
            "done": bool(request.user.first_name or request.user.last_name or request.user.program),
        },
        {
            "title": "Open a module",
            "detail": "Review the latest materials and start building momentum with one small step.",
            "done": bool(recent_modules),
        },
        {
            "title": "Ask one question",
            "detail": "Share what you are stuck on and let the community or AI helper support you.",
            "done": (
                Conversation.objects.filter(user=request.user).exists()
                or Message.objects.filter(user=request.user, role="user").exists()
            ),
        },
    ]

    context = {
        "subjects": subjects,
        "modules": modules,
        "recent_modules": recent_modules,
        "recent_personal_materials": recent_personal_materials,
        "recent_activity": recent_activity,
        "module_count": module_count,
        "subject_count": subject_count,
        "onboarding_steps": onboarding_steps,
    }
    return render(request, "dashboard.html", context)


@login_required(login_url='account:login')
def profile(request):
    """
    GET  → show the read-only profile overview with edit buttons.
    POST → handle profile update from the inline form.
    """
    # -----------------------------------------------------------------
    # 1️⃣  Profile edit handling (POST from the profile form)
    # -----------------------------------------------------------------
    if request.method == "POST" and "profile_update" in request.POST:
        profile_form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, "Your profile was updated.")
            return redirect("account:profile")
        messages.error(request, "Please correct the errors below.")
    else:
        profile_form = ProfileForm(instance=request.user)

    context = {
        "user_obj": request.user,
        "profile_form": profile_form,
    }
    return render(request, "account/profile.html", context)


@login_required(login_url='account:login')
def profile_edit(request):
    """
    GET  → show both the edit personal information and change password forms.
    POST → handle whichever form was submitted.
    """
    # -----------------------------------------------------------------
    # 1️⃣  Profile edit handling (POST from the profile form)
    # -----------------------------------------------------------------
    if request.method == "POST" and "profile_update" in request.POST:
        profile_form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, "Your profile was updated.")
            return redirect("account:profile")
        messages.error(request, "Please correct the errors below.")
        password_form = ChangePasswordForm(user=request.user)
    # -----------------------------------------------------------------
    # 2️⃣  Password‑change handling (POST from the password form)
    # -----------------------------------------------------------------
    elif request.method == "POST" and "change_password" in request.POST:
        password_form = ChangePasswordForm(user=request.user, data=request.POST)
        if password_form.is_valid():
            password_form.save()
            # Keep the user logged‑in after the password change
            update_session_auth_hash(request, request.user)
            messages.success(request, "Your password was updated.")
            return redirect("account:profile")
        # If we fall through we will re‑render the page with errors
        profile_form = ProfileForm(instance=request.user)
    else:
        profile_form = ProfileForm(instance=request.user)
        password_form = ChangePasswordForm(user=request.user)

    context = {
        "profile_form": profile_form,
        "password_form": password_form,
        "user_obj": request.user,
    }
    return render(request, "account/edit_profile.html", context)


@login_required(login_url='account:login')
def profile_modal(request, pk):
    """Return a compact profile card as HTML for AJAX modal loads."""
    user_obj = get_object_or_404(User, pk=pk)

    # Light‑weight counts for forum posts (if they exist)
    if not hasattr(user_obj, "forum_posts_count"):
        try:
            user_obj.forum_posts_count = user_obj.forum_posts.count()
        except Exception:
            user_obj.forum_posts_count = 0

    html = render_to_string('account/partials/profile_modal.html', {'user_obj': user_obj}, request=request)
    return JsonResponse({'html': html})


# -----------------------------------------------------------------
#   PUBLIC REGISTRATION
# -----------------------------------------------------------------
@anonymous_required
def register(request):
    """
    Public registration – uses ``PublicRegisterForm`` which now creates
    an *unverified* user and immediately sends a verification e‑mail.
    """
    policy_context = {
        "policy_version": django_settings.POLICY_VERSION,
        "effective_date": datetime.strptime(
            django_settings.POLICY_EFFECTIVE_DATE, "%Y-%m-%d"
        ),
    }

    if request.method == "POST":
        form = PublicRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()                     # email_verified == False
            _send_email_verification(request, user)

            messages.success(
                request,
                "Your account has been created – check your e‑mail for a verification link.",
            )
            # Auto‑login **is not** performed; we force the user to verify first.
            return redirect("account:email_verification_required")
        messages.error(request, "Please fix the errors below.")
    else:
        form = PublicRegisterForm()

    return render(request, "account/register.html", {"form": form, **policy_context})


# -----------------------------------------------------------------
#   EMAIL VERIFICATION REQUIRED PAGE
# -----------------------------------------------------------------
class EmailVerificationRequiredView(TemplateView):
    """
    Shown when a logged‑in user has ``email_verified=False``.
    Gives a friendly message and a *Resend verification e‑mail* button.
    """
    template_name = "account/email_verification_required.html"

    @method_decorator(login_required(login_url='account:login'))
    def dispatch(self, *args, **kwargs):
        # If the user is already verified – send them on their way.
        if self.request.user.email_verified or not self.request.user.two_factor_enabled:
            return redirect("account:dashboard")
        return super().dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        """
        Handles the *Resend* button.  After sending the e‑mail we log the user
        out because the verification link will automatically log them back in.
        """
        _send_email_verification(request, request.user)
        messages.info(request, "A fresh verification e‑mail has been sent.")
        auth_logout(request)               # log out – the link will log them back in
        return redirect("account:login")


# -----------------------------------------------------------------
#   VERIFY EMAIL LINK HANDLER
# -----------------------------------------------------------------
def verify_email(request, token: str):
    """
    Endpoint that the user clicks from the e‑mail.
    It validates the signed token (max age 48 h) and marks the account as
    verified.  The user is then logged in automatically and redirected.
    """
    try:
        # ``max_age`` is in seconds – 48 h = 172 800 seconds.
        user_pk = signer.unsign(token, max_age=48 * 60 * 60)
    except SignatureExpired:
        messages.error(request, "The verification link has expired – request a new one.")
        return redirect("account:login")
    except BadSignature:
        messages.error(request, "Invalid verification link.")
        return redirect("account:login")

    # ``user_pk`` comes back as a string; cast to int.
    try:
        user = User.objects.get(pk=int(user_pk))
    except (User.DoesNotExist, ValueError):
        messages.error(request, "User not found.")
        return redirect("account:login")

    # Successful verification – flip the flag and log the user in.
    user.email_verified = True
    user.save(update_fields=["email_verified"])
    user.backend = "django.contrib.auth.backends.ModelBackend"
    auth_login(request, user)

    messages.success(request, "Your e‑mail has been verified – welcome!")
    # redirect to the page they originally wanted (if stored) or dashboard
    next_url = request.session.pop("post_verification_redirect", reverse("account:dashboard"))
    return redirect(next_url)


@login_required(login_url='account:login')
@ensure_csrf_cookie
def settings(request):
    """
    Settings page – three vertically‑stacked sections:

    1️⃣  Account Preferences (unchanged UI)
    2️⃣  Archive – shows the user’s archived forum posts,
        modules **and** personal learning material.
    3️⃣  Danger Zone – permanent‑delete button.
    """
    if request.method == "POST" and "send_2fa_email_otp" in request.POST:
        otp_code = (request.POST.get("otp_code") or request.POST.get("authenticator_code") or "").strip()
        secret = request.user.two_factor_secret or request.session.get("pending_2fa_secret")
        if not otp_code:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"valid": False, "message": "Enter the 6-digit code from your authenticator app before sending the Gmail verification code."}, status=400)
            messages.error(request, "Enter the 6-digit code from your authenticator app before sending the Gmail verification code.")
            return redirect("account:settings")

        if not secret or not pyotp.TOTP(secret).verify(otp_code, valid_window=1):
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"valid": False, "message": "That authenticator code is invalid or expired. Please try again."}, status=400)
            messages.error(request, "That authenticator code is invalid or expired. Please try again.")
            return redirect("account:settings")

        _send_2fa_email_otp(request.user, request=request)
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"valid": True, "message": "A verification code was sent to your Gmail address."})
        if not any(message.level >= messages.constants.WARNING for message in messages.get_messages(request)):
            messages.info(request, "A verification code was sent to your Gmail address.")
        return redirect("account:settings")

    if request.method == "POST" and "enable_2fa" in request.POST:
        otp_code = (request.POST.get("otp_code") or request.POST.get("authenticator_code") or "").strip()
        gmail_otp = (request.POST.get("gmail_otp") or "").strip()

        cached_email_otp = _get_2fa_email_otp(request.user, request=request)
        if not gmail_otp or not cached_email_otp or cached_email_otp != gmail_otp:
            messages.error(request, "Enter the 6-digit code sent to your Gmail account before enabling 2FA.")
            return redirect("account:settings")

        if not otp_code:
            messages.error(request, "Enter the 6-digit code from your authenticator app.")
            return redirect("account:settings")

        saved_secret = request.user.two_factor_secret or ""
        pending_secret = request.session.get("pending_2fa_secret") or ""
        secret = saved_secret or pending_secret or pyotp.random_base32()
        verified = False

        if saved_secret and pyotp.TOTP(saved_secret).verify(otp_code, valid_window=1):
            verified = True
            secret = saved_secret
        elif pending_secret and pyotp.TOTP(pending_secret).verify(otp_code, valid_window=1):
            verified = True
            secret = pending_secret

        if verified:
            request.user.two_factor_secret = secret
            request.user.two_factor_enabled = True
            request.user.save(update_fields=["two_factor_secret", "two_factor_enabled"])
            request.session.pop("pending_2fa_secret", None)
            _delete_2fa_email_otp(request.user, request=request)
            messages.success(request, "Two-factor authentication enabled.")
        else:
            messages.error(request, "That code is invalid or expired. Please try again.")
        return redirect("account:settings")

    if request.method == "POST" and "disable_2fa" in request.POST:
        request.user.two_factor_enabled = False
        request.user.two_factor_secret = ""
        request.user.save(update_fields=["two_factor_enabled", "two_factor_secret"])
        request.session.pop("pending_2fa_secret", None)
        messages.success(request, "Two-factor authentication has been disabled.")
        return redirect("account:settings")

    if request.method == "POST" and "request_new_qr" in request.POST:
        new_secret = pyotp.random_base32()
        request.session["pending_2fa_secret"] = new_secret
        messages.info(request, "A new QR code was generated. Please scan it and enter the new 6-digit code.")
        return redirect("account:settings")

    # Keep one stable pending secret while the user is setting up 2FA so the authenticator app
    # and QR code remain in sync across refreshes until the user successfully enables 2FA.
    if not request.user.two_factor_enabled:
        current_secret = request.session.get("pending_2fa_secret")
        if not current_secret:
            current_secret = pyotp.random_base32()
            request.session["pending_2fa_secret"] = current_secret

    # ---- ARCHIVED FORUM POSTS -------------------------------------------------
    archived_posts = (
        Post.objects.filter(author=request.user, is_archived=True)
        .order_by('-created_at')[:10]          # limit for quick loading
    )

    # ---- ARCHIVED MODULES ----------------------------------------------------
    archived_modules = (
        Module.objects.filter(
            subject__author=request.user,      # modules the user authored
            is_archived=True,
        )
        .order_by('-created_at')[:10]
    )

    # ---- ARCHIVED PERSONAL LEARNING MATERIAL ---------------------------------
    archived_materials = (
        PersonalMaterial.objects.filter(
            author=request.user,
            is_archived=True,
        )
        .order_by('-created_at')[:10]
    )

    otp_secret = request.user.two_factor_secret or request.session.get("pending_2fa_secret") or pyotp.random_base32()
    request.session["pending_2fa_secret"] = otp_secret
    otp_uri = pyotp.TOTP(otp_secret).provisioning_uri(
        name=request.user.email,
        issuer_name="EduAlly",
    )

    context = _settings_context(
        request,
        posts=archived_posts,
        modules=archived_modules,
        personal_materials=archived_materials,
    )
    context["otp_secret"] = otp_secret
    context["otp_uri"] = otp_uri
    context["two_factor_enabled"] = request.user.two_factor_enabled
    return render(request, "account/settings.html", context)


def _settings_context(request, delete_form=None, posts=None, modules=None, personal_materials=None):
    return {
        "posts": posts,
        "modules": modules,
        "personal_materials": personal_materials,
        "delete_form": delete_form or DeleteAccountForm(user=request.user),
    }


@anonymous_required
def verify_2fa(request):
    pending_user_id = request.session.get("pending_2fa_user_id")
    if not pending_user_id:
        return redirect("account:login")

    user = get_object_or_404(User, pk=pending_user_id)
    if request.method == "POST":
        otp_code = (request.POST.get("otp_code") or "").strip()
        if pyotp.TOTP(user.two_factor_secret).verify(otp_code, valid_window=1):
            request.session.pop("pending_2fa_user_id", None)
            next_url = request.session.pop("pending_2fa_next", None) or reverse("account:dashboard")
            auth_login(request, user)
            return redirect(next_url)
        messages.error(request, "Invalid or expired verification code.")

    return render(request, "account/verify_2fa.html", {"user": user})


# -----------------------------------------------------------------
#   DANGER ZONE – account deletion (updated to require password confirm)
# -----------------------------------------------------------------
@login_required
def delete_account_modal(request):
    form = DeleteAccountForm(user=request.user)
    html = render_to_string(
        "account/partials/account_delete_modal.html",
        {
            "form": form,
            "request": request,
        },
        request=request,
    )
    return JsonResponse({"html": html})


@login_required
@require_POST
def delete_account(request):
    """Hard-delete the user after confirming the current password."""
    form = DeleteAccountForm(request.POST, user=request.user)
    if not form.is_valid():
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            html = render_to_string(
                "account/partials/account_delete_modal.html",
                {
                    "form": form,
                    "request": request,
                },
                request=request,
            )
            return JsonResponse({"html": html})
        return render(request, "account/settings.html", _settings_context(request, delete_form=form))

    user = request.user
    auth_logout(request)          # log out before we delete the row
    user.delete()
    message = "Your account has been permanently deleted."
    messages.success(request, message)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "success": True,
            "redirect": reverse("account:landing"),
            "message": message,
            "toastType": "success",
            "toastDuration": 5000,
        })
    return redirect("landing")


@never_cache
@login_required(login_url='account:login')
@ensure_csrf_cookie     # ← makes sure the GET includes a CSRF cookie
def logout_confirm(request):
    """GET → modal HTML, POST → log the user out."""
    if request.method == 'POST':
        auth_logout(request)
        # AJAX response (the JS will redirect)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True,
                                 'redirect': reverse('account:landing')})
        # Non‑AJAX fallback (keep old behaviour)
        return redirect('account:landing')

    # GET → return modal markup
    html = render_to_string(
        'account/logout_confirm.html',
        {'request': request},
        request=request,
    )
    return JsonResponse({'html': html})


@require_POST
@login_required(login_url='account:login')
def api_push_subscribe(request):
    """Persist a browser push subscription for the authenticated user."""
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    endpoint = payload.get("endpoint")
    auth = payload.get("keys", {}).get("auth")
    p256dh = payload.get("keys", {}).get("p256dh")

    if not endpoint or not auth or not p256dh:
        return JsonResponse({"error": "Incomplete push subscription payload"}, status=400)

    subscription, _ = PushSubscription.objects.update_or_create(
        user=request.user,
        endpoint=endpoint,
        defaults={"auth": auth, "p256dh": p256dh},
    )
    return JsonResponse({"success": True, "id": subscription.pk})


@require_POST
@login_required(login_url='account:login')
def api_push_unsubscribe(request):
    """Delete a stored browser push subscription for the authenticated user."""
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    endpoint = payload.get("endpoint")
    if not endpoint:
        return JsonResponse({"error": "Endpoint is required"}, status=400)

    PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    return JsonResponse({"success": True})


@require_POST
def api_set_theme(request):
    """
    Called by the front‑end to persist a light/dark theme choice in a cookie.
    """
    theme = request.POST.get('theme')
    if theme is None:
        try:
            payload = json.loads(request.body or b'{}')
            theme = payload.get('theme')
        except Exception:
            theme = None

    if theme not in ('dark', 'light'):
        return JsonResponse({'error': 'Invalid theme'}, status=400)

    response = JsonResponse({'theme': theme})
    max_age = 365 * 24 * 60 * 60
    response.set_cookie('eduallyTheme', theme, max_age=max_age, httponly=False, samesite='Lax')
    return response


# -----------------------------------------------------------------
#   POLICY VIEWS (terms / privacy) – tiny wrappers that render the same
#   content as the modal but give a proper URL for SEO / accessibility.
# -----------------------------------------------------------------
class PolicyBaseView(TemplateView):
    """Inject policy version & effective date into all policy templates."""
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["policy_version"] = django_settings.POLICY_VERSION
        context["effective_date"] = datetime.strptime(
            django_settings.POLICY_EFFECTIVE_DATE, "%Y-%m-%d"
        )
        return context


class TermsView(PolicyBaseView):
    template_name = "account/terms.html"


class PrivacyView(PolicyBaseView):
    template_name = "account/privacy.html"


# -----------------------------------------------------------------
#   CONSENT REQUIRED VIEW
# -----------------------------------------------------------------
class ConsentRequiredView(TemplateView):
    template_name = "account/consent_required.html"

    @method_decorator(login_required(login_url='account:login'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        # Record the user’s acceptance of the latest policy
        UserConsent.objects.update_or_create(
            user=request.user,
            defaults={"version": django_settings.POLICY_VERSION, "accepted_at": timezone.now()},
        )
        # Send them back to where they originally wanted to go
        next_url = request.session.pop("post_consent_redirect", reverse("account:dashboard"))
        return redirect(next_url)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            policy_version=django_settings.POLICY_VERSION,
            effective_date=datetime.strptime(
                django_settings.POLICY_EFFECTIVE_DATE, "%Y-%m-%d"
            ),
        )
        return ctx


# -----------------------------------------------------------------
#   GOOGLE OAUTH – unchanged except for group assignment (see code
#   block a few lines down where the user is created).
# -----------------------------------------------------------------
def _build_google_auth_url(state: str | None = None) -> str:
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": django_settings.GOOGLE_CLIENT_ID,
        "redirect_uri": django_settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    if state:
        params["state"] = state
    return f"{base_url}?{urlencode(params)}"


def _exchange_code_for_tokens(code: str) -> dict:
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": django_settings.GOOGLE_CLIENT_ID,
        "client_secret": django_settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": django_settings.GOOGLE_OAUTH_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    resp = requests.post(token_url, data=data, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _fetch_google_userinfo(access_token: str) -> dict:
    userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(userinfo_url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def google_login(request):
    """
    Kick‑off the Google OAuth flow.  Preserve a ``next`` GET param so we can
    send the user back after they approve.
    """
    next_url = request.GET.get("next")
    auth_url = _build_google_auth_url(state=next_url)
    return redirect(auth_url)


def google_callback(request):
    """
    Handles the redirect back from Google, creates (or fetches) a User,
    assigns the Student group, records consent and logs the user in.
    """
    error = request.GET.get("error")
    if error:
        messages.error(request, "Google sign‑in failed – please try again.")
        return redirect(reverse("account:login"))

    code = request.GET.get("code")
    if not code:
        return HttpResponseBadRequest("Missing code parameter.")

    try:
        token_data = _exchange_code_for_tokens(code)
        access_token = token_data["access_token"]
        userinfo = _fetch_google_userinfo(access_token)
    except Exception:   # pragma: no cover – defensive
        messages.error(request, "Unable to verify Google credentials.")
        return redirect(reverse("account:login"))

    email = userinfo.get("email")
    full_name = userinfo.get("name", "")

    if not email:
        messages.error(request, "Google account did not return an email address.")
        return redirect(reverse("account:login"))

    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            "first_name": full_name.split(" ")[0] if full_name else "",
            "last_name": " ".join(full_name.split(" ")[1:]) if full_name else "",
            "is_active": True,
        },
    )
    if created:
        user.set_unusable_password()
        # Google‑OAuth accounts are automatically verified because Google already validated the address.
        user.email_verified = True
        user.save()

        # -------------------------------------------------------------
        # New user → treat as a Student, create empty profile & consent.
        # -------------------------------------------------------------
        add_user_to_group(user, GROUP_STUDENT)
        StudentProfile.objects.get_or_create(user=user)  # empty profile
        UserConsent.objects.create(
            user=user,
            version=django_settings.POLICY_VERSION,
            accepted_at=timezone.now(),
        )
        messages.success(request, "Your EduAlly account was created via Google.")
    else:
        # Existing user – make sure they have a consent record.
        if not hasattr(user, "consent"):
            UserConsent.objects.create(
                user=user,
                version=django_settings.POLICY_VERSION,
                accepted_at=timezone.now(),
            )

    # -------------------------------------------------------------
    # Log the user in – we use ``ModelBackend`` because the password‑less
    # Google flow bypasses the EmailOrUsername backend.
    # -------------------------------------------------------------
    user.backend = "django.contrib.auth.backends.ModelBackend"
    auth_login(request, user)

    if user_is_in_group(user, GROUP_STUDENT):
        # Grab (or lazily create) the profile so we can inspect fields.
        profile, _ = StudentProfile.objects.get_or_create(user=user)

        missing = (
            not profile.student_id or not profile.year_level
        )
        if missing:
            messages.info(
                request,
                "Please complete your profile by adding a Student ID and selecting your Year Level."
            )
            # Send them straight to the edit‑profile page – they cannot skip it.
            return redirect("account:profile_edit")

    next_url = request.GET.get("state") or request.session.get(
        "post_consent_redirect", reverse("account:dashboard")
    )
    return redirect(next_url)


@login_required
def archives_home(request):
    """
    Tiny landing page for the archive section.
    It simply redirects to the first sub‑page (forum posts) – you can
    change it to render a custom index if you prefer.
    """
    return redirect('account:archive-forum-posts')


# -----------------------------------------------------------------
#   Forum posts
# -----------------------------------------------------------------
@login_required
def archive_forum_post_list(request):
    posts = (
        Post.objects.filter(author=request.user, is_archived=True)
        .order_by('-created_at')
    )
    return render(request, 'account/partials/archive_forum_posts.html',
                  {'posts': posts})


@login_required
def archive_forum_post_detail(request, pk):
    post = get_object_or_404(
        Post,
        pk=pk,
        author=request.user,
        is_archived=True,
    )

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'unarchive':
            post.is_archived = False
            post.save(update_fields=['is_archived'])
            messages.success(request, 'Post has been restored.')
            return redirect('account:archive-forum-posts')

    return render(request, 'account/partials/archive_forum_post_detail.html',
                  {'post': post})


# -----------------------------------------------------------------
#   Modules (subject owner only)
# -----------------------------------------------------------------
@login_required
def archive_module_list(request):
    modules = (
        Module.objects.filter(
            subject__author=request.user,
            is_archived=True,
        )
        .select_related('subject')
        .order_by('-created_at')
    )
    return render(request, 'account/partials/archive_modules.html',
                  {'modules': modules})


@login_required
def archive_module_detail(request, pk):
    module = get_object_or_404(
        Module,
        pk=pk,
        subject__author=request.user,
        is_archived=True,
    )

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'unarchive':
            module.is_archived = False
            module.save(update_fields=['is_archived'])
            messages.success(request, 'Module has been restored.')
            return redirect('account:archive-modules')

    return render(request, 'account/partials/archive_module_detail.html',
                  {'module': module})


# -----------------------------------------------------------------
#   Personal Materials (owner only)
# -----------------------------------------------------------------
@login_required
def archive_personal_material_list(request):
    materials = (
        PersonalMaterial.objects.filter(
            author=request.user,
            is_archived=True,
        )
        .order_by('-created_at')
    )
    return render(request,
                  'account/partials/archive_personal_materials.html',
                  {'materials': materials})


@login_required
def archive_personal_material_detail(request, pk):
    pm = get_object_or_404(
        PersonalMaterial,
        pk=pk,
        author=request.user,
        is_archived=True,
    )

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'unarchive':
            pm.is_archived = False
            pm.save(update_fields=['is_archived'])
            messages.success(request, 'Material has been restored.')
            return redirect('account:archive-personal-materials')

    return render(request,
                  'account/partials/archive_personal_material_detail.html',
                  {'pm': pm})
    
@login_required
def archive_forum_post_delete_modal(request, pk):
    """
    Return the modal HTML that asks the user to confirm permanent deletion
    of an **archived** forum post.
    """
    post = get_object_or_404(
        Post,
        pk=pk,
        author=request.user,
        is_archived=True,
    )
    html = render_to_string(
        'account/partials/archive_forum_post_delete_modal.html',
        {'post': post},
        request=request,
    )
    return JsonResponse({'html': html})


@require_POST
@login_required
def archive_forum_post_delete(request, pk):
    """AJAX endpoint – actually delete the archived post."""
    post = get_object_or_404(
        Post,
        pk=pk,
        author=request.user,
        is_archived=True,
    )
    post.delete()
    messages.success(request, "Post permanently deleted.")
    return JsonResponse(
        {
            "success": True,
            "redirect": reverse("account:archive-forum-posts"),
        }
    )


# -----------------------------------------------------------------
#  DELETE MODAL – Module
# -----------------------------------------------------------------
@login_required
def archive_module_delete_modal(request, pk):
    """Return the modal that confirms permanent deletion of an archived module."""
    module = get_object_or_404(
        Module,
        pk=pk,
        subject__author=request.user,
        is_archived=True,
    )
    html = render_to_string(
        'account/partials/archive_module_delete_modal.html',
        {'module': module},
        request=request,
    )
    return JsonResponse({'html': html})


@require_POST
@login_required
def archive_module_delete(request, pk):
    """AJAX endpoint – delete the archived module (file removed as well)."""
    module = get_object_or_404(
        Module,
        pk=pk,
        subject__author=request.user,
        is_archived=True,
    )
    # Delete the file from storage first (mirrors the non‑AJAX view logic)
    if module.file:
        module.file.delete(save=False)
    module.delete()
    messages.success(request, "Module permanently deleted.")
    return JsonResponse(
        {
            "success": True,
            "redirect": reverse("account:archive-modules"),
        }
    )


# -----------------------------------------------------------------
#  DELETE MODAL – Personal material
# -----------------------------------------------------------------
@login_required
def archive_personal_material_delete_modal(request, pk):
    """Return the modal that confirms permanent deletion of an archived material."""
    pm = get_object_or_404(
        PersonalMaterial,
        pk=pk,
        author=request.user,
        is_archived=True,
    )
    html = render_to_string(
        'account/partials/archive_personal_material_delete_modal.html',
        {'pm': pm},
        request=request,
    )
    return JsonResponse({'html': html})


@require_POST
@login_required
def archive_personal_material_delete(request, pk):
    """AJAX endpoint – delete the archived personal material."""
    pm = get_object_or_404(
        PersonalMaterial,
        pk=pk,
        author=request.user,
        is_archived=True,
    )
    if pm.file:
        pm.file.delete(save=False)
    pm.delete()
    messages.success(request, "Material permanently deleted.")
    return JsonResponse(
        {
            "success": True,
            "redirect": reverse("account:archive-personal-materials"),
        }
    )
    

def teacher_required_for_mutation(view_func):
    """
    *GET* requests are allowed for any authenticated user.
    All other HTTP verbs (POST, PUT, PATCH, DELETE) are allowed **only**
    for users that belong to the *Teacher* group.
    """
    @wraps(view_func)
    @login_required                     # always require a logged‑in user
    def _wrapped(request, *args, **kwargs):
        # --------‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑
        # 1️⃣  GET → public read‑only
        # -----------------------------------------------------------------
        if request.method == "GET":
            return view_func(request, *args, **kwargs)

        # -----------------------------------------------------------------
        # 2️⃣  Anything else → must be a teacher
        # -----------------------------------------------------------------
        if getattr(request.user, "is_teacher_member", False):
            return view_func(request, *args, **kwargs)

        return HttpResponseForbidden(
            "Only teachers may create / edit / delete resources."
        )
    return _wrapped


def _send_otp_helper(email: str, user: User) -> None:
    """
    **Plain helper** – generate a 6‑digit OTP, store it in the cache
    and e‑mail it to the user.  This function must NOT be decorated with
    ``@require_POST`` (or any view decorator) because it is invoked
    directly from the view ``password_reset_request``.
    """
    otp = f"{random.randint(0, 999999):06d}"
    # Cache key is scoped to the e‑mail address; expires after 10 minutes.
    cache.set(f"pwd_reset_otp_{email}", otp, timeout=10 * 60)

    subject = "Your EduAlly password‑reset code"
    body = render_to_string(
        "account/password_reset_email.txt",
        {"user": user, "otp": otp, "site_name": "EduAlly"},
    )
    send_mail(
        subject,
        body,
        django_settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )


def _send_2fa_email_otp(user: User, request=None) -> str:
    """Send a one-time email code to confirm the user before enabling 2FA."""
    otp = f"{random.randint(0, 999999):06d}"
    _set_2fa_email_otp(user, otp, request=request)

    try:
        send_mail(
            subject="Your EduAlly 2FA verification code",
            message=(
                f"Your EduAlly verification code is {otp}. "
                "Enter it to enable two-factor authentication."
            ),
            from_email=django_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except OSError as exc:  # covers SMTP connection issues such as ConnectionRefusedError
        log.warning("Failed to send 2FA Gmail OTP for user %s: %s", user.pk, exc)
        if request is not None:
            messages.warning(
                request,
                "Gmail is unavailable right now. For local testing, use the development code: %s",
                otp,
            )
        return otp
    except Exception as exc:
        log.warning("Unexpected error while sending 2FA Gmail OTP for user %s: %s", user.pk, exc)
        if request is not None:
            messages.warning(
                request,
                "We could not send the Gmail verification code. For local testing, use the development code: %s",
                otp,
            )
        return otp

    return otp

@ratelimit(key='ip', rate='3/h', method='POST', block=True)
def password_reset_request(request):
    """
    Step 1 – ask for an e‑mail address and send an OTP.
    """
    if request.method == "POST":
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            user = User.objects.get(email__iexact=email)  # we know it exists from clean_email()
            _send_otp_helper(email, user)

            # Store the e‑mail in the session so we know which account we’re resetting.
            request.session["pwd_reset_email"] = email
            messages.success(
                request,
                "An OTP has been sent to the e‑mail address you entered.",
            )
            return redirect("account:password_reset_confirm")
    else:
        form = PasswordResetRequestForm()

    return render(
        request,
        "account/password_reset_request.html",
        {"form": form},
    )


@ratelimit(key='ip', rate='5/h', method='POST', block=True)
def password_reset_confirm(request):
    """
    Step 2 – verify OTP and set a new password.
    """
    email = request.session.get("pwd_reset_email")
    if not email:
        # No e‑mail in session → start over.
        messages.info(request, "Please start the password‑reset process again.")
        return redirect("account:password_reset_request")

    # -------------------------------------------------
    #   POST → validate OTP and new password
    # -------------------------------------------------
    if request.method == "POST":
        form = PasswordResetConfirmForm(request.POST)
        if form.is_valid():
            otp_entered = form.cleaned_data["otp"]
            cached_otp = cache.get(f"pwd_reset_otp_{email}")

            if not cached_otp or cached_otp != otp_entered:
                form.add_error(
                    "otp", "Invalid or expired OTP. Please request a new one."
                )
            else:
                # OTP is good – change the password.
                try:
                    user = User.objects.get(email__iexact=email)
                except User.DoesNotExist:
                    # Very unlikely – the e‑mail existed when we sent the OTP.
                    messages.error(request, "User not found.")
                    return redirect("account:password_reset_request")

                user.set_password(form.cleaned_data["password1"])
                user.save()

                # Clean‑up
                cache.delete(f"pwd_reset_otp_{email}")
                request.session.pop("pwd_reset_email", None)

                messages.success(request, "Your password has been reset. You can now log in.")
                return redirect("account:login")
    else:
        form = PasswordResetConfirmForm()

    return render(
        request,
        "account/password_reset_confirm.html",
        {"form": form, "email": email},
    )
    
    
@ratelimit(key='user', rate='5/d', method='POST', block=True)   # ≤ 5 password changes per day per user
@login_required(login_url='account:login')
def change_password(request):
    """
    Dedicated endpoint for changing a password.
    The template already contains the ChangePasswordForm – we just POST to this URL.
    """
    if not request.user.has_usable_password():
        return redirect("account:add_password")

    
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid request method.")

    form = ChangePasswordForm(user=request.user, data=request.POST)
    if form.is_valid():
        form.save()
        # Keep the user logged‑in after the password change
        update_session_auth_hash(request, request.user)
        messages.success(request, "Your password was updated.")
        return redirect('account:profile')
    else:
        # Show the same edit profile page but with the form errors rendered.
        return render(request, "account/edit_profile.html", {
            "profile_form": ProfileForm(instance=request.user),   # unchanged personal‑info form
            "password_form": form,
        })
        
        
# -----------------------------------------------------------------
#   ADD / SET PASSWORD – for OAuth‑only accounts
# -----------------------------------------------------------------
@login_required(login_url='account:login')
def add_password(request):
    """
    Allows a user whose account currently has an *unusable* password
    (i.e. was created via Google) to set a password for direct login.
    If the user already has a usable password we redirect them to the
    normal change‑password page.
    """
    if request.user.has_usable_password():
        # This user already has a password → go to the regular page.
        messages.info(request, "You already have a password; you can change it on the Change‑Password page.")
        return redirect("account:password_change")

    if request.method == "POST":
        form = AddPasswordForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()                     # calls ``user.set_password()``
            # Keep the user logged‑in after setting the password
            update_session_auth_hash(request, request.user)
            messages.success(request, "Your password has been set – you can now sign in with email & password.")
            return redirect("account:profile")
    else:
        form = AddPasswordForm(user=request.user)

    return render(request, "account/add_password.html", {"form": form})
