# account/models.py
from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """
    Core authentication model – **only** authentication‑related fields.
    All role‑specific data lives in the one‑to‑one profile tables below.
    """
    email = models.EmailField("email address", unique=True)

    username = models.CharField(
        "username",
        max_length=150,
        blank=True,
        help_text="Optional – for display or alternative login.",
    )

    first_name = models.CharField("first name", max_length=150, blank=True)
    last_name = models.CharField("last name", max_length=150, blank=True)

    avatar = models.ImageField(
        "profile picture",
        upload_to="avatars/%Y/%m/%d/",
        blank=True,
        null=True,
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

    two_factor_enabled = models.BooleanField(
        "two-factor authentication enabled",
        default=False,
        help_text="Require a one-time code from an authenticator app during login.",
    )
    two_factor_secret = models.CharField(
        "two-factor secret",
        max_length=64,
        blank=True,
        default="",
        help_text="Base32 secret used for TOTP generation.",
    )

    # Reputation system – kept unchanged
    karma = models.IntegerField(
        default=0,
        help_text="Points earned from helpful posts and replies. Starts at 0.",
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # only email & password are required

    class Meta:
        ordering = ["-date_joined"]
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self) -> str:
        return self.email

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.email

    @property
    def short_name(self) -> str:
        return self.first_name or self.email

    @property
    def forum_badge_label(self) -> str:
        if self.karma >= 100:
            return "Expert"
        if self.karma >= 20:
            return "Helpful"
        return "Beginner"

    def get_full_name(self) -> str:
        return self.full_name

    def get_short_name(self) -> str:
        return self.short_name

    # -----------------------------------------------------------------
    # Convenience read‑only properties that forward to the profile.
    # They let existing templates keep using {{ user.student_id }} etc.
    # -----------------------------------------------------------------
    @property
    def student_id(self):
        """
        Return the StudentProfile.student_id if a StudentProfile exists,
        otherwise return an empty string.
        """
        try:
            return self.student_profile.student_id
        except StudentProfile.DoesNotExist:      # <-- safe fallback
            return ""

    @property
    def program(self):
        """
        Return the StudentProfile.program if a StudentProfile exists,
        otherwise return an empty string.
        """
        try:
            return self.student_profile.program
        except StudentProfile.DoesNotExist:
            return ""

    @property
    def year_level(self):
        """
        Return the StudentProfile.year_level if a StudentProfile exists,
        otherwise return an empty string.
        """
        try:
            return self.student_profile.year_level
        except StudentProfile.DoesNotExist:
            return ""
        
    def has_group(self, group_name: str) -> bool:
        """Checks if a user belongs to a specific group name."""
        return self.groups.filter(name=group_name).exists()

    @property
    def is_student_member(self) -> bool:
        """Returns True if user is in the Student group."""
        return self.has_group("Student")

    @property
    def is_teacher_member(self) -> bool:
        """Returns True if user is in the Teacher group."""
        return self.has_group("Teacher")

    @property
    def is_admin_member(self) -> bool:
        """Returns True if user is Admin, superuser, or staff."""
        return self.has_group("Admin") or self.is_superuser or self.is_staff


# -----------------------------------------------------------------
#   ONE‑TO‑ONE PROFILE MODELS
# -----------------------------------------------------------------
class StudentProfile(models.Model):
    """All data that only makes sense for a student."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
    )
    student_id = models.CharField(
        "Student ID",
        max_length=30,
        blank=True,
        help_text="University‑assigned identifier.",
    )
    # Default programme → “Information Technology”
    program = models.CharField(
        "Program / Course",
        max_length=100,
        blank=True,
        default="Information Technology",
    )
    # Year level is now required and limited to 1st‑4th year
    YEAR_CHOICES = [
        ("2nd Year", "2nd Year"),
        ("3rd Year", "3rd Year"),
    ]
    year_level = models.CharField(
        "Year Level",
        max_length=20,
        choices=YEAR_CHOICES,
    )
    
    def clean(self):
        """
        Prevent a user from changing the year level after it has been saved once.
        """
        super().clean()
        if self.pk:                                   # only on updates
            orig = StudentProfile.objects.filter(pk=self.pk).first()
            if orig and orig.year_level and self.year_level != orig.year_level:
                raise ValidationError("Year level cannot be changed once set.")

    def __str__(self) -> str:
        return f"StudentProfile({self.user.email})"


class TeacherProfile(models.Model):
    """Optional profile for staff / teachers."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_profile",
    )
    employee_id = models.CharField(
        "Employee ID",
        max_length=30,
        blank=True,
        help_text="Internal staff identifier.",
    )
    # Department is now always “CCS”
    department = models.CharField(
        "Department",
        max_length=100,
        default="CCS",
        blank=True,
    )

    def __str__(self) -> str:
        return f"TeacherProfile({self.user.email})"


# -----------------------------------------------------------------
#   CONSENT & NOTIFICATIONS (unchanged)
# -----------------------------------------------------------------
class UserConsent(models.Model):
    """
    Records each time a user accepts the latest Terms & Conditions &
    Privacy Notice.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="consent",
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


class PushSubscription(models.Model):
    """
    One subscription per endpoint per user.
    The data is exactly what the browser’s ServiceWorkerSubscription object
    contains (endpoint, p256dh, auth).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    endpoint = models.URLField()
    auth = models.CharField(max_length=255)
    p256dh = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "endpoint")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"PushSubscription({self.user.email}, {self.endpoint[:30]}…)"