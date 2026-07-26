from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .forms import LoginForm
from .models import User, UserConsent
from slm.models import Module, Subject


class LoginFormTests(TestCase):
    def test_login_username_field_uses_email_input(self):
        form = LoginForm()

        self.assertIsInstance(form.fields["username"].widget, forms.EmailInput)


class UserBadgeTests(TestCase):
    def test_forum_badge_labels_by_karma_thresholds(self):
        beginner = User.objects.create_user(
            email="beginner@example.com",
            password="secret123",
            username="beginner",
            karma=0,
        )
        helpful = User.objects.create_user(
            email="helpful@example.com",
            password="secret123",
            username="helpful",
            karma=20,
        )
        expert = User.objects.create_user(
            email="expert@example.com",
            password="secret123",
            username="expert",
            karma=100,
        )

        self.assertEqual(beginner.forum_badge_label, "Beginner")
        self.assertEqual(helpful.forum_badge_label, "Helpful")
        self.assertEqual(expert.forum_badge_label, "Expert")


class ContactPageTests(TestCase):
    def test_contact_page_is_available(self):
        response = self.client.get(reverse("account:contact"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Contact Us")
        self.assertContains(response, "Customer Service")


class LandingPageTests(TestCase):
    def test_landing_page_has_mobile_navigation_toggle(self):
        response = self.client.get(reverse("landing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "mobile-nav-toggle")
        self.assertContains(response, "aria-controls=\"main-nav\"")


class DashboardViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="student@example.com",
            password="secret123",
            username="student",
            first_name="Alex",
            last_name="Rivera",
        )
        self.client.force_login(self.user)
        UserConsent.objects.create(user=self.user, version="1.0")

    def test_dashboard_displays_real_learning_summary(self):
        subject = Subject.objects.create(
            subject_code="GEC101",
            subject_name="General Education",
            author=self.user,
        )
        Module.objects.create(
            subject=subject,
            module_number=1,
            module_name="Intro",
            file=SimpleUploadedFile("module.pdf", b"pdf", content_type="application/pdf"),
        )

        response = self.client.get(reverse("account:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your learning snapshot")
        self.assertContains(response, "1 module")
        self.assertContains(response, "Continue where you left off")

    def test_dashboard_shows_onboarding_checklist_for_new_users(self):
        response = self.client.get(reverse("account:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Set up your learning space")
        self.assertContains(response, "Complete your profile")
