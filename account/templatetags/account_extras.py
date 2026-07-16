# account/templatetags/account_extras.py
"""
Template helpers that make RBAC checks readable in the HTML.
You can use:

    {% if request.user|has_group:"Teacher" %}
        …teacher‑only markup…
    {% endif %}

or the shortcut booleans:

    {% if request.user|is_student %}
        …student‑only markup…
    {% endif %}
"""

from django import template

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


# ------------------------------------------------------------
# Shortcut booleans – they read a little nicer in templates
# ------------------------------------------------------------
@register.filter(name="is_student")
def is_student(user) -> bool:
    return has_group(user, "Student")


@register.filter(name="is_teacher")
def is_teacher(user) -> bool:
    return has_group(user, "Teacher")


@register.filter(name="is_admin")
def is_admin(user) -> bool:
    return has_group(user, "Admin") or user.is_superuser or user.is_staff
