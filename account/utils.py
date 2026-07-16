# account/utils.py
"""
Utility helpers that wrap the built‑in Django group API.
All code that needs to check or modify a user’s role should import
and use these functions – this guarantees a single source of truth.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()


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
