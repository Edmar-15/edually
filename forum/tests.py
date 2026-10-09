"""Forum workflows on the current cleanup branch."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from account.models import UserConsent
from .models import Category, Post, PostUpvote, Reply, ReplyUpvote, Report

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


class ForumTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="writer@example.com", username="writer",
            password="StrongPass123!", email_verified=True,
        )
        self.other = User.objects.create_user(
            email="other@example.com", username="other",
            password="StrongPass123!", email_verified=True,
        )
        for user in (self.user, self.other):
            UserConsent.objects.create(user=user, version=settings.POLICY_VERSION)
        self.category = Category.objects.create(name="General", slug="general")
        self.post = Post.objects.create(
            author=self.user, category=self.category,
            title="Need help", content="Please explain this lesson.",
        )
        self.reply = Reply.objects.create(
            post=self.post, author=self.user, content="My original reply"
        )
        self.client.force_login(self.user)

    def test_guest_is_redirected_from_forum(self):
        self.client.logout()
        response = self.client.get(reverse("forum:list"))
        self.assertEqual(response.status_code, 302)

    def test_forum_and_detail_pages_render(self):
        listing = self.client.get(reverse("forum:list"))
        self.assertEqual(listing.status_code, 200)
        self.assertTemplateUsed(listing, "forum/list.html")
        detail = self.client.get(reverse("forum:post_detail", args=[self.post.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertTemplateUsed(detail, "forum/detail.html")

    def test_ajax_create_post(self):
        response = self.client.post(
            reverse("forum:create"),
            {"title": "New discussion", "content": "An interesting question", "category": self.category.pk},
            **AJAX,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertTrue(Post.objects.filter(title="New discussion", author=self.user).exists())

    def test_post_rejects_prohibited_language(self):
        response = self.client.post(
            reverse("forum:create"),
            {"title": "Bad post", "content": "You are gago", "category": self.category.pk},
            **AJAX,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["success"])
        self.assertFalse(Post.objects.filter(title="Bad post").exists())

    def test_ajax_create_reply_updates_count(self):
        response = self.client.post(
            reverse("forum:create_reply", args=[self.post.pk]),
            {"content": "Another helpful reply"}, **AJAX,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.post.refresh_from_db()
        self.assertEqual(self.post.reply_count, 2)

    def test_reply_edit_modal_and_submit(self):
        url = reverse("forum:reply_edit", args=[self.reply.pk])
        get_response = self.client.get(url, **AJAX)
        self.assertEqual(get_response.status_code, 200)
        self.assertIn("html", get_response.json())
        update = self.client.post(url, {"content": "Updated reply"}, **AJAX)
        self.assertEqual(update.status_code, 200)
        self.assertTrue(update.json()["success"])
        self.reply.refresh_from_db()
        self.assertEqual(self.reply.content, "Updated reply")

    def test_only_reply_author_can_edit_or_delete(self):
        self.client.force_login(self.other)
        for name in ("reply_edit", "reply_delete"):
            with self.subTest(name=name):
                response = self.client.get(reverse("forum:" + name, args=[self.reply.pk]), **AJAX)
                self.assertEqual(response.status_code, 404)

    def test_reply_delete_soft_deletes(self):
        url = reverse("forum:reply_delete", args=[self.reply.pk])
        preview = self.client.get(url, **AJAX)
        self.assertEqual(preview.status_code, 200)
        self.assertIn("html", preview.json())
        response = self.client.post(url, **AJAX)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.reply.refresh_from_db()
        self.assertTrue(self.reply.is_deleted)
        self.post.refresh_from_db()
        self.assertEqual(self.post.reply_count, 0)

    def test_post_upvote_toggles(self):
        url = reverse("forum:upvote", args=[self.post.pk])
        first = self.client.post(url, **AJAX)
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["has_upvoted"])
        self.assertEqual(PostUpvote.objects.count(), 1)
        second = self.client.post(url, **AJAX)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()["has_upvoted"])
        self.assertEqual(PostUpvote.objects.count(), 0)

    def test_reply_upvote_toggles(self):
        url = reverse("forum:reply_upvote", args=[self.reply.pk])
        self.assertTrue(self.client.post(url, **AJAX).json()["has_upvoted"])
        self.assertEqual(ReplyUpvote.objects.count(), 1)
        self.assertFalse(self.client.post(url, **AJAX).json()["has_upvoted"])

    def test_report_post(self):
        response = self.client.post(
            reverse("forum:flag_content", args=["post", self.post.pk]),
            {"reason": "spam", "description": "Repeated messages"}, **AJAX,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertTrue(Report.objects.filter(reporter=self.user, post=self.post).exists())

    def test_post_archive_hides_from_listing(self):
        response = self.client.post(
            reverse("forum:post_archive", args=[self.post.pk]), **AJAX
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.post.refresh_from_db()
        self.assertTrue(self.post.is_archived)

    def test_onboarding_marks_forum_visited(self):
        self.assertFalse(self.user.onboarding_forum_visited)
        self.client.get(reverse("forum:list"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.onboarding_forum_visited)