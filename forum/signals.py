# forum/signals.py
from django.db.models import F
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Reply, Post


@receiver(post_save, sender=Reply)
def increment_reply_count(sender, instance, created, **kwargs):
    """
    When a new Reply is created we increase the stored counter.
    """
    if created:
        Post.objects.filter(pk=instance.post_id).update(
            replies_cnt=F("replies_cnt") + 1
        )


@receiver(post_delete, sender=Reply)
def decrement_reply_count(sender, instance, **kwargs):
    """
    When a Reply is deleted we decrease the stored counter.
    """
    Post.objects.filter(pk=instance.post_id).update(
        replies_cnt=F("replies_cnt") - 1
    )
