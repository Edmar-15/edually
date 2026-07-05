# models.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Message(models.Model):
    """
    One entry in a conversation.
    """
    ROLE_CHOICES = [
        ("user", "User"),
        ("ai", "AI"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ai_messages")
    role = models.CharField(max_length=4, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role.title()} @ {self.created_at:%Y-%m-%d %H:%M}"
