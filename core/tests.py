"""Core routes, PWA assets, and error page tests."""
import json

from django.conf import settings
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from . import views


class CoreTests(TestCase):
    def test_manifest_is_served_as_json(self):
        response = self.client.get(reverse("manifest"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/manifest+json", response["Content-Type"])
        manifest = json.loads(response.content)
        self.assertEqual(manifest["short_name"], "EduAlly")
        self.assertTrue(manifest["icons"])

    def test_service_worker_serves_versioned_javascript(self):
        response = self.client.get(reverse("service-worker"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/javascript", response["Content-Type"])
        body = response.content.decode()
        self.assertIn(settings.PWA_SW_VERSION, body)
        self.assertNotIn("{{ PWA_SW_VERSION }}", body)
        self.assertIn("self.addEventListener", body)

    def test_offline_page(self):
        response = self.client.get(reverse("offline"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "offline.html")

    def test_robots_txt(self):
        response = self.client.get(reverse("robots"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response["Content-Type"])
        self.assertContains(response, "Disallow: /admin/")

    @override_settings(DEBUG=False)
    def test_unknown_url_uses_custom_404(self):
        response = self.client.get("/definitely-not-an-edually-route/")
        self.assertContains(response, "Page not found", status_code=404)

    def test_custom_error_handlers(self):
        request = RequestFactory().get("/")
        cases = (
            (views.bad_request, 400),
            (views.forbidden, 403),
            (views.page_not_found, 404),
        )
        for handler, status in cases:
            with self.subTest(status=status):
                response = handler(request, Exception("test"))
                self.assertEqual(response.status_code, status)
        response = views.server_error(request)
        self.assertEqual(response.status_code, 500)

    def test_csrf_failure_handler(self):
        response = views.csrf_failure(RequestFactory().post("/"), reason="test")
        self.assertContains(response, "Request blocked", status_code=403)