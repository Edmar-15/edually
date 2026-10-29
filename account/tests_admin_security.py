"""Security regression tests for EduAlly's admin-only permission boundaries."""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse

User = get_user_model()


class AdminPermissionSecurityTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            email="security-super@example.com", password="StrongPass123!",
            email_verified=True,
        )
        self.staff = User.objects.create_user(
            email="security-staff@example.com", password="StrongPass123!",
            email_verified=True, is_staff=True,
        )
        self.other_staff = User.objects.create_user(
            email="security-staff2@example.com", password="StrongPass123!",
            email_verified=True, is_staff=True,
        )
        self.student = User.objects.create_user(
            email="security-student@example.com", password="StrongPass123!",
            email_verified=False,
        )
        self.privileged_group = Group.objects.create(name="Privileged Test Group")
        permissions = Permission.objects.filter(
            content_type__app_label="account",
            content_type__model="user",
            codename__in=("view_user", "change_user", "add_user", "delete_user"),
        )
        self.staff.user_permissions.add(*permissions)
        # Give staff group management permission, too, to verify its lockdown.
        group_permissions = Permission.objects.filter(
            content_type__app_label="auth",
            content_type__model="group",
            codename__in=("view_group", "change_group", "add_group", "delete_group"),
        )
        self.staff.user_permissions.add(*group_permissions)
        self.user_list = reverse("admin:account_user_changelist")
        self.user_add = reverse("admin:account_user_add")

    def test_staff_can_manage_regular_users_but_not_privilege_fields(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.user_list).status_code, 200)
        change_url = reverse("admin:account_user_change", args=[self.student.pk])
        response = self.client.get(change_url)
        self.assertEqual(response.status_code, 200)
        fields = response.context["adminform"].form.fields
        for field in ("is_staff", "is_superuser", "groups", "user_permissions"):
            with self.subTest(field=field):
                self.assertNotIn(field, fields)
        self.assertIn("is_active", fields)
        response = self.client.get(self.user_add)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("is_staff", response.context["adminform"].form.fields)
        self.assertIn("email", response.context["adminform"].form.fields)

    def test_forged_edit_still_only_updates_regular_fields(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("admin:account_user_change", args=[self.student.pk]),
            {
                "email": self.student.email,
                "username": "updated-standard-user",
                "first_name": "Updated",
                "last_name": "Student",
                "is_active": "on",
                "email_verified": "on",
                # Django Admin's AdminSplitDateTime widget uses two input names.
                "date_joined_0": self.student.date_joined.strftime("%Y-%m-%d"),
                "date_joined_1": self.student.date_joined.strftime("%H:%M:%S"),
                "is_staff": "on",       # forged privileged fields
                "is_superuser": "on",
                "groups": [str(self.privileged_group.pk)],
                "user_permissions": [str(p.pk) for p in Permission.objects.filter(
                    content_type__app_label="account", codename="change_user"
                )],
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.student.refresh_from_db()
        self.assertEqual(self.student.first_name, "Updated")
        self.assertFalse(self.student.is_staff)
        self.assertFalse(self.student.is_superuser)
        self.assertFalse(self.student.groups.exists())
        self.assertFalse(self.student.user_permissions.exists())

    def test_forged_add_cannot_create_a_staff_or_superuser_account(self):
        self.client.force_login(self.staff)
        response = self.client.post(self.user_add, {
            "email": "new-standard@example.com",
            "username": "new-standard",
            "password1": "NewStrongPass123!",
            "password2": "NewStrongPass123!",
            "is_active": "on",
            "is_staff": "on",  # forged
            "is_superuser": "on",
            "groups": [str(self.privileged_group.pk)],
            "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        created = User.objects.get(email="new-standard@example.com")
        self.assertFalse(created.is_staff)
        self.assertFalse(created.is_superuser)
        self.assertFalse(created.groups.exists())
        self.assertTrue(created.check_password("NewStrongPass123!"))

    def test_staff_cannot_edit_privileged_accounts_or_reset_passwords(self):
        self.client.force_login(self.staff)
        for target in (self.staff, self.other_staff, self.superuser):
            with self.subTest(target=target.email):
                url = reverse("admin:account_user_change", args=[target.pk])
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url, {"first_name": "Hijacked"}).status_code, 403)
                password_url = reverse("admin:auth_user_password_change", args=[target.pk])
                self.assertEqual(self.client.get(password_url).status_code, 403)

    def test_staff_cannot_delete_privileged_accounts_even_by_bulk_action(self):
        self.client.force_login(self.staff)
        for target in (self.other_staff, self.superuser):
            with self.subTest(target=target.email):
                url = reverse("admin:account_user_delete", args=[target.pk])
                self.assertEqual(self.client.get(url).status_code, 403)
        request = RequestFactory().post(self.user_list)
        request.user = self.staff
        user_admin = admin.site._registry[User]
        with self.assertRaises(PermissionDenied):
            user_admin.delete_queryset(
                request,
                User.objects.filter(pk__in=[self.student.pk, self.superuser.pk]),
            )
        self.assertTrue(User.objects.filter(pk=self.student.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.superuser.pk).exists())

    def test_non_superusers_cannot_change_groups_even_with_permissions(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("admin:auth_group_changelist")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:auth_group_add")).status_code, 403)
        url = reverse("admin:auth_group_change", args=[self.privileged_group.pk])
        self.assertEqual(self.client.post(url, {"name": "Hijacked"}).status_code, 403)
        self.privileged_group.refresh_from_db()
        self.assertEqual(self.privileged_group.name, "Privileged Test Group")

    def test_superuser_retains_existing_user_and_group_controls(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:account_user_change", args=[self.staff.pk]))
        self.assertEqual(response.status_code, 200)
        fields = response.context["adminform"].form.fields
        for field in ("is_staff", "is_superuser", "groups", "user_permissions"):
            self.assertIn(field, fields)
        response = self.client.get(self.user_add)
        self.assertEqual(response.status_code, 200)
        self.assertIn("is_staff", response.context["adminform"].form.fields)
        self.assertEqual(self.client.get(reverse("admin:auth_group_changelist")).status_code, 200)
