# account/templatetags/visibility_tags.py
from django import template

register = template.Library()

@register.filter
def short_vis(label):
    """
    Takes the verbose label (e.g. “Public – any logged‑in user can see it”)
    and returns only the first word (“Public” or “Private”).
    """
    if not label:
        return ""
    return label.split(" – ")[0]      # split on the long‑dash we used in the label
