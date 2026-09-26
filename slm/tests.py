import json
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from account.models import StudentProfile, User, UserConsent
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


class YearFilteredPushNotificationTests(TestCase):
    def setUp(self):
        teacher_group, _ = Group.objects.get_or_create(name="Teacher")
        student_group, _ = Group.objects.get_or_create(name="Student")

        self.teacher = User.objects.create_user(
            email="teacher@example.com",
            password="secret123",
            username="teacher",
            email_verified=True,
        )
        self.teacher.groups.add(teacher_group)
        UserConsent.objects.create(user=self.teacher, version="1.0")

        self.second_year_student = User.objects.create_user(
            email="second-year@example.com",
            password="secret123",
            username="second-year",
        )
        self.second_year_student.groups.add(student_group)
        StudentProfile.objects.create(
            user=self.second_year_student,
            year_level="2nd Year",
        )

        self.third_year_student = User.objects.create_user(
            email="third-year@example.com",
            password="secret123",
            username="third-year",
        )
        self.third_year_student.groups.add(student_group)
        StudentProfile.objects.create(
            user=self.third_year_student,
            year_level="3rd Year",
        )

        self.client.force_login(self.teacher)

    def assert_only_second_year_student_notified(self, mock_send):
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(mock_send.call_args.args[0], self.second_year_student)

    @patch("slm.views.send_push_notification")
    def test_subject_creation_notifies_only_students_in_subject_year(self, mock_send):
        response = self.client.post(
            reverse("slm:subject-create"),
            data=json.dumps({
                "subject_code": "GEC201",
                "subject_name": "Second Year Subject",
                "year": "2",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assert_only_second_year_student_notified(mock_send)

    @patch("slm.views.extract_content", return_value="<p>Module content</p>")
    @patch("slm.views.send_push_notification")
    def test_module_creation_notifies_only_students_in_subject_year(
        self,
        mock_send,
        _mock_extract_content,
    ):
        subject = Subject.objects.create(
            subject_code="GEC202",
            subject_name="Second Year Subject",
            author=self.teacher,
            year=Subject.YEAR_TWO,
        )

        response = self.client.post(
            reverse("slm:module-create", args=[subject.pk]),
            data={
                "module_number": "1",
                "module_name": "First Module",
                "file": SimpleUploadedFile(
                    "module.pdf",
                    b"pdf content",
                    content_type="application/pdf",
                ),
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assert_only_second_year_student_notified(mock_send)
