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
        
    @patch(
        "aihelper.views._call_openai",
        return_value="What do you already know about fractions?"
    )
    def test_socratic_uses_shared_prompt(self, mock_openai):

        from .explanations import get_socratic_prompt

        question = "How do fractions work?"

        response = self.post_question({
            "question": question,
            "explanation_level": "socratic",
        })

        self.assertEqual(response.status_code, 200)

        mock_openai.assert_called_once()

        messages = mock_openai.call_args.args[0]

        self.assertEqual(
            messages[0]["content"],
            get_socratic_prompt(question),
        )

        self.assertEqual(
            messages[-1]["content"],
            question,
        )

        self.assertEqual(
            mock_openai.call_args.kwargs["level"],
            "socratic",
        )

        self.assertEqual(
            response.json()["source"],
            "socratic",
        )
        
    @patch(
        "aihelper.views._call_openai",
        return_value="Here is some guidance."
    )
    def test_socratic_learning_actions(self, mock_ai):

        first = self.post_question({
            "question": "How does a Python loop work?",
            "explanation_level": "socratic",
        })

        self.assertEqual(first.status_code, 200)

        conversation_id = first.json()["conversation_id"]

        actions = {
            "hint": "Give one small clue",
            "simplify": "Simplify the latest Socratic question",
            "answer": "Provide the correct answer",
        }

        for action, expected_instruction in actions.items():

            with self.subTest(action=action):

                response = self.post_question({
                    "question": "",
                    "explanation_level": "socratic",
                    "conversation_id": conversation_id,
                    "socratic_action": action,
                })

                self.assertEqual(response.status_code, 200)

                messages = mock_ai.call_args.args[0]

                self.assertIn(
                    expected_instruction,
                    messages[0]["content"],
                )

                self.assertEqual(
                    response.json()["source"],
                    "socratic",
                )

        self.assertEqual(
            Message.objects.filter(
                conversation_id=conversation_id
            ).count(),
            8,
        )

    def test_socratic_action_requires_conversation(self):

        response = self.post_question({
            "question": "",
            "explanation_level": "socratic",
            "socratic_action": "hint",
        })

        self.assertEqual(response.status_code, 400)

        self.assertEqual(
            Conversation.objects.count(),
            0,
        )
        
    @patch(
        "aihelper.views._call_openai",
        return_value="What do you already know about variables?"
    )
    def test_socratic_conversation_mode_is_saved(self, mock_ai):

        response = self.post_question({
            "question": "What is a Python variable?",
            "explanation_level": "socratic",
        })

        self.assertEqual(response.status_code, 200)

        conversation_id = response.json()["conversation_id"]

        conversation = Conversation.objects.get(
            pk=conversation_id
        )

        self.assertEqual(
            conversation.explanation_level,
            "socratic",
        )

        history = self.client.get(
            reverse(
                "aihelper:get_conversation",
                args=[conversation_id],
            )
        )

        self.assertEqual(history.status_code, 200)

        self.assertEqual(
            history.json()["explanation_level"],
            "socratic",
        )

    @patch(
        "aihelper.views._call_openai",
        return_value="An explanation."
    )
    @patch(
        "aihelper.views.find_relevant_slm_context"
    )
    def test_conversation_mode_updates(self, mock_context, mock_ai):

        mock_context.return_value = {
            "found": False,
            "sources": [],
            "context": "",
        }

        first = self.post_question({
            "question": "Explain Python variables",
            "explanation_level": "simplified",
        })

        self.assertEqual(first.status_code, 200)

        conversation_id = first.json()["conversation_id"]

        second = self.post_question({
            "question": "Explain more technically",
            "explanation_level": "technical",
            "conversation_id": conversation_id,
        })

        self.assertEqual(second.status_code, 200)

        conversation = Conversation.objects.get(
            pk=conversation_id
        )

        self.assertEqual(
            conversation.explanation_level,
            "technical",
        )

        self.assertEqual(
            Conversation.objects.count(),
            1,
        )
        

    @patch(
        "aihelper.views._call_openai",
        return_value="What do you already know about loops?"
    )
    @patch("aihelper.views.find_relevant_slm_context")
    def test_socratic_does_not_search_slm(self, mock_context, mock_ai):
        response = self.post_question({
            "question": "Explain Python loops",
            "explanation_level": "socratic",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source"], "socratic")

        mock_context.assert_not_called()
        mock_ai.assert_called_once()

        ai_message = Message.objects.get(
            role="ai",
            conversation_id=response.json()["conversation_id"],
        )

        self.assertEqual(ai_message.source_type, "socratic")


    @patch("aihelper.views._call_openai")
    def test_socratic_action_cannot_access_other_user(self, mock_ai):
        foreign = Conversation.objects.create(
            user=self.other,
            title="Private discussion",
            explanation_level="socratic",
        )

        Message.objects.create(
            conversation=foreign,
            user=self.other,
            role="ai",
            content="What do you think?",
            source_type="socratic",
        )

        response = self.post_question({
            "question": "",
            "explanation_level": "socratic",
            "conversation_id": foreign.pk,
            "socratic_action": "hint",
        })

        self.assertEqual(response.status_code, 404)
        self.assertEqual(foreign.messages.count(), 1)

        mock_ai.assert_not_called()


    @patch("aihelper.views._call_openai")
    def test_socratic_action_rejected_in_simple_conversation(self, mock_ai):
        conversation = Conversation.objects.create(
            user=self.user,
            title="Simple discussion",
            explanation_level="simplified",
        )

        Message.objects.create(
            conversation=conversation,
            user=self.user,
            role="ai",
            content="A normal explanation.",
            source_type="general",
        )

        response = self.post_question({
            "question": "",
            "explanation_level": "socratic",
            "conversation_id": conversation.pk,
            "socratic_action": "hint",
        })

        self.assertEqual(response.status_code, 400)
        self.assertEqual(conversation.messages.count(), 1)

        mock_ai.assert_not_called()


    @patch(
        "aihelper.views._call_openai",
        side_effect=RuntimeError("Simulated AI failure")
    )
    def test_socratic_failure_does_not_save_messages(self, mock_ai):
        conversation = Conversation.objects.create(
            user=self.user,
            title="Existing conversation",
            explanation_level="simplified",
        )

        response = self.post_question({
            "question": "What is recursion?",
            "explanation_level": "socratic",
            "conversation_id": conversation.pk,
        })

        self.assertEqual(response.status_code, 500)

        self.assertEqual(
            conversation.messages.count(),
            0,
        )

        conversation.refresh_from_db()

        self.assertEqual(
            conversation.explanation_level,
            "simplified",
        )


    @patch(
        "aihelper.views._call_openai",
        side_effect=[
            "What do you think a variable is?",
            "What other types of values could it store?",
        ],
    )
    def test_socratic_followup_includes_conversation_history(self, mock_ai):
        first = self.post_question({
            "question": "What is a variable?",
            "explanation_level": "socratic",
        })

        self.assertEqual(first.status_code, 200)

        conversation_id = first.json()["conversation_id"]

        second = self.post_question({
            "question": "Variables store numbers.",
            "explanation_level": "socratic",
            "conversation_id": conversation_id,
        })

        self.assertEqual(second.status_code, 200)
        self.assertEqual(mock_ai.call_count, 2)

        messages = mock_ai.call_args.args[0]

        self.assertEqual(
            [message["role"] for message in messages],
            ["system", "user", "assistant", "user"],
        )

        self.assertEqual(
            messages[1]["content"],
            "What is a variable?",
        )

        self.assertEqual(
            messages[2]["content"],
            "What do you think a variable is?",
        )

        self.assertEqual(
            messages[3]["content"],
            "Variables store numbers.",
        )

        self.assertEqual(
            Message.objects.filter(
                conversation_id=conversation_id
            ).count(),
            4,
        )

    def test_socratic_source_type_is_valid_choice(self):
        conversation = Conversation.objects.create(
            user=self.user,
            title="Socratic validation",
            explanation_level="socratic",
        )

        message = Message(
            conversation=conversation,
            user=self.user,
            role="ai",
            content="What do you think?",
            source_type="socratic",
            source_label="Socratic learning",
        )

        message.full_clean()


    @patch("aihelper.views.openai.OpenAI")
    def test_openai_failure_omits_student_data_from_logs(self, mock_client):
        from .views import _call_openai

        private_text = "STUDENT_PRIVATE_MESSAGE_ABC123"

        mock_client.return_value.chat.completions.create.side_effect = (
            RuntimeError(f"Provider echoed: {private_text}")
        )

        with self.assertLogs("aihelper.views", level="ERROR") as logs:
            with self.assertRaisesRegex(
                RuntimeError,
                "OpenAI request failed",
            ):
                _call_openai(
                    [
                        {
                            "role": "user",
                            "content": private_text,
                        }
                    ],
                    level="socratic",
                )

        logged_text = "\n".join(logs.output)

        self.assertIn("OpenAI request failed", logged_text)
        self.assertNotIn(private_text, logged_text)