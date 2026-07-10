from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from account.models import User, UserConsent
from .models import HighlightAnswer, Module, Subject


class ModuleHighlightApiTests(TestCase):
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
        self.module = Module.objects.create(
            subject=self.subject,
            module_number=1,
            module_name="Intro",
            file=SimpleUploadedFile("module.pdf", b"pdf", content_type="application/pdf"),
        )

    def test_api_returns_only_highlights_for_current_module(self):
        other_subject = Subject.objects.create(
            subject_code="GEC102",
            subject_name="Other Subject",
            author=self.user,
        )
        other_module = Module.objects.create(
            subject=other_subject,
            module_number=1,
            module_name="Other Module",
            file=SimpleUploadedFile("other.pdf", b"pdf", content_type="application/pdf"),
        )
        HighlightAnswer.objects.create(
            module=self.module,
            owner=self.user,
            query="alpha",
            answer_simplified="Alpha answer",
        )
        HighlightAnswer.objects.create(
            module=other_module,
            owner=self.user,
            query="beta",
            answer_simplified="Beta answer",
        )

        response = self.client.get(reverse("slm:module-highlight", args=[self.module.id]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["answers"]), 1)
        self.assertEqual(payload["answers"][0]["query"], "alpha")
