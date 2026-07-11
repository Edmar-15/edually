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
    flag_reason = models.TextField(blank=True, help_text="Reason post was flagged")
    is_deleted = models.BooleanField(default=False)  # soft delete

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
    updated_at = models.DateTimeField(auto_now=True)
    upvotes = models.PositiveIntegerField(default=0)
    is_deleted = models.BooleanField(default=False)  # soft delete

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Reply by {self.author.username} on {self.post.title}"


class ReplyUpvote(models.Model):
    """Track upvotes on replies to prevent duplicates."""
    reply = models.ForeignKey(Reply, on_delete=models.CASCADE, related_name="upvote_set")
    voter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_reply_upvotes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("reply", "voter")
        ordering = ["-created_at"]


class FlagReport(models.Model):
    """Track user reports on inappropriate content."""
    CONTENT_TYPE_CHOICES = [("post", "Post"), ("reply", "Reply")]
    REASON_CHOICES = [
        ("spam", "Spam"),
        ("harassment", "Harassment/Abuse"),
        ("inappropriate", "Inappropriate Content"),
        ("misinformation", "Misinformation"),
        ("other", "Other"),
    ]

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="forum_reports",
    )
    content_type = models.CharField(max_length=10, choices=CONTENT_TYPE_CHOICES)
    post = models.ForeignKey(
        Post, on_delete=models.CASCADE, null=True, blank=True, related_name="flag_reports"
    )
    reply = models.ForeignKey(
        Reply, on_delete=models.CASCADE, null=True, blank=True, related_name="flag_reports"
    )
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    action_taken = models.CharField(
        max_length=50,
        blank=True,
        help_text="Action taken (e.g., 'content removed', 'user warned')",
    )

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("reporter", "content_type", "post", "reply")
