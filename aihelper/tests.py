"""AI Helper API and conversation isolation tests. No live AI calls."""
import json
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from account.models import UserConsent
from .models import Conversation, Message


class AIHelperTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="ai@example.com", password="StrongPass123!", email_verified=True
        )
        self.other = User.objects.create_user(
            email="other@example.com", password="StrongPass123!", email_verified=True
        )
        UserConsent.objects.create(user=self.user, version=settings.POLICY_VERSION)
        UserConsent.objects.create(user=self.other, version=settings.POLICY_VERSION)
        self.client.force_login(self.user)
        self.api_url = reverse("aihelper:helper_api")

    def post_question(self, payload):
        return self.client.post(
            self.api_url, data=json.dumps(payload), content_type="application/json"
        )

    def test_guest_cannot_open_helper(self):
        self.client.logout()
        response = self.client.get(reverse("aihelper:helper"))
        self.assertEqual(response.status_code, 302)

    def test_helper_page_loads(self):
        response = self.client.get(reverse("aihelper:helper"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "aihelper/helper.html")

    def test_empty_conversation_list(self):
        response = self.client.get(reverse("aihelper:list_conversations"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["conversations"], [])

    def test_conversations_are_isolated_by_user(self):
        own = Conversation.objects.create(user=self.user, title="My chat")
        foreign = Conversation.objects.create(user=self.other, title="Secret chat")
        response = self.client.get(reverse("aihelper:list_conversations"))
        ids = [item["id"] for item in response.json()["conversations"]]
        self.assertIn(own.pk, ids)
        self.assertNotIn(foreign.pk, ids)
        blocked = self.client.get(
            reverse("aihelper:get_conversation", args=[foreign.pk])
        )
        self.assertEqual(blocked.status_code, 404)

    def test_get_own_conversation_returns_messages(self):
        conv = Conversation.objects.create(user=self.user, title="Photosynthesis")
        Message.objects.create(
            conversation=conv, user=self.user, role="user", content="What is it?"
        )
        response = self.client.get(
            reverse("aihelper:get_conversation", args=[conv.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["messages"][0]["content"], "What is it?")

    def test_api_rejects_get_bad_json_and_empty_question(self):
        self.assertEqual(self.client.get(self.api_url).status_code, 400)
        bad = self.client.post(
            self.api_url, data="{invalid", content_type="application/json"
        )
        self.assertEqual(bad.status_code, 400)
        empty = self.post_question({"question": "   "})
        self.assertEqual(empty.status_code, 400)
        self.assertEqual(Conversation.objects.count(), 0)

    @patch("aihelper.views._call_openai", return_value="Plants use sunlight.")
    @patch("aihelper.views.find_relevant_slm_context")
    def test_general_answer_is_persisted(self, lookup, call_ai):
        lookup.return_value = {"found": False, "sources": [], "context": ""}
        response = self.post_question({"question": "What is photosynthesis?"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["answer"], "Plants use sunlight.")
        self.assertEqual(data["source"], "general")
        conv = Conversation.objects.get(pk=data["conversation_id"])
        self.assertEqual(conv.user, self.user)
        self.assertEqual(list(conv.messages.values_list("role", flat=True)), ["user", "ai"])
        self.assertEqual(conv.messages.get(role="ai").source_type, "general")
        call_ai.assert_called_once()

    @patch("aihelper.views._call_openai", return_value="A lesson-based answer.")
    @patch("aihelper.views.find_relevant_slm_context")
    def test_slm_source_metadata_is_saved(self, lookup, call_ai):
        lookup.return_value = {
            "found": True,
            "context": "Lesson excerpt",
            "sources": [{"title": "Lesson 1"}],
        }
        response = self.post_question({"question": "Explain lesson 1"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["source"], "slm")
        ai = Message.objects.get(conversation_id=data["conversation_id"], role="ai")
        self.assertEqual(ai.source_metadata, [{"title": "Lesson 1"}])
        self.assertEqual(ai.source_type, "slm")

    @patch("aihelper.views._call_openai", return_value="Continuing answer")
    @patch("aihelper.views.find_relevant_slm_context")
    def test_existing_conversation_is_reused(self, lookup, call_ai):
        lookup.return_value = {"found": False, "sources": [], "context": ""}
        conv = Conversation.objects.create(user=self.user, title="Existing")
        response = self.post_question(
            {"question": "Follow-up question", "conversation_id": conv.pk}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["conversation_id"], conv.pk)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_cannot_write_to_another_users_conversation(self):
        foreign = Conversation.objects.create(user=self.other, title="Other")
        response = self.post_question(
            {"question": "Hello", "conversation_id": foreign.pk}
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(foreign.messages.exists())