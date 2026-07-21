# slm/file_utils.py
import logging
from typing import Any

logger = logging.getLogger(__name__)

def delete_file(file_field: Any) -> None:
    """
    Delete the file behind a FileField (or any object that implements
    the ``delete(save=False)`` API).  Raises an exception on failure –
    callers should wrap it in a transaction or catch it deliberately.
    """
    if not file_field:
        return

    # ``name`` is empty for an unsaved/empty field.
    if not getattr(file_field, "name", None):
        return

    storage = getattr(file_field, "storage", None)
    name = file_field.name

    # Guard against a storage that does not implement ``exists`` (e.g. dummy storage)
    if storage is not None and hasattr(storage, "exists") and not storage.exists(name):
        # File already vanished – nothing to do.
        logger.debug("File %s does not exist, nothing to delete.", name)
        return

    try:
        # ``save=False`` prevents a second ``save()`` on the model.
        file_field.delete(save=False)
        logger.info("Deleted file %s", name)
    except Exception as exc:  # pragma: no cover – defensive
        logger.error("Failed to delete file %s: %s", name, exc)
        # Re‑raise so the caller can decide to roll back a DB transaction
        raise


# slm/file_utils.py (add a thin wrapper)
def replace_file(instance: Any, field_name: str, new_file) -> None:
    """
    Replace <instance>.<field_name> with ``new_file`` and delete the old file.
    The operation is atomic – if the new file cannot be saved the old file
    is **restored** (the DB transaction rolls back, and we never call
    ``instance.save`` with a half‑written state).
    """
    old_file = getattr(instance, field_name, None)

    # Assign the new file *first* – Django will write it to storage when we save.
    setattr(instance, field_name, new_file)

    try:
        # Save only the file field – this writes the new file to the storage backend.
        instance.save(update_fields=[field_name])
    except Exception as exc:  # pragma: no cover – storage errors
        # Attempt to roll back the DB change (the transaction that called us
        # should roll back; but we also want to keep the old file reference
        # intact for the caller's context).
        setattr(instance, field_name, old_file)
        logger.error("Failed to replace %s on %s: %s", field_name, instance, exc)
        raise

    # At this point the new file is safely stored – now delete the old one.
    if old_file:
        delete_file(old_file)