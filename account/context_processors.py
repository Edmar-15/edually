from django.contrib.auth import get_user_model


def unread_notifications(request):
    """Expose the current user's unread notification count to all templates."""
    if not request.user.is_authenticated:
        return {"unread_notification_count": 0}

    user_model = get_user_model()
    return {
        "unread_notification_count": request.user.notifications.filter(read=False).count()
    }

def user_groups(request):
    """
    Adds three booleans (is_student, is_teacher, is_admin) and the full
    QuerySet of groups to the template context.
    """
    if not request.user.is_authenticated:
        return {"is_student": False, "is_teacher": False, "is_admin": False, "user_groups": []}
    return {
        "is_student": request.user.groups.filter(name="Student").exists(),
        "is_teacher": request.user.groups.filter(name="Teacher").exists(),
        "is_admin": request.user.is_staff or request.user.is_superuser,
        "user_groups": request.user.groups.all(),
    }