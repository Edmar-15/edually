"""Phase 2F: Login Security Django Admin regression tests."""
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, RequestFactory
from django.urls import reverse
from axes.admin import AccessAttemptAdmin, AccessLogAdmin, AccessFailureLogAdmin
from axes.models import AccessAttempt, AccessLog, AccessFailureLog, AccessAttemptExpiration

User = get_user_model()


class LoginSecurityAdminTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            email="axes-review-super@example.com", password="StrongPass123!", email_verified=True,
        )
        self.staff = User.objects.create_user(
            email="axes-review-staff@example.com", password="StrongPass123!",
            is_staff=True, email_verified=True,
        )
        self.attempt = AccessAttempt.objects.create(
            username="sample@example.com", ip_address="192.0.2.11", user_agent="Test browser",
            path_info="/account/login/", failures_since_start=settings.AXES_FAILURE_LIMIT,
        )
        self.client.force_login(self.superuser)

    def url(self, model):
        return reverse(f"admin:axes_{model}_changelist")

    def test_attempt_list_shows_overview_threshold_and_search(self):
        response = self.client.get(self.url("accessattempt"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/axes/change_list.html")
        stats = response.context["edually_security_overview"]["stats"]
        self.assertEqual([s["value"] for s in stats], [1, 1, 0, 1])
        self.assertContains(response, "At failure limit")
        self.assertContains(response, "sample@example.com")
        self.assertEqual(self.client.get(self.url("accessattempt"), {"q": "sample@example.com"}).context["cl"].result_count, 1)

    def test_attempt_expiration_column_and_no_expiration_fallback(self):
        model_admin = admin.site._registry[AccessAttempt]
        self.assertIsInstance(model_admin, AccessAttemptAdmin)
        request = RequestFactory().get(self.url("accessattempt"))
        request.user = self.superuser
        record = model_admin.get_queryset(request).get(pk=self.attempt.pk)
        self.assertEqual(model_admin.expires_on(record), "Not set")
        self.assertIn("expiration", model_admin.get_queryset(request).query.select_related)

    def test_access_log_and_failure_log_lists_render(self):
        AccessLog.objects.create(
            username="good@example.com", ip_address="192.0.2.12",
            user_agent="Test browser", path_info="/account/login/",
        )
        AccessFailureLog.objects.create(
            username="failed@example.com", ip_address="192.0.2.13",
            user_agent="Test browser", path_info="/account/login/", locked_out=True,
        )
        for model, heading, label in (
            ("accesslog", "Access history", "No logout recorded"),
            ("accessfailurelog", "Individual failure logs", "Lockout flagged"),
        ):
            with self.subTest(model=model):
                response = self.client.get(self.url(model))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "admin/axes/change_list.html")
                self.assertContains(response, heading)
                self.assertContains(response, label)
                # Axes may log the test client's force_login(), so AccessLog
                # can already contain a record before the explicit fixture.
                expected_model = AccessLog if model == "accesslog" else AccessFailureLog
                self.assertEqual(
                    response.context["edually_security_overview"]["stats"][0]["value"],
                    expected_model.objects.count(),
                )
                self.assertContains(
                    response,
                    "good@example.com" if model == "accesslog" else "failed@example.com",
                )

    def test_built_in_axes_cleanup_and_readonly_fields_are_preserved(self):
        for model, base in (
            (AccessAttempt, AccessAttemptAdmin),
            (AccessLog, AccessLogAdmin),
            (AccessFailureLog, AccessFailureLogAdmin),
        ):
            with self.subTest(model=model.__name__):
                instance = admin.site._registry[model]
                self.assertIsInstance(instance, base)
                self.assertFalse(instance.has_add_permission(RequestFactory().get("/")))
        self.assertIn("cleanup_expired_attempts", admin.site._registry[AccessAttempt].actions)
        self.assertIn("post_data", admin.site._registry[AccessAttempt].readonly_fields)

    def test_attempt_record_detail_remains_available(self):
        response = self.client.get(reverse("admin:axes_accessattempt_change", args=[self.attempt.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/axes/change_form.html")
        self.assertContains(response, "Authentication record details")

    def test_security_overview_respects_admin_view_permission(self):
        self.client.force_login(self.staff)
        for model in ("accessattempt", "accesslog", "accessfailurelog"):
            with self.subTest(model=model):
                self.assertEqual(self.client.get(self.url(model)).status_code, 403)

    def test_view_permission_does_not_grant_deletion(self):
        permission = Permission.objects.get(
            content_type__app_label="axes", content_type__model="accessattempt", codename="view_accessattempt",
        )
        self.staff.user_permissions.add(permission)
        self.client.force_login(self.staff)
        response = self.client.get(self.url("accessattempt"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Failed login attempts")
        request = RequestFactory().get(self.url("accessattempt"))
        request.user = self.staff
        self.assertFalse(admin.site._registry[AccessAttempt].has_delete_permission(request))
