from django.conf import settings as django_settings
from django.shortcuts import redirect
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth import logout
from django.urls import reverse

class IdleTimeoutMiddleware:
    """Log out users after a period of inactivity."""
    def __init__(self, get_response):
        self.get_response = get_response
        self.timeout = getattr(django_settings, "IDLE_TIMEOUT", 30 * 60)

    def __call__(self, request):
        if (
            request.path.startswith('/static/') or 
            request.path.startswith('/media/') or 
            request.path.endswith('.js') or 
            request.path.endswith('.css')
        ):
            return self.get_response(request)

        if request.user.is_authenticated:
            now = timezone.now()
            last_ts = request.session.get("last_activity")

            if last_ts:
                try:
                    last_activity_time = timezone.datetime.fromisoformat(last_ts)
                    elapsed = (now - last_activity_time).total_seconds()
                    
                    if elapsed > self.timeout:
                        logout(request)
                        messages.info(
                            request,
                            f"You have been logged out after {self.timeout // 60} minutes of inactivity."
                        )
                        return redirect(reverse("account:login"))
                except (ValueError, TypeError):
                    pass

            request.session["last_activity"] = now.isoformat()

        return self.get_response(request)