# account/middleware.py
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from django.utils.functional import SimpleLazyObject


def _is_exempt(request):
    """
    Return True if the request should **bypass** the consent check.
    """
    # 1. Anonymous users – they have no consent to check.
    if not request.user.is_authenticated:
        return True

    # 2. Superusers are exempt – they never need to accept the policies.
    if request.user.is_superuser:
        return True

    # 3. Explicitly exempt URLs (login, logout, register, the policy pages, admin, etc.)
    resolver_match = request.resolver_match
    if resolver_match:
        # Namespaces & names we know are public
        exempt_names = {
            "login",
            "logout",
            "register",
            "terms",
            "privacy",
            "consent_required",
        }

        # If the request lives under the *account* namespace and matches one of the
        # exempt names, let it pass.
        if resolver_match.namespace == "account" and resolver_match.url_name in exempt_names:
            return True

        # Admin URLs (they already have permission checks)
        if resolver_match.namespace == "admin":
            return True

    # Anything else – not exempt.
    return False


class RequireLatestConsentMiddleware(MiddlewareMixin):
    """
    Middleware that ensures every **authenticated non‑superuser** has accepted the
    latest Terms & Conditions / Privacy Notice. If they haven’t, they are
    redirected to a tiny “consent required” page where they can review the
    policies and click “I Agree”.
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        # If the request is for an exempt URL or the user is a superuser,
        # simply let the view run.
        if _is_exempt(request):
            return None

        # At this point we know the user is authenticated and NOT a superuser.
        # Check their consent record.
        consent = getattr(request.user, "consent", None)

        # If there is *no* consent record or the stored version is stale,
        # push them to the consent‑required view.
        if consent is None or consent.version != settings.POLICY_VERSION:
            # Save the URL they originally wanted – we’ll send them back after consent.
            request.session["post_consent_redirect"] = request.get_full_path()
            return redirect(reverse("account:consent_required"))

        # Consent exists and is up‑to‑date → allow the original view.
        return None
