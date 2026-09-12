from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from account.models import UserConsent
from .models import Category, Post, Reply, Report


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


class ForumBadWordValidationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='alice',
            email='alice@example.com',
            password='secret123',
        )
        UserConsent.objects.create(user=self.user, version='1.0')
        self.category = Category.objects.create(name='General', slug='general')
        self.post = Post.objects.create(
            author=self.user,
            title='Need help',
            content='Question content',
            category=self.category,
        )
        self.client.force_login(self.user)

    def test_post_creation_rejects_bad_words(self):
        response = self.client.post(
            reverse('forum:create'),
            {
                'title': 'Testing bad words',
                'content': 'This is gago and stupid.',
                'category': self.category.pk,
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('inappropriate language', data['html'])
        self.assertFalse(Post.objects.filter(title='Testing bad words').exists())

    def test_reply_creation_rejects_bad_words(self):
        response = self.client.post(
            reverse('forum:create_reply', args=[self.post.pk]),
            {'content': 'You are a tanga and idiot.'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('inappropriate language', data['html'])
        self.assertFalse(Reply.objects.filter(post=self.post, content='You are a tanga and idiot.').exists())

    def test_post_detail_lists_latest_reply_first(self):
        older_reply = Reply.objects.create(
            post=self.post,
            author=self.user,
            content='Older reply',
        )
        newer_reply = Reply.objects.create(
            post=self.post,
            author=self.user,
            content='Newer reply',
        )

        response = self.client.get(reverse('forum:post_detail', args=[self.post.pk]))

        self.assertEqual(list(response.context['replies']), [newer_reply, older_reply])


class ForumModerationWarningTests(TestCase):
    def setUp(self):
        self.teacher = get_user_model().objects.create_user(
            username='teacher',
            email='teacher@example.com',
            password='secret123',
        )
        UserConsent.objects.create(user=self.teacher, version='1.0')
        self.teacher.groups.add(Group.objects.get_or_create(name='Teacher')[0])

        self.category = Category.objects.create(name='General', slug='general')
        self.post = Post.objects.create(
            author=self.teacher,
            title='Need help',
            content='This is a stupid discussion.',
            category=self.category,
        )

        self.reporter = get_user_model().objects.create_user(
            username='reporter',
            email='reporter@example.com',
            password='secret123',
        )
        UserConsent.objects.create(user=self.reporter, version='1.0')

        Report.objects.create(
            reporter=self.reporter,
            content_type=Report.POST,
            post=self.post,
            reason='inappropriate',
            description='Contains offensive language.',
        )

        self.client.force_login(self.teacher)

    def test_moderation_dashboard_shows_bad_word_warning(self):
        response = self.client.get(reverse('forum:moderation_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'inappropriate language')


class ForumAjaxUpvoteTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='alice',
            email='alice@example.com',
            password='secret123',
        )
        UserConsent.objects.create(user=self.user, version='1.0')
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
