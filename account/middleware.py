# account/middleware.py
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
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
