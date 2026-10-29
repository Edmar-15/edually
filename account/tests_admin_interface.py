"""Regression coverage for Phase 2A's admin-only user interface."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class AdminUserInterfaceTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            email="admin-ui@example.com", password="StrongPass123!",
            email_verified=True,
        )
        self.student_user = User.objects.create_user(
            email="student-ui@example.com", password="StrongPass123!",
            username="student-ui", first_name="Sample", last_name="Student",
            email_verified=False, is_active=True,
        )

    def test_user_management_has_summary_and_search(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("admin:account_user_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/account/user/change_list.html")
        self.assertEqual(response.context["edually_user_summary"]["total"], 2)
        self.assertEqual(response.context["edually_user_summary"]["not_verified"], 1)
        self.assertContains(response, "Account overview")
        self.assertContains(response, "student-ui@example.com")
        self.assertContains(response, "Not verified")
        self.assertContains(response, "Admin access")
        self.assertContains(response, "Not enabled")

    def test_user_management_search_filters_results(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("admin:account_user_changelist"), {"q": "student-ui"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["cl"].result_count, 1)

    def test_change_and_add_forms_keep_django_admin_workflow(self):
        self.client.force_login(self.admin_user)
        change_url = reverse("admin:account_user_change", args=[self.student_user.pk])
        response = self.client.get(change_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/account/user/change_form.html")
        self.assertContains(response, "Editing an account")
        self.assertContains(response, "Advanced permissions")

        response = self.client.get(reverse("admin:account_user_add"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Creating a new account")
        self.assertContains(response, 'name="password1"')

    def test_regular_user_cannot_view_admin_account_list(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse("admin:account_user_changelist"))
        self.assertNotEqual(response.status_code, 200)
