# account/utils.py
"""
Utility helpers that wrap the built‑in Django group API.
All code that needs to check or modify a user’s role should import
and use these functions – this guarantees a single source of truth.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.conf import settings
from django.urls import reverse
from pywebpush import WebPushException, webpush
import json
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


def ensure_group(name: str) -> Group:
    """
    Return an existing ``Group`` with *name* or create it if it does not exist.
    """
    group, _ = Group.objects.get_or_create(name=name)
    return group


def add_user_to_group(user: User, group_name: str) -> None:
    """
    Add *user* to the group *group_name* (creating the group if needed).
    """
    group = ensure_group(group_name)
    user.groups.add(group)


def remove_user_from_group(user: User, group_name: str) -> None:
    """
    Remove *user* from the group *group_name*.  Silently ignore if the group
    does not exist.
    """
    try:
        group = Group.objects.get(name=group_name)
    except Group.DoesNotExist:
        return
    user.groups.remove(group)


def user_is_in_group(user: User, group_name: str) -> bool:
    """
    Quick boolean test – works for anonymous users as well.
    """
    if not user.is_authenticated:
        return False
    return user.groups.filter(name=group_name).exists()


def send_push_notification(user: User, title: str, body: str, url: str, tag: str = "edually") -> int:
    """Send a browser push to all active subscriptions for a user."""
    private_key = getattr(settings, "VAPID_PRIVATE_KEY", "")
    admin_email = getattr(settings, "VAPID_ADMIN_EMAIL", "")
    if not private_key or not admin_email:
        logger.warning("Web Push is not configured; notification was skipped.")
        return 0

    from .models import PushSubscription

    sent = 0
    payload = json.dumps({"title": title, "body": body, "url": url, "tag": tag})
    for subscription in user.push_subscriptions.all():
        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {"auth": subscription.auth, "p256dh": subscription.p256dh},
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={"sub": f"mailto:{admin_email}"},
            )
            sent += 1
        except WebPushException as error:
            status_code = getattr(getattr(error, "response", None), "status_code", None)
            if status_code in (404, 410):
                subscription.delete()
            else:
                logger.warning("Web Push delivery failed for %s: %s", user.email, error)
        except Exception:
            logger.exception("Unexpected Web Push delivery failure for %s", user.email)

    return sent
