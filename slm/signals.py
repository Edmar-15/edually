# slm/signals.py
import logging
from django.db.models.signals import pre_save, post_delete
from django.dispatch import receiver
from .models import Module, PersonalMaterial
from .file_utils import delete_file

log = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# 1️⃣ Delete the *old* file when a new file is assigned (replace)
# ----------------------------------------------------------------------
def _delete_old_file(instance, field_name):
    """
    Helper used by the two pre_save receivers – deletes the previous file
    if it differs from the newly‑assigned one.
    """
    if not instance.pk:
        # New model – nothing to delete
        return

    try:
        old = getattr(instance.__class__.objects.get(pk=instance.pk), field_name)
    except instance.__class__.DoesNotExist:
        return

    new = getattr(instance, field_name)
    if old and old.name and old.name != getattr(new, "name", None):
        try:
            delete_file(old)
        except Exception as exc:  # pragma: no cover – we already log inside delete_file
            log.warning("Failed to delete old %s for %s %s: %s",
                        field_name, instance.__class__.__name__, instance.pk, exc)


@receiver(pre_save, sender=Module)
def module_pre_save_cleanup(sender, instance, **kwargs):
    _delete_old_file(instance, "file")


@receiver(pre_save, sender=PersonalMaterial)
def pm_pre_save_cleanup(sender, instance, **kwargs):
    _delete_old_file(instance, "file")

# ----------------------------------------------------------------------
# 2️⃣ Delete the file when the model row is removed (post_delete)
# ----------------------------------------------------------------------
@receiver(post_delete, sender=Module)
def module_post_delete_cleanup(sender, instance, **kwargs):
    if instance.file:
        try:
            delete_file(instance.file)
        except Exception as exc:  # pragma: no cover
            log.warning("Failed to delete Module file on post_delete: %s", exc)


@receiver(post_delete, sender=PersonalMaterial)
def pm_post_delete_cleanup(sender, instance, **kwargs):
    if instance.file:
        try:
            delete_file(instance.file)
        except Exception as exc:  # pragma: no cover
            log.warning("Failed to delete PersonalMaterial file on post_delete: %s", exc)
