# account/views.py
from __future__ import annotations

from datetime import datetime
from urllib.parse import urlencode

import json
import requests
from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login as auth_login,
)
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.views.generic import TemplateView

# --------------------------------------------------------------
# Existing imports continued (forms, models, etc.)
# --------------------------------------------------------------
from .forms import PublicRegisterForm, ProfileForm
from .models import Notification, UserConsent
from slm.models import Module
# For onboarding completion checks (ask one question)
from aihelper.models import Conversation, Message

User = get_user_model()


# -----------------------------------------------------------------
# NEW – GOOGLE OAUTH HELPERS
# -----------------------------------------------------------------
def _build_google_auth_url(state: str | None = None) -> str:
    """
    Build the Google OAuth2 authorization URL.

    Parameters
    ----------
    state: optional string – can be used to carry the original URL the
           user wanted to visit (e.g. ``request.GET.get('next')``).

    Returns
    -------
    Fully‑qualified URL that the user should be redirected to.
    """
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": django_settings.GOOGLE_CLIENT_ID,
        "redirect_uri": django_settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",  # always show account picker
    }
    if state:
        params["state"] = state
    return f"{base_url}?{urlencode(params)}"


def _exchange_code_for_tokens(code: str) -> dict:
    """
    Exchange the ``code`` received from Google for an ``access_token``
    (and an ``id_token``).  Raises ``requests.HTTPError`` on failure.
    """
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
    return resp.json()   # contains access_token, id_token, refresh_token, expires_in


def _fetch_google_userinfo(access_token: str) -> dict:
    """
    Retrieve basic user info (email, name, picture) from Google.
    """
    userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(userinfo_url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


# -----------------------------------------------------------------
# NEW – VIEW: start the OAuth flow
# -----------------------------------------------------------------
def google_login(request):
    """
    Redirect the user to Google’s OAuth consent screen.

    If the current request contains a ``next`` GET param we store it in the
    ``state`` parameter so we can return the user after a successful login.
    """
    # Preserve where the user originally wanted to go
    next_url = request.GET.get("next")
    auth_url = _build_google_auth_url(state=next_url)
    return redirect(auth_url)


# -----------------------------------------------------------------
# NEW – VIEW: handle Google’s redirect back to us
# -----------------------------------------------------------------
def google_callback(request):
    """
    Google sends us ``?code=...`` (or ``?error=...``).  We:

    1. Exchange the code for an access token.
    2. Pull the user's profile (email, name, picture).
    3. Find or create a ``User`` instance.
    4. Record consent (since this path bypasses the normal registration form).
    5. Log the user in and send them to the original ``next`` URL (or dashboard).
    """
    error = request.GET.get("error")
    if error:
        # Something went wrong on Google’s side (e.g. user denied consent)
        messages.error(request, "Google sign‑in failed – please try again.")
        return redirect(reverse("account:login"))

    code = request.GET.get("code")
    if not code:
        return HttpResponseBadRequest("Missing code parameter.")

    try:
        token_data = _exchange_code_for_tokens(code)
        access_token = token_data["access_token"]
        userinfo = _fetch_google_userinfo(access_token)
    except Exception as exc:   # pragma: no cover – defensive
        messages.error(request, "Unable to verify Google credentials.")
        return redirect(reverse("account:login"))

    # -------------------------------------------------------------
    # Extract the fields we need
    # -------------------------------------------------------------
    email = userinfo.get("email")
    full_name = userinfo.get("name", "")
    picture = userinfo.get("picture")  # optional – we just ignore it for now

    if not email:
        messages.error(request, "Google account did not return an email address.")
        return redirect(reverse("account:login"))

    # -------------------------------------------------------------
    # Find an existing user – or create a brand‑new one.
    # -------------------------------------------------------------
    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            "first_name": full_name.split(" ")[0] if full_name else "",
            "last_name": " ".join(full_name.split(" ")[1:]) if full_name else "",
            # ``username`` is optional – we leave it blank.
            "is_active": True,
        },
    )
    if created:
        # No password – set unusable so the user can still login via Google
        user.set_unusable_password()
        user.save()
        # Record consent immediately (the user is effectively “registering”)
        UserConsent.objects.create(
            user=user,
            version=django_settings.POLICY_VERSION,
            accepted_at=timezone.now(),
        )
        messages.success(request, "Your EduAlly account was created via Google.")
    else:
        # Existing user – ensure they have a consent record.
        if not hasattr(user, "consent"):
            UserConsent.objects.create(
                user=user,
                version=django_settings.POLICY_VERSION,
                accepted_at=timezone.now(),
            )

    # -------------------------------------------------------------
    # Log the user in – we use ``backend`` explicitly because the
    # ``EmailOrUsernameModelBackend`` expects a password.
    # -------------------------------------------------------------
    user.backend = "django.contrib.auth.backends.ModelBackend"
    auth_login(request, user)

    # -------------------------------------------------------------
    # Redirect to the original destination (if present)
    # -------------------------------------------------------------
    next_url = request.GET.get("state") or request.session.get(
        "post_consent_redirect", reverse("account:dashboard")
    )
    return redirect(next_url)

def landing(request):
    return render(request, "account/landing.html")

@login_required(login_url='account:login')
def dashboard(request):
    subjects = request.user.subjects.all()[:3]
    modules = Module.objects.filter(subject__author=request.user).select_related("subject")[:3]
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
            "done": modules.exists(),
        },
        {
            "title": "Ask one question",
            "detail": "Share what you are stuck on and let the community or AI helper support you.",
            # Mark done if the user has created any conversation or submitted any message
            "done": (
                Conversation.objects.filter(user=request.user).exists()
                or Message.objects.filter(user=request.user, role="user").exists()
            ),
        },
    ]

    context = {
        "subjects": subjects,
        "modules": modules,
        "recent_activity": recent_activity,
        "module_count": modules.count(),
        "subject_count": subjects.count(),
        "onboarding_steps": onboarding_steps,
    }
    return render(request, 'dashboard.html', context)


@login_required(login_url="account:login")
def notifications_inbox(request):
    notifications = Notification.objects.filter(recipient=request.user).select_related("actor").order_by("-created_at")
    # Mark notifications as read when viewing the inbox
    notifications.filter(read=False).update(read=True)
    context = {
        "notifications": notifications,
    }
    return render(request, "account/notifications.html", context)

@login_required(login_url="account:login")
def profile(request):
    """
    Render the profile page.
    GET  – show the read‑only overview + edit form (collapsed).
    POST – validate & save changes, then redirect back.
    """
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile was updated.")
            return redirect("account:profile")
        messages.error(request, "Please correct the errors below.")
    else:
        form = ProfileForm(instance=request.user)

    context = {
        "user_obj": request.user,
        "profile_form": form,
    }
    return render(request, "account/profile.html", context)


@login_required(login_url='account:login')
def profile_modal(request, pk):
    """Return a compact profile card as HTML for AJAX modal loads."""
    user_obj = get_object_or_404(User, pk=pk)
    # Lightweight counts – attempt to read attributes if present in queryset
    # Fallbacks will be provided by the template filters/defaults
    # Provide forum posts count if attribute not present
    if not hasattr(user_obj, 'forum_posts_count'):
        try:
            user_obj.forum_posts_count = user_obj.forum_posts.count()
        except Exception:
            user_obj.forum_posts_count = 0

    html = render_to_string('account/partials/profile_modal.html', {'user_obj': user_obj}, request=request)
    return JsonResponse({'html': html})


# -----------------------------------------------------------------
# REGISTER – unchanged except it now uses the trimmed PublicRegisterForm
# -----------------------------------------------------------------
def register(request):
    policy_context = {
        "policy_version": django_settings.POLICY_VERSION,
        "effective_date": datetime.strptime(
            django_settings.POLICY_EFFECTIVE_DATE, "%Y-%m-%d"
        ),
    }

    if request.method == "POST":
        form = PublicRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            raw_password = form.cleaned_data["password1"]
            user = authenticate(request, email=user.email, password=raw_password)
            if user is not None:
                auth_login(request, user)
                messages.success(request, "Welcome! Your account has been created.")
                return redirect(reverse_lazy("account:dashboard"))
            messages.warning(request, "Account created but auto‑login failed. Please log in.")
            return redirect(reverse_lazy("account:login"))

        messages.error(request, "Please fix the errors below.")
    else:
        form = PublicRegisterForm()

    return render(request, "account/register.html", {"form": form, **policy_context})

@login_required(login_url='account:login')
@ensure_csrf_cookie
def settings(request):
    return render(request, 'account/settings.html')

@login_required(login_url='account:login')
def logout_confirm(request):
    """
    AJAX view for logout confirmation.
    GET – returns the logout confirmation modal
    POST – logs out the user
    """
    if request.method == 'POST':
        from django.contrib.auth import logout
        logout(request)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'redirect': reverse('account:landing'),
            })
        return redirect('account:landing')

    # GET – return confirmation modal content as JSON
    html = render_to_string(
        'account/logout_confirm.html',
        {'request': request},
        request=request,
    )
    return JsonResponse({'html': html})

@require_POST
def api_set_theme(request):
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


class PolicyBaseView(TemplateView):
    """Common base for both policies – inject version & effective date."""
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["policy_version"] = django_settings.POLICY_VERSION
        # Convert string → date for nicer display
        context["effective_date"] = datetime.strptime(
            django_settings.POLICY_EFFECTIVE_DATE, "%Y-%m-%d"
        )
        return context
    

class ConsentRequiredView(TemplateView):
    template_name = "account/consent_required.html"

    @method_decorator(login_required(login_url='account:login'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        # User clicked the "I Agree" button
        UserConsent.objects.update_or_create(
            user=request.user,
            defaults={
                "version": django_settings.POLICY_VERSION,
                "accepted_at": timezone.now(),
            },
        )
        # Redirect back to where they originally wanted to go
        next_url = request.session.pop("post_consent_redirect", reverse("account:dashboard"))
        return redirect(next_url)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["policy_version"] = django_settings.POLICY_VERSION
        ctx["effective_date"] = datetime.strptime(
            django_settings.POLICY_EFFECTIVE_DATE, "%Y-%m-%d"
        )
        return ctx