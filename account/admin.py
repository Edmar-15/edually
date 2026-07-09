# account/admin.py
from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User
from .forms import UserCreationForm, UserChangeForm
from .models import UserConsent


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = UserCreationForm
    form = UserChangeForm
    model = User

    list_display = (
        "email",
        "username",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("email", "username", "first_name", "last_name")
    ordering = ("-date_joined",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),

        ("Personal info", {"fields": ("username", "first_name", "last_name", "avatar")}),

        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),

        ("Important dates", {"fields": ("last_login", "date_joined")}),

        # New extra fields specific to EduAlly
        ("Student data", {"fields": ("student_id", "program", "year_level")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "password1", "password2", "is_staff", "is_active"),
        }),
    )


@admin.register(UserConsent)
class UserConsentAdmin(admin.ModelAdmin):
    list_display = ("user", "version", "accepted_at")
    list_filter = ("version",)
    search_fields = ("user__email", "user__username")
    ordering = ("-accepted_at",)
