"""Regression coverage for EduAlly Phase 2C group administration."""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse

User = get_user_model()


class AdminGroupInterfaceTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            email="group-admin@example.com", password="StrongPass123!", email_verified=True,
        )
        self.staff = User.objects.create_user(
            email="group-staff@example.com", password="StrongPass123!",
            is_staff=True, email_verified=True,
        )
        self.student = User.objects.create_user(
            email="group-student@example.com", password="StrongPass123!", email_verified=True,
        )
        self.students = Group.objects.create(name="Student")
        self.teachers = Group.objects.create(name="Teacher")
        self.student.groups.add(self.students)
        self.permission = Permission.objects.get(
            content_type__app_label="account", content_type__model="user", codename="view_user",
        )
        self.teachers.permissions.add(self.permission)
        self.list_url = reverse("admin:auth_group_changelist")

    def test_group_dashboard_shows_real_counts_and_permission_status(self):
        self.client.force_login(self.superuser)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/auth/group/change_list.html")
        self.assertEqual(response.context["edually_group_summary"], {
            "total": 2, "with_members": 1, "with_permissions": 1,
            "without_permissions": 1,
        })
        self.assertContains(response, "Roles &amp; permissions")
        self.assertContains(response, "No group permissions")
        self.assertContains(response, "Permissions assigned")
        self.assertContains(response, "Student")
        self.assertContains(response, "Teacher")

    def test_group_search_and_permission_filters(self):
        self.client.force_login(self.superuser)
        response = self.client.get(self.list_url, {"q": "Student"})
        self.assertEqual(response.context["cl"].result_count, 1)
        response = self.client.get(self.list_url, {"permission_status": "assigned"})
        self.assertEqual(response.context["cl"].result_count, 1)
        self.assertContains(response, "Teacher")
        response = self.client.get(self.list_url, {"permission_status": "none"})
        self.assertEqual(response.context["cl"].result_count, 1)
        self.assertContains(response, "Student")

    def test_member_and_permission_counts_are_distinct(self):
        second_student = User.objects.create_user(
            email="group-student2@example.com", password="StrongPass123!", email_verified=True,
        )
        second_student.groups.add(self.students)
        extra_permission = Permission.objects.get(
            content_type__app_label="account", content_type__model="user", codename="change_user",
        )
        self.students.permissions.add(self.permission, extra_permission)
        self.client.force_login(self.superuser)
        response = self.client.get(self.list_url)
        self.assertEqual(response.context["edually_group_summary"]["with_members"], 1)
        self.assertEqual(response.context["edually_group_summary"]["with_permissions"], 2)
        group_rows = {group.name: group for group in response.context["cl"].result_list}
        self.assertEqual(group_rows["Student"]._edually_members, 2)
        self.assertEqual(group_rows["Student"]._edually_permissions, 2)

    def test_group_add_and_change_forms_keep_django_permission_selector(self):
        self.client.force_login(self.superuser)
        add_url = reverse("admin:auth_group_add")
        response = self.client.get(add_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/auth/group/change_form.html")
        self.assertContains(response, "Creating a new group")
        self.assertIn("permissions", response.context["adminform"].form.fields)
        response = self.client.post(add_url, {
            "name": "Moderators", "permissions": [str(self.permission.pk)], "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        moderator = Group.objects.get(name="Moderators")
        self.assertEqual(list(moderator.permissions.values_list("pk", flat=True)), [self.permission.pk])
        change_url = reverse("admin:auth_group_change", args=[moderator.pk])
        response = self.client.get(change_url)
        self.assertContains(response, "Editing group permissions")
        response = self.client.post(change_url, {"name": "Moderators", "permissions": [], "_save": "Save"})
        self.assertEqual(response.status_code, 302)
        moderator.refresh_from_db()
        self.assertFalse(moderator.permissions.exists())

    def test_system_role_names_are_readonly_but_permissions_can_be_changed(self):
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(reverse("admin:auth_group_change", args=[self.students.pk])).status_code, 200)
        response = self.client.get(reverse("admin:auth_group_change", args=[self.students.pk]))
        self.assertNotIn("name", response.context["adminform"].form.fields)
        response = self.client.post(
            reverse("admin:auth_group_change", args=[self.students.pk]),
            {"name": "Not Student", "permissions": [str(self.permission.pk)], "_save": "Save"},
        )
        self.assertEqual(response.status_code, 302)
        self.students.refresh_from_db()
        self.assertEqual(self.students.name, "Student")
        self.assertTrue(self.students.permissions.filter(pk=self.permission.pk).exists())

    def test_system_role_groups_cannot_be_deleted_individually_or_in_bulk(self):
        self.client.force_login(self.superuser)
        admin_group = Group.objects.create(name="Admin")
        for group in (self.students, self.teachers, admin_group):
            with self.subTest(group=group.name):
                delete_url = reverse("admin:auth_group_delete", args=[group.pk])
                self.assertEqual(self.client.get(delete_url).status_code, 403)
                self.assertEqual(self.client.post(delete_url, {"post": "yes"}).status_code, 403)
                self.assertTrue(Group.objects.filter(pk=group.pk).exists())

        ordinary = Group.objects.create(name="Moderators")
        model_admin = admin.site._registry[Group]
        request = RequestFactory().post(self.list_url)
        request.user = self.superuser
        self.assertTrue(model_admin.has_delete_permission(request, ordinary))
        self.assertFalse(model_admin.has_delete_permission(request, self.students))
        with self.assertRaises(PermissionDenied):
            model_admin.delete_queryset(
                request, Group.objects.filter(pk__in=(self.students.pk, ordinary.pk)),
            )
        self.assertTrue(Group.objects.filter(pk=self.students.pk).exists())
        self.assertTrue(Group.objects.filter(pk=ordinary.pk).exists())

    def test_non_superuser_cannot_view_or_modify_groups_even_with_auth_permissions(self):
        auth_group_perms = Permission.objects.filter(
            content_type__app_label="auth", content_type__model="group",
            codename__in=("add_group", "change_group", "view_group", "delete_group"),
        )
        self.staff.user_permissions.add(*auth_group_perms)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:auth_group_add")).status_code, 403)
        self.assertEqual(self.client.post(reverse("admin:auth_group_add"), {
            "name": "Forged", "permissions": [str(self.permission.pk)], "_save": "Save",
        }).status_code, 403)
        change_url = reverse("admin:auth_group_change", args=[self.students.pk])
        self.assertEqual(self.client.get(change_url).status_code, 403)
        self.assertEqual(self.client.post(change_url, {
            "name": "Hijacked", "permissions": [str(self.permission.pk)], "_save": "Save",
        }).status_code, 403)
        self.students.refresh_from_db()
        self.assertEqual(self.students.name, "Student")
        self.assertFalse(self.students.permissions.exists())
