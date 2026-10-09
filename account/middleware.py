from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from django.contrib import messages
from .models import UserConsent


def _is_exempt(request):
    """
    Return True if the request should bypass the consent check.
    """

    if not request.user.is_authenticated:
        return True

    if request.user.is_superuser:
        return True

    # Keep the service worker and other site metadata outside the consent flow.
    if request.path in {
        "/service-worker.js",
        "/manifest.json",
        "/offline/",
        "/robots.txt",
        "/sitemap.xml",
    }:
        return True

    resolver_match = request.resolver_match

    if resolver_match:
        exempt_names = {
            "login",
            "logout",
            "register",
            "terms",
            "privacy",
            "consent_required",
            "logout_confirm",
            "service-worker",
            "manifest",
            "offline",
        }

        if (
            resolver_match.namespace == "account"
            and resolver_match.url_name in exempt_names
        ):
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

        try:
            consent = request.user.consent
        except UserConsent.DoesNotExist:
            consent = None

        if consent is None or consent.version != settings.POLICY_VERSION:
            if (
                request.method == "GET"
                and not request.path.startswith("/static/")
                and not request.path.startswith("/media/")
            ):
                request.session["post_consent_redirect"] = request.get_full_path()

            return redirect(reverse("account:consent_required"))


def _email_verification_exempt(request) -> bool:
    """
    Return True if the current request should *not* be blocked because the
    user is allowed to visit it even when their e‑mail is un‑verified.
    """
    if not request.user.is_authenticated:
        return True

    if request.user.is_staff or request.user.is_superuser:
        return True
    
    if request.path in {
        "/service-worker.js",
        "/manifest.json",
        "/offline/",
        "/robots.txt",
        "/sitemap.xml",
    }:
        return True

    resolver = request.resolver_match
    if resolver:
        exempt_names = {
            "login",
            "logout",
            "register",
            "verify_email",
            "email_verification_required",
            "logout_confirm",
            "consent_required",
            "terms",
            "privacy",
            "password_reset_request",
            "password_reset_confirm",
        }

        if resolver.namespace == "account" and resolver.url_name in exempt_names:
            return True

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
        if _email_verification_exempt(request):
            return None

        if (
            request.user.is_authenticated
            and not getattr(request.user, "email_verified", False)
        ):
            request.session["post_verification_redirect"] = request.get_full_path()
            messages.warning(
                request,
                "You must verify your e‑mail address before you can use this page. "
                "Check your inbox for the verification link.",
            )
            return redirect(reverse("account:email_verification_required"))

        return None