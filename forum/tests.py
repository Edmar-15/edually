from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from .models import Category, Post, Reply


class ForumLegacyRouteCompatibilityTests(TestCase):
    def test_legacy_route_names_resolve(self):
        legacy_names = [
            'forum:feed',
            'forum:notifications',
            'forum:moderation_dashboard',
            'forum:post_create',
            'forum:upvote',
            'forum:reply_upvote',
        ]

        for route_name in legacy_names:
            if route_name in {'forum:upvote', 'forum:reply_upvote'}:
                if route_name == 'forum:upvote':
                    self.assertIsNotNone(reverse(route_name, args=[1]))
                else:
                    self.assertIsNotNone(reverse(route_name, args=[1]))
            else:
                self.assertIsNotNone(reverse(route_name))


class ForumAjaxUpvoteTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='alice',
            email='alice@example.com',
            password='secret123',
        )
        self.category = Category.objects.create(name='General', slug='general')
        self.post = Post.objects.create(
            author=self.user,
            title='Need help',
            content='Question content',
            category=self.category,
        )
        self.reply = Reply.objects.create(
            post=self.post,
            author=self.user,
            content='Helpful reply',
        )
        self.client.force_login(self.user)

    def test_post_upvote_ajax_returns_json(self):
        response = self.client.post(
            reverse('forum:upvote', args=[self.post.pk]),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['upvotes'], 1)
        self.assertTrue(data['has_upvoted'])

    def test_reply_upvote_ajax_returns_json(self):
        response = self.client.post(
            reverse('forum:reply_upvote', args=[self.reply.pk]),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['upvotes'], 1)
        self.assertTrue(data['has_upvoted'])
