# forum/signals.py
from django.db.models import F
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Reply, Post, ReplyUpvote, PostUpvote
from django.conf import settings


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


@receiver(post_save, sender=ReplyUpvote)
def increment_reply_upvotes(sender, instance, created, **kwargs):
    """
    When a new ReplyUpvote is created increment the reply's upvote counter.
    """
    if created:
        Reply.objects.filter(pk=instance.reply_id).update(
            upvotes=F("upvotes") + 1
        )
        # Award karma to reply author
        Reply.objects.filter(pk=instance.reply_id).select_related('author')
        PostAuthor = Reply.objects.filter(pk=instance.reply_id).values_list('author_id', flat=True).first()
        if PostAuthor:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            User.objects.filter(pk=PostAuthor).update(karma=F('karma') + 1)


@receiver(post_delete, sender=ReplyUpvote)
def decrement_reply_upvotes(sender, instance, **kwargs):
    """
    When a ReplyUpvote is deleted decrement the reply's upvote counter.
    """
    Reply.objects.filter(pk=instance.reply_id).update(
        upvotes=F("upvotes") - 1
    )
    # Remove karma from reply author
    PostAuthor = Reply.objects.filter(pk=instance.reply_id).values_list('author_id', flat=True).first()
    if PostAuthor:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        User.objects.filter(pk=PostAuthor).update(karma=F('karma') - 1)


@receiver(post_save, sender=PostUpvote)
def increment_post_upvotes(sender, instance, created, **kwargs):
    """
    When a new PostUpvote is created increment the post's upvote counter
    and award karma to the post author.
    """
    if created:
        Post.objects.filter(pk=instance.post_id).update(
            upvotes=F("upvotes") + 1
        )
        # Award karma to post author
        PostAuthor = Post.objects.filter(pk=instance.post_id).values_list('author_id', flat=True).first()
        if PostAuthor:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            User.objects.filter(pk=PostAuthor).update(karma=F('karma') + 1)


@receiver(post_delete, sender=PostUpvote)
def decrement_post_upvotes(sender, instance, **kwargs):
    """
    When a PostUpvote is deleted decrement the post's upvote counter
    and remove karma from the post author.
    """
    Post.objects.filter(pk=instance.post_id).update(
        upvotes=F("upvotes") - 1
    )
    PostAuthor = Post.objects.filter(pk=instance.post_id).values_list('author_id', flat=True).first()
    if PostAuthor:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        User.objects.filter(pk=PostAuthor).update(karma=F('karma') - 1)
