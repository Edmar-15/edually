# account/views.py
from __future__ import annotations

import json
from datetime import datetime
from urllib.parse import urlencode

import requests
from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login as auth_login,
)
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse, HttpResponseRedirect
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView
from django.template.loader import render_to_string

# --------------------------------------------------------------
# Local imports
# --------------------------------------------------------------
from .forms import PublicRegisterForm, ProfileForm, LoginForm
from .models import Notification, UserConsent, User, StudentProfile
from .constants import GROUP_TEACHER, GROUP_STUDENT, GROUP_ADMIN
from .utils import user_is_in_group, add_user_to_group

# Other apps used in the dashboard
from slm.models import Module
from aihelper.models import Conversation, Message


# -----------------------------------------------------------------
#   ROLE‑BASED LOGIN VIEW
# -----------------------------------------------------------------
class RoleBasedLoginView(TemplateView):
    """
    Sub‑class of Django's LoginView that redirects users to the dashboard
    that matches their group membership.
    """
    template_name = "account/login.html"
    form_class = LoginForm
    redirect_authenticated_user = True

    def get(self, request, *args, **kwargs):
        # Let the regular LoginView handle GET (display the form)
        from django.contrib.auth.views import LoginView
        return LoginView.as_view(
            template_name=self.template_name,
            authentication_form=self.form_class,
            redirect_authenticated_user=self.redirect_authenticated_user,
        )(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # Let the regular LoginView handle POST (authenticate)
        from django.contrib.auth.views import LoginView
        response = LoginView.as_view(
            template_name=self.template_name,
            authentication_form=self.form_class,
            redirect_authenticated_user=self.redirect_authenticated_user,
        )(request, *args, **kwargs)

        # If the login succeeded, ``LoginView`` will have already set
        # request.user. We simply decide where to go next.
        if request.user.is_authenticated:
            return redirect(self.get_success_url())
        return response

    def get_success_url(self):
        """Inspect groups and decide the final dashboard."""
        user = self.request.user

        # Superusers / staff → Django admin (or a staff‑specific view)
        if user.is_superuser or user.is_staff:
            return reverse("admin:index")

        if user_is_in_group(user, GROUP_TEACHER):
            # You need to have a URL named "teacher:dashboard"
            return reverse("teacher:dashboard")

        # Default → student dashboard
        return reverse("account:dashboard")


# -----------------------------------------------------------------
#   LANDING / DASHBOARD / PROFILE etc.
# -----------------------------------------------------------------
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
    return render(request, "dashboard.html", context)


@login_required(login_url="account:login")
def notifications_inbox(request):
    notifications = Notification.objects.filter(recipient=request.user).select_related("actor").order_by("-created_at")
    notifications.filter(read=False).update(read=True)
    return render(request, "account/notifications.html", {"notifications": notifications})


@login_required(login_url="account:login")
def profile(request):
    """
    Render the profile page.
    GET → show form with current data.
    POST → validate, save and redirect back to the same page.
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

    return render(request, "account/profile.html", {"user_obj": request.user, "profile_form": form})


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


def register(request):
    """
    Public registration – uses ``PublicRegisterForm`` which now knows whether
    the user wants to be a Student or a Teacher.
    """
    policy_context = {
        "policy_version": django_settings.POLICY_VERSION,
        "effective_date": datetime.strptime(
            django_settings.POLICY_EFFECTIVE_DATE, "%Y-%m-%d"
        ),
        "GROUP_STUDENT": GROUP_STUDENT,
        "GROUP_TEACHER": GROUP_TEACHER,
    }

    if request.method == "POST":
        form = PublicRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            # Auto‑login after successful registration
            raw_password = form.cleaned_data["password1"]
            user = authenticate(request, email=user.email, password=raw_password)
            if user is not None:
                auth_login(request, user)
                messages.success(request, "Welcome! Your account has been created.")
                return redirect(reverse_lazy("account:dashboard"))
            messages.warning(
                request,
                "Account created but auto‑login failed. Please log in.",
            )
            return redirect(reverse_lazy("account:login"))
        messages.error(request, "Please fix the errors below.")
    else:
        form = PublicRegisterForm()

    return render(request, "account/register.html", {"form": form, **policy_context})



@login_required(login_url='account:login')
@ensure_csrf_cookie
def settings(request):
    """Simple settings page – kept unchanged."""
    return render(request, 'account/settings.html')


@login_required(login_url='account:login')
def logout_confirm(request):
    """
    AJAX view for logout confirmation.
    GET → return the modal HTML for the frontend.
    POST → actually log the user out.
    """
    if request.method == 'POST':
        from django.contrib.auth import logout
        logout(request)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'redirect': reverse('account:landing')})
        return redirect('account:landing')

    html = render_to_string(
        'account/logout_confirm.html',
        {'request': request},
        request=request,
    )
    return JsonResponse({'html': html})


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

    next_url = request.GET.get("state") or request.session.get(
        "post_consent_redirect", reverse("account:dashboard")
    )
    return redirect(next_url)
