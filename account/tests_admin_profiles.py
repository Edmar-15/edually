"""Phase 2B admin profile view, editing, and permission regression tests."""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse

from account.models import StudentProfile, TeacherProfile

User = get_user_model()


class AdminProfileInterfaceTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            email="profile-admin@example.com", password="StrongPass123!", email_verified=True,
        )
        self.student_user = User.objects.create_user(
            email="profile-student@example.com", password="StrongPass123!",
            first_name="Sample", last_name="Student", email_verified=True,
        )
        self.teacher_user = User.objects.create_user(
            email="profile-teacher@example.com", password="StrongPass123!",
            first_name="Sample", last_name="Teacher", email_verified=True,
        )
        self.student = StudentProfile.objects.create(
            user=self.student_user, student_id="S-23001",
            program="Information Technology", year_level="2nd Year",
        )
        self.teacher = TeacherProfile.objects.create(
            user=self.teacher_user, employee_id="T-100", department="CCS",
        )

    def test_student_list_and_search(self):
        self.client.force_login(self.superuser)
        url = reverse("admin:account_studentprofile_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/account/studentprofile/change_list.html")
        self.assertContains(response, "Student profiles")
        self.assertContains(response, "S-23001")
        self.assertContains(response, "2nd Year")
        self.assertEqual(response.context["edually_profile_summary"]["year_assigned"], 1)
        self.assertContains(response, "Reset Year Levels")
        response = self.client.get(url, {"q": "S-23001"})
        self.assertEqual(response.context["cl"].result_count, 1)

    def test_student_year_filter_includes_not_assigned(self):
        pending_user = User.objects.create_user(
            email="pending-year-ui@example.com",
            password="StrongPass123!",
            email_verified=True,
        )
        StudentProfile.objects.create(
            user=pending_user,
            student_id="S-PENDING-UI",
            year_level="",
        )
        self.client.force_login(self.superuser)
        url = reverse("admin:account_studentprofile_changelist")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Not assigned")
        self.assertEqual(response.context["cl"].result_count, 2)

        response = self.client.get(url, {"year_level": "__pending__"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["cl"].result_count, 1)
        self.assertContains(response, "S-PENDING-UI")
        self.assertNotContains(response, "S-23001")

        response = self.client.get(url, {"year_level": "2nd Year"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["cl"].result_count, 1)
        self.assertContains(response, "S-23001")
        self.assertNotContains(response, "S-PENDING-UI")

    def test_reset_links_and_confirmation_use_danger_styling(self):
        self.client.force_login(self.superuser)
        changelist = self.client.get(reverse("admin:account_studentprofile_changelist"))
        self.assertContains(changelist, "edually-profile-reset-danger")
        confirmation = self.client.get(
            reverse("admin:account_studentprofile_reset_year_levels")
        )
        self.assertEqual(confirmation.status_code, 200)
        self.assertContains(confirmation, "edually-profile-reset-confirm")

    def test_teacher_list_and_search(self):
        self.client.force_login(self.superuser)
        url = reverse("admin:account_teacherprofile_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/account/teacherprofile/change_list.html")
        self.assertContains(response, "Teacher profiles")
        self.assertContains(response, "T-100")
        self.assertEqual(response.context["edually_profile_summary"]["id_assigned"], 1)
        response = self.client.get(url, {"q": "CCS"})
        self.assertEqual(response.context["cl"].result_count, 1)

    def test_student_assigned_year_is_read_only(self):
        self.client.force_login(self.superuser)
        url = reverse("admin:account_studentprofile_change", args=[self.student.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/account/profile_change_form.html")
        self.assertNotIn("year_level", response.context["adminform"].form.fields)
        self.assertContains(response, "Once a year level is assigned")
        # Even a forged year-level change must not modify the locked value.
        response = self.client.post(url, {
            "user": str(self.student_user.pk), "student_id": "S-23002",
            "program": "Information Technology", "year_level": "3rd Year", "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        self.student.refresh_from_db()
        self.assertEqual(self.student.year_level, "2nd Year")
        self.assertEqual(self.student.student_id, "S-23002")

    def test_blank_year_is_editable_and_reset_requires_superuser(self):
        self.client.force_login(self.superuser)
        reset_url = reverse("admin:account_studentprofile_reset_year_levels")
        self.assertEqual(self.client.get(reset_url).status_code, 200)
        self.assertEqual(self.client.post(reset_url).status_code, 302)
        self.student.refresh_from_db()
        self.assertEqual(self.student.year_level, "")
        change_url = reverse("admin:account_studentprofile_change", args=[self.student.pk])
        response = self.client.get(change_url)
        self.assertIn("year_level", response.context["adminform"].form.fields)
        response = self.client.post(change_url, {
            "user": str(self.student_user.pk), "student_id": "S-23001",
            "program": "Information Technology", "year_level": "3rd Year", "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        self.student.refresh_from_db()
        self.assertEqual(self.student.year_level, "3rd Year")

    def test_teacher_profile_form_remains_editable(self):
        self.client.force_login(self.superuser)
        url = reverse("admin:account_teacherprofile_change", args=[self.teacher.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/account/profile_change_form.html")
        self.assertContains(response, "Editing a teacher profile record")
        response = self.client.post(url, {
            "user": str(self.teacher_user.pk), "employee_id": "T-101",
            "department": "ENG", "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        self.teacher.refresh_from_db()
        self.assertEqual((self.teacher.employee_id, self.teacher.department), ("T-101", "ENG"))

    def test_staff_cannot_reassign_profiles_to_privileged_account(self):
        staff = User.objects.create_user(
            email="profile-staff@example.com", password="StrongPass123!",
            email_verified=True, is_staff=True,
        )
        permissions = Permission.objects.filter(
            content_type__app_label="account",
            content_type__model__in=("studentprofile", "teacherprofile"),
            codename__in=("view_studentprofile", "change_studentprofile", "add_studentprofile",
                         "delete_studentprofile", "view_teacherprofile", "change_teacherprofile",
                         "add_teacherprofile", "delete_teacherprofile"),
        )
        staff.user_permissions.add(*permissions)
        protected_profile = TeacherProfile.objects.create(user=staff, employee_id="T-ADMIN")
        self.client.force_login(staff)
        for model_name in ("studentprofile", "teacherprofile"):
            url = reverse(f"admin:account_{model_name}_changelist")
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "T-ADMIN")
        self.assertEqual(
            self.client.get(reverse("admin:account_teacherprofile_change", args=[protected_profile.pk])).status_code,
            302,  # Django redirects when the filtered queryset hides a profile.
        )
        student_change = reverse("admin:account_studentprofile_change", args=[self.student.pk])
        response = self.client.post(student_change, {
            "user": str(staff.pk), "student_id": "MOVED", "program": "IT", "_save": "Save",
        })
        self.assertEqual(response.status_code, 200)  # Invalid linked account.
        self.student.refresh_from_db()
        self.assertEqual(self.student.user_id, self.student_user.pk)
        self.assertEqual(self.student.student_id, "S-23001")
        reset_url = reverse("admin:account_studentprofile_reset_year_levels")
        self.assertEqual(self.client.get(reset_url).status_code, 403)
        self.assertEqual(self.client.post(reset_url).status_code, 403)
        request = RequestFactory().post("/")
        request.user = staff
        with self.assertRaises(PermissionDenied):
            admin.site._registry[TeacherProfile].delete_queryset(
                request, TeacherProfile.objects.filter(pk__in=(self.teacher.pk, protected_profile.pk)),
            )
        self.assertTrue(TeacherProfile.objects.filter(pk=protected_profile.pk).exists())
