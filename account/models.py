# account/models.py
from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

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
    phone_number = models.CharField(
        "phone number", max_length=20, blank=True, help_text="Optional."
    )
    birth_date = models.DateField("date of birth", blank=True, null=True)
    avatar = models.ImageField(
        "profile picture", upload_to="avatars/", blank=True, null=True
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
