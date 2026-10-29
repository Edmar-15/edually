"""Phase 2D: Forum Admin UI and report moderation regression tests."""
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from forum.models import Category, Post, Reply, Report

User = get_user_model()


class ForumAdminInterfaceTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            email="forum-admin@example.com", password="StrongPass123!", email_verified=True,
        )
        self.author = User.objects.create_user(
            email="forum-writer@example.com", password="StrongPass123!", username="writer",
            email_verified=True,
        )
        self.reporter = User.objects.create_user(
            email="forum-reporter@example.com", password="StrongPass123!", email_verified=True,
        )
        self.other_reporter = User.objects.create_user(
            email="forum-reporter2@example.com", password="StrongPass123!", email_verified=True,
        )
        self.category = Category.objects.create(name="Questions", slug="questions")
        self.post = Post.objects.create(
            author=self.author, category=self.category, title="How do modules work?",
            content="A discussion about modules.",
        )
        self.reply = Reply.objects.create(post=self.post, author=self.author, content="They contain learning material.")

    def test_category_overview_counts_only_visible_posts(self):
        Post.objects.create(
            author=self.author, category=self.category, title="Archived post", content="Archived", is_archived=True,
        )
        Post.objects.create(
            author=self.author, category=self.category, title="Deleted post", content="Deleted", is_deleted=True,
        )
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:forum_category_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/forum/change_list.html")
        self.assertEqual(response.context["edually_forum_overview"]["stats"], (("Total categories", 1), ("With visible posts", 1)))
        self.assertContains(response, "Forum categories")
        self.assertContains(response, "Questions")
        self.assertEqual(response.context["cl"].result_list[0]._edually_visible_posts, 1)

    def test_post_list_and_moderation_filters(self):
        Post.objects.create(
            author=self.author, category=self.category, title="Archived post", content="Archived", is_archived=True,
        )
        self.client.force_login(self.superuser)
        url = reverse("admin:forum_post_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Discussion posts")
        self.assertContains(response, "Archived")
        self.assertEqual(response.context["cl"].result_count, 2)
        self.assertEqual(dict(response.context["edually_forum_overview"]["stats"])["Visible"], 1)
        response = self.client.get(url, {"is_archived__exact": "1"})
        self.assertEqual(response.context["cl"].result_count, 1)
        response = self.client.get(url, {"q": "forum-writer@example.com"})
        self.assertEqual(response.context["cl"].result_count, 2)

    def test_reply_list_and_change_form_preserve_fields(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("admin:forum_reply_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Discussion replies")
        response = self.client.get(reverse("admin:forum_reply_change", args=[self.reply.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/forum/change_form.html")
        fields = response.context["adminform"].form.fields
        self.assertIn("content", fields)
        self.assertIn("is_deleted", fields)
        self.assertIn("is_best_answer", fields)
        self.assertNotIn("created_at", fields)

    def test_reports_are_registered_reviewable_and_cannot_be_created_or_deleted(self):
        report = Report.objects.create(
            reporter=self.reporter, content_type=Report.POST, post=self.post, reason="spam",
        )
        self.client.force_login(self.superuser)
        list_url = reverse("admin:forum_report_changelist")
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reported content")
        self.assertContains(response, "Pending")
        self.assertEqual(dict(response.context["edually_forum_overview"]["stats"])["Pending"], 1)
        response = self.client.get(reverse("admin:forum_report_change", args=[report.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "admin/forum/report/change_form.html")
        self.assertContains(response, "read-only")
        self.assertNotContains(response, 'name="is_resolved"')
        self.assertEqual(self.client.get(reverse("admin:forum_report_add")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:forum_report_delete", args=[report.pk])).status_code, 403)

    def test_dismiss_reports_resolves_all_for_content_and_leaves_post_visible(self):
        first = Report.objects.create(reporter=self.reporter, content_type=Report.POST, post=self.post, reason="spam")
        second = Report.objects.create(reporter=self.other_reporter, content_type=Report.POST, post=self.post, reason="other")
        extra_post = Post.objects.create(author=self.author, category=self.category, title="Other post", content="Other")
        untouched = Report.objects.create(
            reporter=self.reporter, content_type=Report.POST, post=extra_post, reason="spam",
        )
        self.client.force_login(self.superuser)
        response = self.client.post(reverse("admin:forum_report_changelist"), {
            "action": "dismiss_selected_reports", "_selected_action": [str(first.pk)],
            "index": "0",
        })
        self.assertEqual(response.status_code, 302)
        first.refresh_from_db()
        second.refresh_from_db()
        untouched.refresh_from_db()
        self.post.refresh_from_db()
        self.assertTrue(first.is_resolved)
        self.assertTrue(second.is_resolved)
        self.assertEqual(first.action_taken, "dismiss")
        self.assertEqual(second.action_taken, "dismiss")
        self.assertFalse(untouched.is_resolved)
        self.assertFalse(self.post.is_deleted)

    def test_report_admin_is_superuser_only_even_with_model_permissions(self):
        staff = User.objects.create_user(
            email="forum-staff@example.com", password="StrongPass123!", is_staff=True, email_verified=True,
        )
        staff.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="forum", content_type__model="report",
        ))
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse("admin:forum_report_changelist")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:forum_report_add")).status_code, 403)
        self.assertEqual(self.client.post(reverse("admin:forum_report_changelist"), {
            "action": "dismiss_selected_reports", "_selected_action": [str(self.post.pk)],
        }).status_code, 403)

    def test_existing_upvote_admin_pages_remain_accessible(self):
        self.client.force_login(self.superuser)
        for model in ("postupvote", "replyupvote"):
            with self.subTest(model=model):
                response = self.client.get(reverse(f"admin:forum_{model}_changelist"))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "admin/forum/change_list.html")
