"""Current account smoke and workflow tests for EduAlly."""
from unittest.mock import patch

import pyotp
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import UserConsent

User = get_user_model()


class AccountTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="student@example.com",
            username="student",
            password="StrongPass123!",
            email_verified=True,
        )
        UserConsent.objects.create(
            user=self.user, version=settings.POLICY_VERSION
        )

    def test_password_is_hashed(self):
        self.assertNotEqual(self.user.password, "StrongPass123!")
        self.assertTrue(self.user.check_password("StrongPass123!"))

    def test_public_registration_page_loads(self):
        response = self.client.get(reverse("account:register"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "account/register.html")

    def test_login_page_loads(self):
        response = self.client.get(reverse("account:login"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "account/login.html")

    def test_dashboard_requires_authentication(self):
        response = self.client.get(reverse("account:dashboard"))
        self.assertRedirects(
            response,
            reverse("account:login") + "?next=" + reverse("account:dashboard"),
        )

    def test_dashboard_uses_current_sections(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("account:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard.html")
        self.assertContains(response, "Getting started")
        self.assertContains(response, "SLM Modules")
        self.assertContains(response, "Quick Access")

    def test_profile_page(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("account:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "account/profile.html")

    def test_terms_and_privacy_standalone_pages(self):
        for name, template in (
            ("terms", "account/terms.html"),
            ("privacy", "account/privacy.html"),
        ):
            with self.subTest(page=name):
                response = self.client.get(reverse("account:" + name))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template)
                self.assertEqual(
                    response.context["policy_version"], settings.POLICY_VERSION
                )

    def test_missing_consent_redirects_to_policy(self):
        UserConsent.objects.filter(user=self.user).delete()
        self.client.force_login(self.user)
        response = self.client.get(reverse("account:dashboard"))
        self.assertRedirects(response, reverse("account:consent_required"))

    def test_accepting_policy_creates_latest_consent(self):
        UserConsent.objects.filter(user=self.user).delete()
        self.client.force_login(self.user)
        response = self.client.post(reverse("account:consent_required"))
        self.assertRedirects(response, reverse("account:dashboard"))
        self.assertEqual(
            UserConsent.objects.get(user=self.user).version,
            settings.POLICY_VERSION,
        )

    def test_unverified_user_is_redirected(self):
        self.user.email_verified = False
        self.user.save(update_fields=["email_verified"])
        self.client.force_login(self.user)
        response = self.client.get(reverse("account:dashboard"))
        self.assertRedirects(
            response, reverse("account:email_verification_required")
        )

    def test_theme_api_validates_values(self):
        url = reverse("account:api_set_theme")
        bad = self.client.post(url, {"theme": "purple"})
        self.assertEqual(bad.status_code, 400)
        good = self.client.post(url, {"theme": "dark"})
        self.assertEqual(good.status_code, 200)
        self.assertEqual(good.json()["theme"], "dark")
        self.assertEqual(good.cookies["eduallyTheme"].value, "dark")

    def test_2fa_requires_email_code_and_authenticator(self):
        self.client.force_login(self.user)
        self.user.two_factor_secret = "JBSWY3DPEHPK3PXP"
        self.user.save(update_fields=["two_factor_secret"])
        otp = pyotp.TOTP(self.user.two_factor_secret).now()

        response = self.client.post(
            reverse("account:settings"),
            {"enable_2fa": "1", "otp_code": otp},
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertFalse(self.user.two_factor_enabled)

        with patch("account.views._get_2fa_email_otp", return_value="123456"):
            response = self.client.post(
                reverse("account:settings"),
                {"enable_2fa": "1", "otp_code": otp, "gmail_otp": "123456"},
            )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.two_factor_enabled)