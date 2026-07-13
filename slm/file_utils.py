# ─────────────────────────────────────────────────────────────────────────────
# slm/file_utils.py
# Helper utilities for safely deleting/replacing FileField files.
# ─────────────────────────────────────────────────────────────────────────────
import logging
from typing import Any

logger = logging.getLogger(__name__)

def delete_file(file_field: Any) -> None:
    """
    Delete the file behind a ``FileField`` (or any object that implements the
    ``delete(save=False)`` API).  Silently ignore missing files but log any
    unexpected error.

    The function **does not** call ``save()`` on the model – callers have to
    persist the model themselves if they also change other fields.
    """
    if not file_field:
        return

    # ``name`` is empty for an unsaved/empty field.
    if not getattr(file_field, "name", None):
        return

    try:
        # ``save=False`` prevents a second ``save()`` on the model.
        file_field.delete(save=False)
    except Exception as exc:                     # pragma: no cover – defensive
        logger.warning("Failed to delete file %s: %s", getattr(file_field, "name", "<unknown>"), exc)


def replace_file(instance: Any, field_name: str, new_file) -> None:
    """
    Replace ``instance.<field_name>`` with ``new_file`` **and delete the old
    file**.  The model instance is saved (only the file field is updated).

    Example
    -------
    >>> replace_file(module, "file", request.FILES["file"])
    """
    old_file = getattr(instance, field_name, None)
    delete_file(old_file)

    setattr(instance, field_name, new_file)
    # ``update_fields`` is used where we only want to touch the file column.
    instance.save(update_fields=[field_name])