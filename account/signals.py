# account/signals.py
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import User, UserConsent


@receiver(post_save, sender=User)
def auto_consent_for_staff(sender, instance, created, **kwargs):
    """
    When a staff or super‑user account is created we give it a consent
    record automatically so the consent middleware never blocks them.
    """
    if not created:
        return

    if instance.is_staff or instance.is_superuser:
        UserConsent.objects.create(
            user=instance,
            version=settings.POLICY_VERSION,
            accepted_at=timezone.now(),
        )
