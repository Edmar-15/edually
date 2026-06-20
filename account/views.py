# account/views.py
from __future__ import annotations

from datetime import datetime
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login as auth_login,
)
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

# --------------------------------------------------------------
# Existing imports continued (forms, models, etc.)
# --------------------------------------------------------------
from .forms import PublicRegisterForm
from .models import UserConsent

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
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
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
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
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
            version=settings.POLICY_VERSION,
            accepted_at=timezone.now(),
        )
        messages.success(request, "Your EduAlly account was created via Google.")
    else:
        # Existing user – ensure they have a consent record.
        if not hasattr(user, "consent"):
            UserConsent.objects.create(
                user=user,
                version=settings.POLICY_VERSION,
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

def register(request):
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
            else:
                messages.warning(request, "Account created but auto‑login failed. Please log in.")
                return redirect(reverse_lazy("account:login"))
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = PublicRegisterForm()
        
        policy_context = {
            "policy_version": settings.POLICY_VERSION,
            "effective_date": datetime.strptime(
                settings.POLICY_EFFECTIVE_DATE, "%Y-%m-%d"
            ),
        }
    return render(request, "account/register.html", {"form": form, **policy_context})

def landing(request):
    return render(request, "account/landing.html")

@login_required(login_url='account:login')
def dashboard(request):
    return render(request, 'dashboard.html')

@login_required(login_url='account:login')
def profile(request):
    return render(request, 'account/profile.html')


class PolicyBaseView(TemplateView):
    """Common base for both policies – inject version & effective date."""
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["policy_version"] = settings.POLICY_VERSION
        # Convert string → date for nicer display
        context["effective_date"] = datetime.strptime(
            settings.POLICY_EFFECTIVE_DATE, "%Y-%m-%d"
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
                "version": settings.POLICY_VERSION,
                "accepted_at": timezone.now(),
            },
        )
        # Redirect back to where they originally wanted to go
        next_url = request.session.pop("post_consent_redirect", reverse("account:dashboard"))
        return redirect(next_url)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["policy_version"] = settings.POLICY_VERSION
        ctx["effective_date"] = datetime.strptime(
            settings.POLICY_EFFECTIVE_DATE, "%Y-%m-%d"
        )
        return ctx