# account/admin.py
from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .forms import UserCreationForm, UserChangeForm
from .models import (
    User,
    StudentProfile,
    TeacherProfile,
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
    list_display = ("user", "employee_id")
    search_fields = ("user__email", "employee_id")


@admin.register(UserConsent)
class UserConsentAdmin(admin.ModelAdmin):
    list_display = ("user", "version", "accepted_at")
    list_filter = ("version",)
    search_fields = ("user__email", "user__username")
    ordering = ("-accepted_at",)
    
    
from django.contrib import admin
from axes.admin import AccessAttemptAdmin
from axes.models import AccessAttempt, AccessAttemptExpiration

# 1. Unregister django-axes default admin layout
admin.site.unregister(AccessAttempt)

# 2. Subclass with corrected model attribute logic
@admin.register(AccessAttempt)
class CustomAccessAttemptAdmin(AccessAttemptAdmin):
    
    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        # Drop the raw unformatted object string column out of your list layout
        cleaned_list = [f for f in self.list_display if f != 'access_attempt_expiration']
        self.list_display = tuple(cleaned_list + ['get_expiration_time'])

    @admin.display(description='Access Attempt Expiration')
    def get_expiration_time(self, obj):
        # Match using the exact foreign key field name: access_attempt_id
        expiration_record = AccessAttemptExpiration.objects.filter(access_attempt_id=obj.id).first()
        
        # Pull the correct timestamp column name: expires_at
        if expiration_record and expiration_record.expires_at:
            return expiration_record.expires_at.strftime("%b. %d, %Y, %I:%M %p")
            
        return "-"
