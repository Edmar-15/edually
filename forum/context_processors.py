# account/context_processors.py
from forum.models import Notification

def unread_notifications(request):
    """
    Add `unread_notifications_count` and `recent_notifications` to every
    template context for authenticated users.
    """
    if not request.user.is_authenticated:
        return {}

    # Use the correct reverse manager (`forum_notifications`) – or query the model
    unread = request.user.forum_notifications.filter(read=False).count()
    # or: unread = Notification.objects.filter(recipient=request.user,
    #                                         read=False).count()

    recent = (
        Notification.objects.filter(recipient=request.user)
        .select_related('actor', 'target_post', 'target_reply')
        .order_by('-created_at')[:8]
    )

    return {
        'unread_notifications_count': unread,
        'recent_notifications': recent,
    }
