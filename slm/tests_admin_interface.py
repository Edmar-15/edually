"""Phase 2E: Learning Content Django Admin regression tests."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from slm.models import Subject, Module, PersonalMaterial, HighlightAnswer, HighlightAnnotation

User = get_user_model()


class LearningContentAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="slm-admin@example.com", password="StrongPass123!", email_verified=True,
        )
        self.owner = User.objects.create_user(
            email="slm-owner@example.com", password="StrongPass123!", email_verified=True,
        )
        self.subject = Subject.objects.create(
            subject_code="CSC101", subject_name="Programming Basics",
            author=self.owner, year=Subject.YEAR_TWO,
        )
        self.module = Module.objects.create(
            subject=self.subject, module_number=1, module_name="Intro",
            file="modules/intro.pdf", extracted_html="<p>Intro</p>",
        )
        self.material = PersonalMaterial.objects.create(
            title="My Notes", author=self.owner, file="users/notes.pdf",
            visibility=PersonalMaterial.Visibility.PRIVATE,
        )
        self.answer = HighlightAnswer.objects.create(
            owner=self.owner, module=self.module, query="example",
            answer_simplified="A simple explanation",
        )
        self.annotation = HighlightAnnotation.objects.create(
            owner=self.owner, module=self.module, query="example", note="Review this",
        )
        self.client.force_login(self.admin)

    def url(self, model):
        return reverse(f"admin:slm_{model}_changelist")

    def test_subject_overview_search_and_module_count(self):
        response = self.client.get(self.url("subject"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/slm/change_list.html")
        self.assertContains(response, "Learning subjects")
        stats = response.context["edually_slm_overview"]["stats"]
        self.assertEqual([item["value"] for item in stats], [1, 1, 0, 1])
        self.assertContains(response, "CSC101")
        self.assertContains(response, "Programming Basics")
        self.assertEqual(response.context["cl"].result_list[0]._edually_module_total, 1)
        response = self.client.get(self.url("subject"), {"q": "CSC101"})
        self.assertEqual(response.context["cl"].result_count, 1)
        self.assertEqual(len(self.client.get(reverse("admin:slm_subject_change", args=[self.subject.pk])).context["inline_admin_formsets"]), 1)

    def test_module_overview_and_extraction_badges(self):
        response = self.client.get(self.url("module"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([s["value"] for s in response.context["edually_slm_overview"]["stats"]], [1, 1, 0, 1])
        self.assertContains(response, "Ready")
        self.assertContains(response, "Intro")
        self.module.is_archived = True
        self.module.extracted_html = ""
        self.module.save(update_fields=["is_archived", "extracted_html"])
        response = self.client.get(self.url("module"))
        self.assertContains(response, "Not available")
        self.assertContains(response, "Archived")
        self.assertEqual([s["value"] for s in response.context["edually_slm_overview"]["stats"]], [1, 0, 1, 0])

    def test_personal_material_visibility_and_stats(self):
        response = self.client.get(self.url("personalmaterial"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Private")
        self.assertEqual([s["value"] for s in response.context["edually_slm_overview"]["stats"]], [1, 1, 0, 0])
        self.material.visibility = PersonalMaterial.Visibility.PUBLIC
        self.material.save(update_fields=["visibility"])
        response = self.client.get(self.url("personalmaterial"))
        self.assertContains(response, "Public")
        self.assertEqual([s["value"] for s in response.context["edually_slm_overview"]["stats"]], [1, 0, 1, 0])

    def test_highlight_answers_and_annotations_remain_accessible(self):
        for model in ("highlightanswer", "highlightannotation"):
            with self.subTest(model=model):
                response = self.client.get(self.url(model))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "admin/slm/change_list.html")
                self.assertEqual([s["value"] for s in response.context["edually_slm_overview"]["stats"]], [1, 1, 0])
                self.assertContains(response, "example")

    def test_module_editor_preserves_html_and_original_upload(self):
        url = reverse("admin:slm_module_change", args=[self.module.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/slm/change_form.html")
        field = response.context["adminform"].form.fields["extracted_html"]
        self.assertEqual(field.widget.attrs["class"], "edually-extracted-html-editor")
        self.assertContains(response, "does not update the original uploaded file")
        response = self.client.post(url, {
            "subject": str(self.subject.pk), "module_number": "1", "module_name": "Intro",
            "extracted_html": "<h2>Revised</h2>", "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        self.module.refresh_from_db()
        self.assertEqual(self.module.extracted_html, "<h2>Revised</h2>")
        self.assertEqual(self.module.file.name, "modules/intro.pdf")

    def test_personal_material_editor_and_archive_field(self):
        url = reverse("admin:slm_personalmaterial_change", args=[self.material.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/slm/change_form.html")
        self.assertEqual(response.context["adminform"].form.fields["extracted_html"].widget.attrs["class"], "edually-extracted-html-editor")
        self.assertIn("is_archived", response.context["adminform"].form.fields)

    def test_staff_without_slm_permissions_cannot_change_records(self):
        staff = User.objects.create_user(
            email="slm-staff@example.com", password="StrongPass123!",
            is_staff=True, email_verified=True,
        )
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.url("subject")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:slm_module_change", args=[self.module.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:slm_personalmaterial_change", args=[self.material.pk])).status_code, 403)
