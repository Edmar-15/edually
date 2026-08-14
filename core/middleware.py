from django.conf import settings as django_settings
from django.shortcuts import redirect
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth import logout
from django.urls import reverse

class IdleTimeoutMiddleware:
    """
    Logs a user out after `settings.IDLE_TIMEOUT` seconds of inactivity.
    Works for the *whole* project because it is placed after
    AuthenticationMiddleware in ``MIDDLEWARE``.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # Default to 30 minutes (1800 seconds) if not explicitly set
        self.timeout = getattr(django_settings, "IDLE_TIMEOUT", 30 * 60)

    def __call__(self, request):
        
        if (
            request.path.startswith('/static/') or 
            request.path.startswith('/media/') or 
            request.path.endswith('.js') or 
            request.path.endswith('.css')
        ):
            return self.get_response(request)
        # 1. Only process authenticated users
        if request.user.is_authenticated:
            now = timezone.now()  # Standard, aware UTC timestamp
            last_ts = request.session.get("last_activity")

            if last_ts:
                try:
                    # Parsed time inherits the timezone info stored in the string
                    last_activity_time = timezone.datetime.fromisoformat(last_ts)
                    elapsed = (now - last_activity_time).total_seconds()
                    
                    if elapsed > self.timeout:
                        logout(request)  # Clears session data completely
                        messages.info(
                            request,
                            f"You have been logged out after {self.timeout // 60} minutes of inactivity."
                        )
                        return redirect(reverse("account:login"))
                except (ValueError, TypeError):
                    # Fallback protection if session string format gets corrupted
                    pass

            # Update the activity timestamp string for the next check
            request.session["last_activity"] = now.isoformat()

        # 2. Continue down the middleware chain
        return self.get_response(request)