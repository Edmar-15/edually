"""Template filters for checking roles and formatting profile initials."""

from django import template
import re

register = template.Library()


@register.filter(name="has_group")
def has_group(user, group_name: str) -> bool:
    """
    Return True if *user* belongs to a Group called *group_name*.
    Works for AnonymousUser as well (returns False).
    """
    if not hasattr(user, "groups"):
        return False
    return user.groups.filter(name=group_name).exists()


@register.filter(name="is_student")
def is_student(user) -> bool:
    return has_group(user, "Student")


@register.filter(name="is_teacher")
def is_teacher(user) -> bool:
    return has_group(user, "Teacher")


@register.filter(name="is_admin")
def is_admin(user) -> bool:
    return has_group(user, "Admin") or user.is_superuser or user.is_staff


@register.filter(name="initials")
def initials(user) -> str:
    """Return up to two-character initials for a user object.

    Priority:
      1. first_name + last_name initials
      2. split full name into first two words
      3. first two characters of username
    """
    if not user:
        return ""

    fn = getattr(user, "first_name", "") or ""
    ln = getattr(user, "last_name", "") or ""
    if fn and ln:
        return (fn[0] + ln[0]).upper()

    full = getattr(user, "get_full_name", None)
    name = ""
    if callable(full):
        try:
            name = full() or ""
        except Exception:
            name = ""

    name = name.strip()
    if name:
        parts = [p for p in name.split() if p]
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return name[:2].upper()

    uname = (getattr(user, "username", "") or "").strip()
    if uname:
        return uname[:2].upper()

    email = (getattr(user, "email", "") or "").strip()
    if email:
        local = email.split('@')[0]
        parts = [p for p in re.split(r'[\._\-\+]', local) if p]
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return local[:2].upper()

    return ""
