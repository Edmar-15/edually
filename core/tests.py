from django.test import Client, RequestFactory, TestCase, override_settings

from . import views


class CustomErrorPageTests(TestCase):
	@override_settings(DEBUG=False)
	def test_unknown_url_uses_custom_404_page(self):
		response = self.client.get("/this-page-does-not-exist/")

		self.assertEqual(response.status_code, 404)
		self.assertContains(response, "Page not found", status_code=404)

	@override_settings(DEBUG=False)
	def test_csrf_rejection_uses_custom_403_page(self):
		client = Client(enforce_csrf_checks=True)

		response = client.post("/account/login/")

		self.assertEqual(response.status_code, 403)
		self.assertContains(response, "Request blocked", status_code=403)

	@override_settings(DEBUG=False)
	def test_standard_error_handlers_render_their_status_pages(self):
		request = RequestFactory().get("/")
		handlers = (
			(views.bad_request, 400, Exception()),
			(views.forbidden, 403, Exception()),
			(views.page_not_found, 404, Exception()),
			(views.server_error, 500, None),
		)

		for handler, status_code, exception in handlers:
			with self.subTest(status_code=status_code):
				if exception is None:
					response = handler(request)
				else:
					response = handler(request, exception)
				self.assertEqual(response.status_code, status_code)
