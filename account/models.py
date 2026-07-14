# account/models.py
from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.conf import settings

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField("email address", unique=True)
    username = models.CharField(
        "username",
        max_length=150,
        blank=True,
        null=True,
        help_text="Optional – for display or alternative login.",
    )

    first_name = models.CharField("first name", max_length=150, blank=True)
    last_name = models.CharField("last name", max_length=150, blank=True)

    avatar = models.ImageField(
        "profile picture", upload_to="avatars/", blank=True, null=True
    )
    
    student_id   = models.CharField(
        "Student ID",
        max_length=30,
        blank=True,
        help_text="University‑assigned identifier (optional).",
    )
    program      = models.CharField(
        "Program / Course",
        max_length=100,
        blank=True,
    )
    year_level   = models.CharField(
        "Year Level",
        max_length=20,
        blank=True,
    )

    is_staff = models.BooleanField(
        "staff status",
        default=False,
        help_text="Designates whether the user can log into the admin site.",
    )
    is_active = models.BooleanField(
        "active",
        default=True,
        help_text="Unselect this instead of deleting accounts.",
    )
    date_joined = models.DateTimeField("date joined", default=timezone.now)
    
    # Reputation system
    karma = models.IntegerField(
        default=0,
        help_text="Points earned from helpful posts and replies. Starts at 0."
    )

    objects = UserManager()

    USERNAME_FIELD = "email"  
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        ordering = ["-date_joined"]

    def __str__(self) -> str:
        return self.email

    @property
    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.email

    @property
    def get_short_name(self) -> str:
        return self.first_name or self.email


class UserConsent(models.Model):
    """
    Records each time a user accepts the latest Terms & Conditions & Privacy Notice.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='consent',
        primary_key=True,
    )
    version = models.CharField(
        max_length=10,
        help_text="Policy version the user accepted (e.g., '1.0').",
    )
    accepted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "User Consent"
        verbose_name_plural = "User Consents"

    def __str__(self) -> str:
        return f"{self.user.email} – v{self.version} ({self.accepted_at:%Y-%m-%d})"


class Notification(models.Model):
    """In-app notification for a user."""
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications_sent",
        null=True,
        blank=True,
    )
    verb = models.CharField(max_length=120)
    target_post = models.ForeignKey(
        "forum.Post",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    target_reply = models.ForeignKey(
        "forum.Reply",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    url = models.CharField(max_length=255, blank=True)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self) -> str:
        recipient_name = self.recipient.get_short_name or str(self.recipient)
        return f"Notification for {recipient_name}: {self.verb}"

    @property
    def message(self) -> str:
        if self.actor:
            actor_name = self.actor.get_short_name or str(self.actor)
            return f"{actor_name} {self.verb}"
        return self.verb

    @property
    def destination(self) -> str:
        return self.url or "#"
