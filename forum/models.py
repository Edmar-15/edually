# forum/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.db.models import F          # <-- NEW import (used by signals)

class Category(models.Model):
    """Forum categories (e.g. General Discussion, Course Questions, …)"""
    name = models.CharField(max_length=64, unique=True)
    slug = models.SlugField(max_length=64, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Post(models.Model):
    """A single forum thread / question."""
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_posts",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name="posts",
    )
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    # moderation fields
    verified = models.BooleanField(default=False)   # teacher‑approved
    flagged = models.BooleanField(default=False)   # user‑reported

    # engagement stats
    upvotes = models.PositiveIntegerField(default=0)
    replies_cnt = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["title"], name="forum_post_title_idx"),
            models.Index(fields=["created_at"], name="forum_post_created_idx"),
        ]

    def __str__(self):
        return self.title


class PostUpvote(models.Model):
    """Many‑to‑many through model to prevent duplicate up‑votes."""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="upvote_set")
    voter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_upvotes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("post", "voter")
        ordering = ["-created_at"]


class Reply(models.Model):
    """A reply to a post."""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="replies")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_replies",
    )
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]
