# aihelper/models.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Conversation(models.Model):
    """
    A single chat thread belonging to a user.
    """
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="ai_conversations"
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        help_text="First user question (auto‑filled) – used in the sidebar.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Conversation"
        verbose_name_plural = "Conversations"

    def __str__(self):
        return self.title or f"Conversation {self.id}"


class Message(models.Model):
    """
    One entry in a conversation.
    """
    ROLE_CHOICES = [
        ("user", "User"),
        ("ai", "AI"),
    ]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="ai_messages"
    )
    role = models.CharField(max_length=4, choices=ROLE_CHOICES)
    content = models.TextField()
    SOURCE_TYPE_CHOICES = [
        ("slm", "SLM"),
        ("general", "General Knowledge"),
    ]

    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_TYPE_CHOICES,
        null=True,
        blank=True,
        default=None,
    )

    source_label = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    source_metadata = models.JSONField(
        default=list,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
        ]

    def __str__(self):
        return f"{self.role.title()} @ {self.created_at:%Y-%m-%d %H:%M}"
