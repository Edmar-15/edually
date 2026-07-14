from django.contrib.auth import get_user_model


def unread_notifications(request):
    """Expose the current user's unread notification count to all templates."""
    if not request.user.is_authenticated:
        return {"unread_notification_count": 0}

    user_model = get_user_model()
    return {
        "unread_notification_count": request.user.notifications.filter(read=False).count()
    }
