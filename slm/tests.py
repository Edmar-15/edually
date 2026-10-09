"""SLM subject, module, material and annotation API tests."""
import json
import tempfile
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from account.models import StudentProfile, UserConsent
from .models import (
    HighlightAnnotation, Module, PersonalMaterial, RecentModuleView, Subject
)
from .views import validate_module_file


class SLMTests(TestCase):
    def setUp(self):
        User = get_user_model()
        teacher_group, _ = Group.objects.get_or_create(name="Teacher")
        student_group, _ = Group.objects.get_or_create(name="Student")
        self.teacher = User.objects.create_user(
            email="teacher@example.com", username="teacher",
            password="StrongPass123!", email_verified=True,
        )
        self.student = User.objects.create_user(
            email="learner@example.com", username="learner",
            password="StrongPass123!", email_verified=True,
        )
        self.teacher.groups.add(teacher_group)
        self.student.groups.add(student_group)
        StudentProfile.objects.create(user=self.student, year_level="2nd Year")
        for user in (self.teacher, self.student):
            UserConsent.objects.create(user=user, version=settings.POLICY_VERSION)
        self.subject = Subject.objects.create(
            subject_code="GEC101", subject_name="General Education",
            author=self.teacher, year="2",
        )
        self.module = Module.objects.create(
            subject=self.subject, module_number=1, module_name="Introduction",
            file="modules/example.pdf", extracted_html="Introduction to the lesson",
        )
        self.temp_media = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_media.cleanup)
        self.media_override = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.client.force_login(self.teacher)

    @staticmethod
    def json_data(obj):
        return json.dumps(obj)

    def test_anonymous_subject_api_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("slm:subject-list"))
        self.assertEqual(response.status_code, 302)

    def test_teacher_lists_own_subjects(self):
        response = self.client.get(reverse("slm:subject-list"))
        self.assertEqual(response.status_code, 200)
        codes = [item["subject_code"] for item in response.json()["results"]]
        self.assertIn("GEC101", codes)

    def test_student_only_sees_matching_year(self):
        Subject.objects.create(
            subject_code="GEC301", subject_name="Advanced", author=self.teacher, year="3"
        )
        self.client.force_login(self.student)
        response = self.client.get(reverse("slm:subject-list"))
        self.assertEqual(response.status_code, 200)
        codes = {item["subject_code"] for item in response.json()["results"]}
        self.assertIn("GEC101", codes)
        self.assertNotIn("GEC301", codes)

    def test_student_cannot_create_subject(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("slm:subject-create"),
            data=self.json_data({"subject_code": "NO1", "subject_name": "No", "year": "2"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Subject.objects.filter(subject_code="NO1").exists())

    @patch("slm.views.notify_students_for_subject")
    def test_teacher_can_create_subject(self, notify):
        response = self.client.post(
            reverse("slm:subject-create"),
            data=self.json_data({"subject_code": "GEC102", "subject_name": "Science", "year": "2"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Subject.objects.filter(subject_code="GEC102", author=self.teacher).exists())
        notify.assert_called_once()

    def test_subject_create_rejects_invalid_year(self):
        response = self.client.post(
            reverse("slm:subject-create"),
            data=self.json_data({"subject_code": "GEC103", "subject_name": "Science", "year": "9"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_module_list(self):
        response = self.client.get(reverse("slm:module-list", args=[self.subject.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 1)

    def test_module_detail_records_recent_visit(self):
        response = self.client.get(
            reverse("slm:module-detail", args=[self.subject.pk, self.module.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            RecentModuleView.objects.filter(user=self.teacher, module=self.module).exists()
        )

    def test_file_type_validation(self):
        allowed = SimpleUploadedFile("notes.pdf", b"fake PDF content")
        self.assertTrue(validate_module_file(allowed))
        forbidden = SimpleUploadedFile("notes.exe", b"not allowed")
        with self.assertRaises(ValidationError):
            validate_module_file(forbidden)

    @patch("slm.views.extract_content", return_value="<p>Lesson</p>")
    @patch("slm.views.notify_students_for_subject")
    def test_teacher_uploads_module(self, notify, extract):
        url = reverse("slm:module-create", args=[self.subject.pk])
        response = self.client.post(url, {
            "module_number": "2", "module_name": "Second module",
            "file": SimpleUploadedFile("second.pdf", b"%PDF-test", content_type="application/pdf"),
        })
        self.assertEqual(response.status_code, 201)
        module = Module.objects.get(subject=self.subject, module_number=2)
        self.assertEqual(module.extracted_html, "<p>Lesson</p>")
        extract.assert_called_once()

    def test_private_material_is_not_visible_to_another_user(self):
        material = PersonalMaterial.objects.create(
            author=self.teacher, title="Private notes", file="personal/notes.pdf",
            visibility=PersonalMaterial.Visibility.PRIVATE,
        )
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("slm:personalmaterial-detail", args=[material.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_public_material_can_be_opened_by_other_user(self):
        material = PersonalMaterial.objects.create(
            author=self.teacher, title="Public notes", file="personal/notes.pdf",
            visibility=PersonalMaterial.Visibility.PUBLIC,
        )
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("slm:personalmaterial-detail", args=[material.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_annotations_are_created_and_listed_per_user(self):
        url = reverse("slm:module-annotation", args=[self.module.pk])
        data = {"query": "Introduction", "note": "Review later", "start_offset": 0, "end_offset": 12}
        response = self.client.post(
            url, self.json_data(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            HighlightAnnotation.objects.filter(owner=self.teacher, module=self.module).exists()
        )
        listing = self.client.get(url)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.json()["annotations"]), 1)
        self.client.force_login(self.student)
        other_listing = self.client.get(url)
        self.assertEqual(other_listing.status_code, 200)
        self.assertEqual(other_listing.json()["annotations"], [])

    def test_annotation_rejects_bad_offsets(self):
        url = reverse("slm:module-annotation", args=[self.module.pk])
        response = self.client.post(
            url,
            self.json_data({"query": "Intro", "note": "Bad", "start_offset": 5, "end_offset": 1}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)