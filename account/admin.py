# account/admin.py
from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .forms import UserCreationForm, UserChangeForm
from .models import (
    User,
    StudentProfile,
    TeacherProfile,
    Notification,
    UserConsent,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin for the core User model – authentication fields only."""
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
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "username", "password1", "password2", "is_staff", "is_active"),
            },
        ),
    )


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "student_id", "program", "year_level")
    search_fields = ("user__email", "student_id", "program")


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "employee_id", "department")
    search_fields = ("user__email", "employee_id", "department")


@admin.register(UserConsent)
class UserConsentAdmin(admin.ModelAdmin):
    list_display = ("user", "version", "accepted_at")
    list_filter = ("version",)
    search_fields = ("user__email", "user__username")
    ordering = ("-accepted_at",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "actor", "verb", "target_post", "target_reply", "read", "created_at")
    list_filter = ("read", "created_at")
    search_fields = ("recipient__email", "actor__email", "verb")
    ordering = ("-created_at",)
