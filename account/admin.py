from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.db.models import Count, Q
from django.utils.html import format_html
from .forms import UserCreationForm, UserChangeForm
from .models import (
    User,
    StudentProfile,
    TeacherProfile,
    UserConsent,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Human-readable user management; Django still enforces permissions."""
    add_form = UserCreationForm
    form = UserChangeForm
    model = User
    change_list_template = "admin/account/user/change_list.html"
    change_form_template = "admin/account/user/change_form.html"
    add_form_template = "admin/account/user/change_form.html"

    list_display = (
        "account_identity",
        "role_summary",
        "account_status",
        "email_status",
        "admin_access_badge",
        "date_joined",
    )
    list_display_links = ("account_identity",)
    list_filter = (
        "is_active",
        "email_verified",
        "is_staff",
        "is_superuser",
        "groups",
    )
    search_fields = ("email", "username", "first_name", "last_name")
    search_help_text = "Search by email address, username, first name, or last name."
    ordering = ("-date_joined",)
    list_per_page = 25

    # Keep all original editable fields, including the advanced permissions.
    fieldsets = (
        (
            "Sign-in and email verification",
            {
                "fields": ("email", "password", "email_verified"),
                "description": (
                    "Manage the account's sign-in email and verification status. "
                    "Use the password link to change the password securely."
                ),
            },
        ),
        (
            "Personal information",
            {"fields": ("username", "first_name", "last_name", "avatar")},
        ),
        (
            "Account access",
            {
                "fields": ("is_active", "is_staff"),
                "description": (
                    "An inactive account cannot sign in. Staff status grants "
                    "access to the admin site, subject to assigned permissions."
                ),
            },
        ),
        (
            "Advanced permissions",
            {
                "classes": ("collapse",),
                "fields": ("is_superuser", "groups", "user_permissions"),
                "description": (
                    "Superusers have all permissions. Groups and individual "
                    "permissions determine what other users can manage."
                ),
            },
        ),
        (
            "Account dates",
            {
                "fields": ("last_login", "date_joined"),
                "classes": ("collapse",),
            },
        ),
    )

    # Keep the exact creation fields/behavior already used in EduAlly.
    add_fieldsets = (
        (
            "Create a user account",
            {
                "classes": ("wide",),
                "fields": (
                    "email", "username", "password1", "password2",
                    "is_staff", "is_active",
                ),
                "description": (
                    "Enter an email address and password. Staff access is "
                    "optional and does not automatically grant all permissions. "
                    "You can assign groups after creating the account."
                ),
            },
        ),
    )

    def get_queryset(self, request):
        # Avoid one group lookup per account in the list's Role column.
        return super().get_queryset(request).prefetch_related("groups")

    @admin.display(description="Account", ordering="email")
    def account_identity(self, obj):
        name = " ".join(part for part in (obj.first_name, obj.last_name) if part).strip()
        secondary = name or ("@" + obj.username if obj.username else "No name provided")
        return format_html(
            '<span class="edually-user-primary">{}</span>'
            '<span class="edually-user-secondary">{}</span>',
            obj.email,
            secondary,
        )

    @admin.display(description="Role / group")
    def role_summary(self, obj):
        roles = [group.name for group in obj.groups.all()]
        if obj.is_superuser:
            roles.insert(0, "Superuser")
        elif obj.is_staff:
            roles.insert(0, "Staff")
        return ", ".join(roles) if roles else "No group assigned"

    @admin.display(description="Account status", ordering="is_active")
    def account_status(self, obj):
        css_class = "active" if obj.is_active else "inactive"
        label = "Active" if obj.is_active else "Inactive"
        return format_html(
            '<span class="edually-user-badge edually-user-badge--{}">{}</span>',
            css_class,
            label,
        )

    @admin.display(description="Email verification", ordering="email_verified")
    def email_status(self, obj):
        css_class = "verified" if obj.email_verified else "unverified"
        label = "Verified" if obj.email_verified else "Not verified"
        return format_html(
            '<span class="edually-user-badge edually-user-badge--{}">{}</span>',
            css_class,
            label,
        )

    @admin.display(description="Admin access", ordering="is_staff")
    def admin_access_badge(self, obj):
        # Make the status explicit, rather than Django's red "X" icon.
        if obj.is_staff:
            return format_html(
                '<span class="edually-user-badge edually-user-badge--staff">{}</span>',
                "Enabled",
            )
        return format_html(
            '<span class="edually-user-badge edually-user-badge--no-staff">{}</span>',
            "Not enabled",
        )

    def changelist_view(self, request, extra_context=None):
        # Only reveal account totals if the user can view this model.
        if request.method == "GET" and self.has_view_or_change_permission(request):
            counts = self.model.objects.aggregate(
                total=Count("pk"),
                active=Count("pk", filter=Q(is_active=True)),
                inactive=Count("pk", filter=Q(is_active=False)),
                not_verified=Count("pk", filter=Q(email_verified=False)),
            )
            extra_context = {
                **(extra_context or {}),
                "edually_user_summary": counts,
            }
        return super().changelist_view(request, extra_context=extra_context)
    # Phase 2A: EduAlly user management


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "student_id", "program", "year_level")
    search_fields = ("user__email", "student_id", "program")

    change_list_template = "admin/account/studentprofile/change_list.html"

    def get_urls(self):
        custom_urls = [
            path(
                "reset-year-levels/",
                self.admin_site.admin_view(self.reset_year_levels),
                name="account_studentprofile_reset_year_levels",
            ),
        ]
        return custom_urls + super().get_urls()

    def reset_year_levels(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied

        if request.method == "POST":
            updated = StudentProfile.objects.exclude(
                year_level=""
            ).update(year_level="")

            self.message_user(
                request,
                f"Year levels reset for {updated} student profiles.",
                level=messages.SUCCESS,
            )

            return HttpResponseRedirect(
                reverse("admin:account_studentprofile_changelist")
            )

        context = {
            **self.admin_site.each_context(request),
            "title": "Confirm Year Level Reset",
            "opts": self.model._meta,
            "affected_count": StudentProfile.objects.exclude(
                year_level=""
            ).count(),
        }

        return TemplateResponse(
            request,
            "admin/account/studentprofile/reset_year_levels.html",
            context,
        )


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
