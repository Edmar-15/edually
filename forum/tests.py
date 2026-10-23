from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.test import SimpleTestCase
from .content_filter import check_content

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

    def test_filter_blocks_invalid_posts(self):
        invalid_inputs = [
            "fuck",
            "B0B0",
            "g@go",
            "f.u.c.k",
            "12467654!@@#$%^%#$sdfghgjhghfd",
        ]

        for index, content in enumerate(invalid_inputs):
            with self.subTest(content=content):
                title = f"Filter test {index}"

                response = self.client.post(
                    reverse("forum:create"),
                    {
                        "title": title,
                        "content": content,
                        "category": self.category.pk,
                    },
                    **AJAX,
                )

                self.assertFalse(response.json()["success"])
                self.assertFalse(
                    Post.objects.filter(title=title).exists()
                )

    def test_filter_blocks_invalid_replies(self):
        invalid_inputs = [
            "fuck",
            "B0B0",
            "g@go",
            "12467654!@@#$%^%#$sdfghgjhghfd",
        ]

        original_count = Reply.objects.count()

        for content in invalid_inputs:
            with self.subTest(content=content):
                response = self.client.post(
                    reverse(
                        "forum:create_reply",
                        args=[self.post.pk],
                    ),
                    {"content": content},
                    **AJAX,
                )

                self.assertFalse(response.json()["success"])
                self.assertEqual(
                    Reply.objects.count(),
                    original_count,
                )

    def test_filter_blocks_invalid_post_edits(self):
        url = reverse(
            "forum:post_edit",
            args=[self.post.pk],
        )

        response = self.client.post(
            url,
            {
                "title": "Updated title",
                "content": "g@go",
                "category": self.category.pk,
            },
            **AJAX,
        )

        self.post.refresh_from_db()

        self.assertEqual(
            self.post.content,
            "Please explain this lesson.",
        )
        self.assertIn("html", response.json())

    def test_filter_blocks_invalid_reply_edits(self):
        url = reverse(
            "forum:reply_edit",
            args=[self.reply.pk],
        )

        response = self.client.post(
            url,
            {"content": "f.u.c.k"},
            **AJAX,
        )

        self.reply.refresh_from_db()

        self.assertEqual(
            self.reply.content,
            "My original reply",
        )
        self.assertIn("html", response.json())

    def test_filter_allows_programming_content(self):
        response = self.client.post(
            reverse("forum:create"),
            {
                "title": "What is C++?",
                "content": (
                    '#include <iostream>\n'
                    'print("Hello, world!")'
                ),
                "category": self.category.pk,
            },
            **AJAX,
        )

        self.assertTrue(response.json()["success"])

    def test_create_post_requires_category(self):
        response = self.client.post(
            reverse("forum:create"),
            {
                "title": "Missing category discussion",
                "content": "This discussion has no category.",
            },
            **AJAX,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["success"])
        self.assertIn(
            "Please select a category.",
            response.json()["html"],
        )
        self.assertFalse(
            Post.objects.filter(
                title="Missing category discussion"
            ).exists()
        )

    def test_create_post_rejects_invalid_category(self):
        response = self.client.post(
            reverse("forum:create"),
            {
                "title": "Invalid category discussion",
                "content": "This category does not exist.",
                "category": "999999",
            },
            **AJAX,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["success"])
        self.assertIn(
            "Please select a valid category.",
            response.json()["html"],
        )
        self.assertFalse(
            Post.objects.filter(
                title="Invalid category discussion"
            ).exists()
        )

    def test_edit_post_requires_category(self):
        response = self.client.post(
            reverse("forum:post_edit", args=[self.post.pk]),
            {
                "title": "Updated discussion",
                "content": "Updated discussion content.",
                "category": "",
            },
            **AJAX,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json().get("success", False))

        self.post.refresh_from_db()
        self.assertEqual(self.post.category, self.category)
        self.assertEqual(self.post.title, "Need help")


class ContentFilterRegressionTests(SimpleTestCase):

    def test_blocks_profanity_and_spam(self):
        blocked_inputs = [
            "bobo",
            "fuck",
            "B0B0",
            "g@go",
            "f.u.c.k",
            "f u c k",
            "b o b o",
            "f-u-c-k",
            "12467654!@@#$%^%#$sdfghgjhghfd",
            "12345678!@@#$%^&*abcdefg",
            "hello 12345678!@@#$%^&*abcdefg world",
            "!!!!!!!!!!!!!!!!",
            "################",
        ]

        for text in blocked_inputs:
            with self.subTest(text=text):
                self.assertIsNotNone(
                    check_content(text),
                    msg=f"Should block: {text}",
                )

    def test_allows_legitimate_educational_content(self):
        allowed_inputs = [
            "What is C++?",
            "How do Python functions work?",
            "I hate cyberbullying.",
            "How do we reduce trash in our school?",
            "What is hate speech?",
            "What does uyab mean in Cebuano?",
            "How does the class handle errors?",
            "#include <iostream>",
            'print("Hello, world!")',
            "What does #include <iostream> do?",
            "C++ uses operators like !=, &&, and ||.",
            'print("ABC12345!!!@@@###xyz")',
            "https://example.com/lesson/12345?symbols=!@#$%^&abcde",
            "What does 12345 != 67890 mean?",
            "How do I use regex ^[A-Za-z0-9_!@#$%^&*]+$?",
            "How do we reduce trash in school?",
        ]

        for text in allowed_inputs:
            with self.subTest(text=text):
                self.assertIsNone(
                    check_content(text),
                    msg=f"Should allow: {text}",
                )
