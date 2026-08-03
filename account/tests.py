import json
from unittest.mock import patch

from django import forms
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .forms import LoginForm
from .models import Announcement, PushSubscription, User, UserConsent
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


class SettingsPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="student@example.com",
            password="secret123",
            username="student",
        )
        self.client.force_login(self.user)
        UserConsent.objects.create(user=self.user, version="1.0")

    def test_settings_page_uses_switch_for_browser_notifications(self):
        response = self.client.get(reverse("account:settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="browser-notifications-toggle"')
        self.assertContains(response, 'class="switch"')
        self.assertNotContains(response, 'id="enable-push-toggle"')

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


class ServiceWorkerTests(TestCase):
    def test_service_worker_endpoint_serves_valid_javascript(self):
        response = self.client.get(reverse("service-worker"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/javascript")
        self.assertNotContains(response, "{{")
        self.assertContains(response, 'self.addEventListener("push"')


class RecentModuleDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="student@example.com",
            password="secret123",
            username="student",
        )
        self.client.force_login(self.user)
        UserConsent.objects.create(user=self.user, version="1.0")

        self.subject = Subject.objects.create(
            subject_code="GEC101",
            subject_name="General Education",
            author=self.user,
        )
        self.module_one = Module.objects.create(
            subject=self.subject,
            module_number=1,
            module_name="First Module",
            file=SimpleUploadedFile("module1.pdf", b"pdf1", content_type="application/pdf"),
        )
        self.module_two = Module.objects.create(
            subject=self.subject,
            module_number=2,
            module_name="Second Module",
            file=SimpleUploadedFile("module2.pdf", b"pdf2", content_type="application/pdf"),
        )

    def test_dashboard_shows_recently_visited_modules_by_most_recent_order(self):
        session = self.client.session
        session["recent_modules"] = [self.module_two.pk, self.module_one.pk]
        session.save()

        response = self.client.get(reverse("account:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recently visited modules")
        self.assertContains(response, "Second Module")
        self.assertContains(response, "First Module")

        page_html = response.content.decode()
        second_link = page_html.index(
            f'href="{reverse("slm:module-detail", kwargs={"subject_id": self.subject.pk, "module_id": self.module_two.pk})}"'
        )
        first_link = page_html.index(
            f'href="{reverse("slm:module-detail", kwargs={"subject_id": self.subject.pk, "module_id": self.module_one.pk})}"'
        )
        self.assertLess(second_link, first_link)

    def test_module_detail_records_recent_visit_in_session(self):
        response = self.client.get(
            reverse("slm:module-detail", kwargs={"subject_id": self.subject.pk, "module_id": self.module_one.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session.get("recent_modules", []), [self.module_one.pk])

    def test_recent_module_uses_file_type_icon(self):
        self.assertEqual(self.module_one.file_icon, "fas")
        self.assertEqual(self.module_one.file_icon_classes, "fas fa-file-pdf activity-icon--pdf")
        self.assertEqual(self.module_two.file_icon, "fas")
        self.assertEqual(self.module_two.file_icon_classes, "fas fa-file-pdf activity-icon--pdf")

    def test_dashboard_restores_recent_modules_from_cookie_when_session_is_empty(self):
        self.client.cookies["eduallyRecentModules"] = json.dumps([self.module_two.pk, self.module_one.pk])
        self.client.logout()
        self.client.force_login(self.user)

        response = self.client.get(reverse("account:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recently visited modules")
        self.assertContains(response, "Second Module")
        self.assertContains(response, "First Module")

        page_html = response.content.decode()
        second_link = page_html.index(
            f'href="{reverse("slm:module-detail", kwargs={"subject_id": self.subject.pk, "module_id": self.module_two.pk})}"'
        )
        first_link = page_html.index(
            f'href="{reverse("slm:module-detail", kwargs={"subject_id": self.subject.pk, "module_id": self.module_one.pk})}"'
        )
        self.assertLess(second_link, first_link)


class AnnouncementPushTests(TestCase):
    def setUp(self):
        self.teacher_group, _ = Group.objects.get_or_create(name="Teacher")
        self.teacher = User.objects.create_user(
            email="teacher@example.com",
            password="secret123",
            username="teacher",
            first_name="Teacher",
            last_name="User",
        )
        self.teacher.groups.add(self.teacher_group)
        self.client.force_login(self.teacher)
        UserConsent.objects.create(user=self.teacher, version="1.0")

        self.subscriber = User.objects.create_user(
            email="subscriber@example.com",
            password="secret123",
            username="subscriber",
        )
        PushSubscription.objects.create(
            user=self.subscriber,
            endpoint="https://example.com/endpoint",
            auth="auth-secret",
            p256dh="p256dh-secret",
        )

    @patch("account.views._send_announcement_push")
    def test_create_modal_dispatches_push_for_new_announcement(self, send_push):
        response = self.client.post(
            reverse("account:announcement_create_modal"),
            {"title": "System update", "content": "Maintenance starts tonight."},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Announcement.objects.filter(title="System update").exists())
        send_push.assert_called_once()

