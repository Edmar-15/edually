# account/middleware.py
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from django.contrib import messages
from .models import UserConsent


def _is_exempt(request):
    """
    Return ``True`` if the request should bypass the consent check.
    """
    # 1. Anonymous users – they have no consent to check.
    if not request.user.is_authenticated:
        return True

    # 2. Superusers are exempt – they never need to accept the policies.
    if request.user.is_superuser:
        return True

    # 3. Explicitly exempt URLs (login, logout, register, policy pages, admin, etc.)
    resolver_match = request.resolver_match
    if resolver_match:
        exempt_names = {
            "login",
            "logout",
            "register",
            "terms",
            "privacy",
            "consent_required",
            "logout_confirm"
        }
        if resolver_match.namespace == "account" and resolver_match.url_name in exempt_names:
            return True
        if resolver_match.namespace == "admin":
            return True

    return False


class RequireLatestConsentMiddleware(MiddlewareMixin):
    """
    Middleware that forces every authenticated non‑superuser to have a
    ``UserConsent`` for the current policy version.  If they don’t,
    they are redirected to ``account:consent_required``.
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        if _is_exempt(request):
            return None

        # Safe lookup – avoids ``UserConsent.DoesNotExist`` for new users.
        try:
            consent = request.user.consent
        except UserConsent.DoesNotExist:   # noqa: F821 – imported lazily below
            consent = None

        if consent is None or consent.version != settings.POLICY_VERSION:
            request.session["post_consent_redirect"] = request.get_full_path()
            return redirect(reverse("account:consent_required"))
        return None


def _email_verification_exempt(request) -> bool:
    """
    Return True if the current request should *not* be blocked because the
    user is allowed to visit it even when their e‑mail is un‑verified.
    """
    # 1️⃣  Anonymous users – they have no e‑mail to verify.
    if not request.user.is_authenticated:
        return True

    # 2️⃣  Staff / super‑users are trusted to bypass verification.
    if request.user.is_staff or request.user.is_superuser:
        return True

    # 3️⃣  Explicitly allow a handful of URLs (login, logout, registration,
    #     the verification page itself, consent, policy pages, password‑reset
    #     flow, etc.).
    resolver = request.resolver_match
    if resolver:
        exempt_names = {
            # authentication flow
            "login",
            "logout",
            "register",
            "verify_email",
            "email_verification_required",
            "logout_confirm",
            # consent & policies
            "consent_required",
            "terms",
            "privacy",
            # password‑reset
            "password_reset_request",
            "password_reset_confirm",
            # logout‑confirm modal (used by the UI)
            "logout_confirm",
        }

        # The view lives in the ``account`` namespace (all your auth URLs)
        if resolver.namespace == "account" and resolver.url_name in exempt_names:
            return True

        # Admin is always allowed
        if resolver.namespace == "admin":
            return True

    return False


class RequireEmailVerificationMiddleware(MiddlewareMixin):
    """
    Prevents a logged‑in user whose ``email_verified`` flag is False from
    reaching any part of the site that requires a verified address.
    The user is sent to the ``account:email_verification_required`` view,
    where a friendly message and a “Resend verification e‑mail” button are shown.
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Fast‑path: the URL is on the exempt list → let the view run.
        if _email_verification_exempt(request):
            return None

        # If the user is logged in but still un‑verified → redirect.
        if (
            request.user.is_authenticated
            and getattr(request.user, "two_factor_enabled", False)
            and not getattr(request.user, "email_verified", False)
        ):
            # Remember where they wanted to go so we can send them back after verification.
            request.session["post_verification_redirect"] = request.get_full_path()
            # Optional: give a one‑off toast/message (your templates already read
            # the messages framework).
            messages.warning(
                request,
                "You must verify your e‑mail address before you can use this page. "
                "Check your inbox for the verification link.",
            )
            return redirect(reverse("account:email_verification_required"))

        # No problem – continue to the view.
        return None