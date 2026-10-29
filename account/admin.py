from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import Group
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.db.models import Count, Q
from django.utils.html import format_html
from .constants import GROUP_STUDENT, GROUP_TEACHER, GROUP_ADMIN
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

    # Phase 2A security: privilege changes are superuser-only.
    # Admin staff with account permissions may still manage *regular* users.
    # Guard the target as well as form fields: password reset and delete routes
    # also use these ModelAdmin permission hooks.
    def _protected_account(self, request, obj):
        return (
            obj is not None
            and not request.user.is_superuser
            and (obj.is_staff or obj.is_superuser)
        )

    def has_view_permission(self, request, obj=None):
        if self._protected_account(request, obj):
            return False
        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if self._protected_account(request, obj):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if self._protected_account(request, obj):
            return False
        return super().has_delete_permission(request, obj)

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if request.user.is_superuser:
            return fieldsets

        # Django builds its ModelForm from these fieldsets; a forged POST
        # containing any removed field cannot assign staff, superuser, groups,
        # or individual permissions. This also removes is_staff on Add User.
        privileged = {"is_staff", "is_superuser", "groups", "user_permissions"}
        safe_fieldsets = []
        for title, options in fieldsets:
            fields = tuple(field for field in options["fields"] if field not in privileged)
            if not fields:
                continue
            safe_options = {**options, "fields": fields}
            if title == "Account access":
                safe_options["description"] = (
                    "You may activate or deactivate standard accounts. "
                    "Only superusers can grant staff access or advanced permissions."
                )
            elif title == "Create a user account":
                safe_options["description"] = (
                    "Create a standard account. Only a superuser can later "
                    "grant staff access, groups, or elevated permissions."
                )
            safe_fieldsets.append((title, safe_options))
        return tuple(safe_fieldsets)

    def delete_queryset(self, request, queryset):
        # The built-in bulk delete action does not check permission per row.
        # Prevent a mixed selection from deleting even one privileged account.
        if not request.user.is_superuser and queryset.filter(
            Q(is_staff=True) | Q(is_superuser=True)
        ).exists():
            raise PermissionDenied("Only superusers may delete privileged accounts.")
        return super().delete_queryset(request, queryset)

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



# Role/group permissions affect the whole site, not just the Users form.
# Restrict Group administration too; otherwise staff granted auth.change_group
# could elevate their own permissions indirectly through a group they belong to.
# Phase 2C: clear, superuser-only roles and group permissions
class GroupPermissionAssignmentFilter(admin.SimpleListFilter):
    title = "Assigned permissions"
    parameter_name = "permission_status"

    def lookups(self, request, model_admin):
        return (("assigned", "With permissions"), ("none", "Without permissions"))

    def queryset(self, request, queryset):
        if self.value() == "assigned":
            return queryset.filter(permissions__isnull=False).distinct()
        if self.value() == "none":
            return queryset.filter(permissions__isnull=True)
        return queryset


class SuperuserOnlyGroupAdmin(BaseGroupAdmin):
    """Keep Django's group/permission behavior, while making roles easier to audit."""

    change_list_template = "admin/auth/group/change_list.html"
    change_form_template = "admin/auth/group/change_form.html"
    list_display = ("group_identity", "member_count", "permission_count", "permission_state")
    list_display_links = ("group_identity",)
    list_filter = (GroupPermissionAssignmentFilter,)
    search_fields = ("name",)
    search_help_text = "Search groups by name."
    ordering = ("name",)
    list_per_page = 25
    # Retain GroupAdmin's built-in filter_horizontal = ("permissions",).
    fieldsets = (
        ("Group details", {
            "fields": ("name",),
            "description": "Use a descriptive name so administrators can recognize the role. "
            "The built-in Student, Teacher, and Admin names are locked because EduAlly uses them for role checks.",
        }),
        ("Access permissions", {
            "fields": ("permissions",),
            "description": (
                "Permissions assigned here apply to every member of this group. "
                "Search the available permissions, select the ones needed, then save. "
                "Only superusers can modify this list."
            ),
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        # EduAlly's account routing checks these exact group names. Prevent
        # accidental renaming without restricting permission editing.
        if obj is not None and obj.name in {GROUP_STUDENT, GROUP_TEACHER, GROUP_ADMIN}:
            return (*fields, "name")
        return fields

    def has_module_permission(self, request):
        return request.user.is_superuser and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return request.user.is_superuser and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_change_permission(request, obj)

    # Protect built-in EduAlly role groups from deletion.
    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.name in {GROUP_STUDENT, GROUP_TEACHER, GROUP_ADMIN}:
            return False
        return request.user.is_superuser and super().has_delete_permission(request, obj)

    def delete_queryset(self, request, queryset):
        # Bulk delete bypasses per-object has_delete_permission checks.
        if queryset.filter(name__in=(GROUP_STUDENT, GROUP_TEACHER, GROUP_ADMIN)).exists():
            raise PermissionDenied('Built-in EduAlly role groups cannot be deleted.')
        return super().delete_queryset(request, queryset)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _edually_members=Count("user", distinct=True),
            _edually_permissions=Count("permissions", distinct=True),
        )

    @admin.display(description="Group / role", ordering="name")
    def group_identity(self, obj):
        return format_html('<span class="edually-group-primary">{}</span>', obj.name)

    @admin.display(description="Members", ordering="_edually_members")
    def member_count(self, obj):
        return obj._edually_members

    @admin.display(description="Permissions", ordering="_edually_permissions")
    def permission_count(self, obj):
        return obj._edually_permissions

    @admin.display(description="Permission status")
    def permission_state(self, obj):
        enabled = bool(obj._edually_permissions)
        return format_html(
            '<span class="edually-group-badge edually-group-badge--{}">{}</span>',
            "assigned" if enabled else "empty",
            "Permissions assigned" if enabled else "No group permissions",
        )

    def changelist_view(self, request, extra_context=None):
        if request.method == "GET" and self.has_view_or_change_permission(request):
            # Distinct protects counts against join multiplication from M2M rows.
            summary = self.model.objects.aggregate(
                total=Count("pk", distinct=True),
                with_members=Count("pk", filter=Q(user__isnull=False), distinct=True),
                with_permissions=Count("pk", filter=Q(permissions__isnull=False), distinct=True),
            )
            summary["without_permissions"] = summary["total"] - summary["with_permissions"]
            extra_context = {**(extra_context or {}), "edually_group_summary": summary}
        return super().changelist_view(request, extra_context=extra_context)


admin.site.unregister(Group)
admin.site.register(Group, SuperuserOnlyGroupAdmin)

# Phase 2B refinement: an explicit filter for students with no assigned year.
class StudentYearLevelFilter(admin.SimpleListFilter):
    title = "Year Level"
    parameter_name = "year_level"

    def lookups(self, request, model_admin):
        return [
            *StudentProfile.YEAR_CHOICES,
            ("__pending__", "Not assigned"),
        ]

    def queryset(self, request, queryset):
        selected = self.value()
        if selected == "__pending__":
            return queryset.filter(year_level="")
        if selected in {value for value, _ in StudentProfile.YEAR_CHOICES}:
            return queryset.filter(year_level=selected)
        return queryset


# Phase 2B: student and teacher profile admin
class ProfileAdminGuard:
    """Keep profile administration from bypassing UserAdmin privilege checks."""

    def _is_privileged_profile(self, request, obj):
        return (
            obj is not None
            and not request.user.is_superuser
            and (obj.user.is_staff or obj.user.is_superuser)
        )

    def has_view_permission(self, request, obj=None):
        return not self._is_privileged_profile(request, obj) and super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return not self._is_privileged_profile(request, obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return not self._is_privileged_profile(request, obj) and super().has_delete_permission(request, obj)

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related("user")
        if not request.user.is_superuser:
            queryset = queryset.filter(user__is_staff=False, user__is_superuser=False)
        return queryset

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # A forged user ID must not link a regular profile to a privileged account.
        if db_field.name == "user" and not request.user.is_superuser:
            kwargs["queryset"] = User.objects.filter(is_staff=False, is_superuser=False)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def delete_queryset(self, request, queryset):
        # Django's built-in bulk-delete action does not check each object.
        if not request.user.is_superuser and queryset.filter(
            Q(user__is_staff=True) | Q(user__is_superuser=True)
        ).exists():
            raise PermissionDenied("Only superusers may delete privileged profiles.")
        return super().delete_queryset(request, queryset)

    @admin.display(description="Account", ordering="user__email")
    def profile_identity(self, obj):
        name = " ".join(part for part in (obj.user.first_name, obj.user.last_name) if part).strip()
        subline = name or ("@" + obj.user.username if obj.user.username else "Name not provided")
        return format_html(
            '<span class="edually-profile-primary">{}</span>'
            '<span class="edually-profile-secondary">{}</span>',
            obj.user.email, subline,
        )

    @admin.display(description="Account status", ordering="user__is_active")
    def user_status(self, obj):
        return format_html(
            '<span class="edually-profile-badge edually-profile-badge--{}">{}</span>',
            "positive" if obj.user.is_active else "muted",
            "Active" if obj.user.is_active else "Inactive",
        )


@admin.register(StudentProfile)
class StudentProfileAdmin(ProfileAdminGuard, admin.ModelAdmin):
    list_display = (
        "profile_identity", "student_id_display", "program_display",
        "year_level_display", "user_status",
    )
    list_display_links = ("profile_identity",)
    search_fields = (
        "user__email", "user__username", "user__first_name", "user__last_name",
        "student_id", "program",
    )
    search_help_text = "Search by student name, email, username, student ID, or program."
    list_filter = (StudentYearLevelFilter, "user__is_active")
    ordering = ("user__email",)
    list_per_page = 25
    change_list_template = "admin/account/studentprofile/change_list.html"
    change_form_template = "admin/account/profile_change_form.html"
    fieldsets = (
        ("Linked account", {"fields": ("user",), "description": "Choose the account this student profile belongs to."}),
        ("Student details", {"fields": ("student_id", "program", "year_level")}),
    )

    @admin.display(description="Student ID", ordering="student_id")
    def student_id_display(self, obj):
        return obj.student_id or "Not set"

    @admin.display(description="Program / Course", ordering="program")
    def program_display(self, obj):
        return obj.program or "Not set"

    @admin.display(description="Year level", ordering="year_level")
    def year_level_display(self, obj):
        return format_html(
            '<span class="edually-profile-badge edually-profile-badge--{}">{}</span>',
            "positive" if obj.year_level else "pending",
            obj.year_level or "Not assigned",
        )

    def get_readonly_fields(self, request, obj=None):
        readonly = super().get_readonly_fields(request, obj)
        # StudentProfile.clean() already forbids changing an assigned year.
        # Make that constraint obvious in the form instead of showing a selector.
        return (*readonly, "year_level") if obj is not None and obj.year_level else readonly

    def changelist_view(self, request, extra_context=None):
        if request.method == "GET" and self.has_view_or_change_permission(request):
            counts = self.get_queryset(request).aggregate(
                total=Count("pk"),
                id_assigned=Count("pk", filter=~Q(student_id="")),
                year_assigned=Count("pk", filter=~Q(year_level="")),
                year_pending=Count("pk", filter=Q(year_level="")),
            )
            extra_context = {**(extra_context or {}), "edually_profile_summary": counts}
        return super().changelist_view(request, extra_context=extra_context)

    # Preserve existing custom route and superuser-only reset behavior.
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
class TeacherProfileAdmin(ProfileAdminGuard, admin.ModelAdmin):
    list_display = ("profile_identity", "employee_id_display", "department_display", "user_status")
    list_display_links = ("profile_identity",)
    search_fields = (
        "user__email", "user__username", "user__first_name", "user__last_name",
        "employee_id", "department",
    )
    search_help_text = "Search by teacher name, email, username, employee ID, or department."
    list_filter = ("user__is_active", "department")
    ordering = ("user__email",)
    list_per_page = 25
    change_list_template = "admin/account/teacherprofile/change_list.html"
    change_form_template = "admin/account/profile_change_form.html"
    fieldsets = (
        ("Linked account", {"fields": ("user",), "description": "Choose the account this teacher profile belongs to."}),
        ("Teacher details", {"fields": ("employee_id", "department")}),
    )

    @admin.display(description="Employee ID", ordering="employee_id")
    def employee_id_display(self, obj):
        return obj.employee_id or "Not set"

    @admin.display(description="Department", ordering="department")
    def department_display(self, obj):
        return obj.department or "Not set"

    def changelist_view(self, request, extra_context=None):
        if request.method == "GET" and self.has_view_or_change_permission(request):
            counts = self.get_queryset(request).aggregate(
                total=Count("pk"),
                id_assigned=Count("pk", filter=~Q(employee_id="")),
                department_assigned=Count("pk", filter=~Q(department="")),
                active=Count("pk", filter=Q(user__is_active=True)),
            )
            extra_context = {**(extra_context or {}), "edually_profile_summary": counts}
        return super().changelist_view(request, extra_context=extra_context)

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
