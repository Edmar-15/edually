# aihelper/views.py

import json
import logging

from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.db import transaction

from .explanations import system_prompt_for
from .models import Message, Conversation
from .context import find_relevant_slm_context

import openai


log = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# 0️⃣ Utility – fetch the most recent *n* turns
# ----------------------------------------------------------------------

def _last_n_turns(
    conversation: Conversation,
    n_turns: int = 8,
) -> list[dict]:
    """
    Return the most recent ``n_turns`` pairs from a conversation
    in the order expected by the OpenAI chat API.

    The Message model stores the AI side as ``role='ai'`` for
    historical reasons, while the OpenAI endpoint expects
    ``role='assistant'``.
    """

    recent_qs = (
        conversation.messages
        .select_related("user")
        .order_by("-created_at")
        .values("role", "content")[: 2 * n_turns]
    )

    recent = list(recent_qs)

    # Reverse to chronological order.
    recent.reverse()

    openai_role_map = {
        "user": "user",
        "ai": "assistant",
    }

    return [
        {
            "role": openai_role_map.get(
                item["role"],
                "user",
            ),
            "content": item["content"],
        }
        for item in recent
    ]


# ----------------------------------------------------------------------
# 1️⃣ Helper that actually contacts OpenAI Cloud
# ----------------------------------------------------------------------

def _call_openai(
    messages: list[dict],
    *,
    level: str = "simplified",
) -> str:
    """
    Calls the OpenAI chat completion endpoint and returns the
    assistant's reply.

    ``messages`` already contains:
        system prompt
        optional conversation history
        current user question
    """

    client = openai.OpenAI(
        api_key=settings.OPENAI_API_KEY,
    )

    temperature_by_level = {
        "simplified": 0.5,
        "technical": 0.2,
        "socratic": 0.8,
    }

    temperature = temperature_by_level.get(
        level,
        0.5,
    )

    try:
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=1024,
        )

    except Exception as exc:
        log.exception(
            (
                "OpenAI request failed – model=%s, "
                "temperature=%.2f, token_limit=%s, payload=%s"
            ),
            settings.OPENAI_MODEL,
            temperature,
            1024,
            messages,
        )

        raise RuntimeError(
            "OpenAI request failed"
        ) from exc

    return resp.choices[0].message.content


# ----------------------------------------------------------------------
# Socratic mode – completely independent from SLM/general source logic
# ----------------------------------------------------------------------

def _handle_socratic_request(
    request,
    question: str,
    conversation: Conversation,
) -> JsonResponse:
    """
    Handle Socratic mode separately from Simple/Technical mode.

    Socratic mode:
    - Does NOT search SLM content.
    - Does NOT use the Simple/Technical source logic.
    - Uses a Socratic-specific system prompt.
    - Stores the response source as "socratic".
    """

    system_prompt = """
You are EduAlly's Socratic learning assistant.

Your purpose is to help the student THINK and discover the answer,
not simply provide the answer.

Follow these rules:

1. Do not immediately give the final answer to the student's question.
2. Ask a meaningful guiding question that helps the student reason.
3. Ask only ONE main question at a time.
4. Use the student's previous responses to decide what to ask next.
5. If the student's reasoning is correct, acknowledge it briefly and
   guide them toward the next step.
6. If the student's reasoning is incorrect, do not simply give the answer.
   Point out the issue and provide a small hint or guiding question.
7. If the student is confused, simplify the reasoning without directly
   solving the entire problem.
8. Encourage the student to explain their reasoning.
9. Avoid long lectures and unnecessary definitions.
10. Do not mention SLM, learning-material sources, or general-knowledge
    source labels.
11. Stay focused on helping the student understand the concept through
    guided questioning.

Your response should normally contain:
- a brief acknowledgement or observation when useful
- ONE guiding question
"""

    # Get recent conversation history.
    history = _last_n_turns(
        conversation,
        n_turns=8,
    )

    openai_messages = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]

    openai_messages.extend(history)

    openai_messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    try:
        ai_reply = _call_openai(
            openai_messages,
            level="socratic",
        )

    except Exception as exc:
        log.error(
            "Socratic OpenAI request failed: %s",
            exc,
        )

        return JsonResponse(
            {
                "error": "The Socratic AI could not respond right now."
            },
            status=500,
        )

    # Persist the Socratic exchange.
    with transaction.atomic():

        Message.objects.bulk_create(
            [
                Message(
                    conversation=conversation,
                    user=request.user,
                    role="user",
                    content=question,
                ),

                Message(
                    conversation=conversation,
                    user=request.user,
                    role="ai",
                    content=ai_reply,
                    source_type="socratic",
                    source_label="Socratic learning",
                    source_metadata=[],
                ),
            ]
        )

    if not conversation.title:
        conversation.title = question[:80]
        conversation.save(
            update_fields=["title"]
        )

    return JsonResponse(
        {
            "answer": ai_reply,

            "source": "socratic",
            "source_label": "Socratic learning",
            "sources": [],

            "conversation_id": conversation.id,
            "title": conversation.title,
        }
    )


# ----------------------------------------------------------------------
# 2️⃣ Conversation summaries
# ----------------------------------------------------------------------

def _conversation_summaries(user) -> list[dict]:
    """
    Build lightweight summaries with the first user prompt as the
    display text.
    """

    conversations = (
        Conversation.objects
        .filter(user=user)
        .prefetch_related("messages")
    )

    summaries = []

    for conversation in conversations:

        first_user_prompt = (
            conversation.messages
            .filter(role="user")
            .order_by("created_at")
            .values_list("content", flat=True)
            .first()
        )

        prompt = (
            first_user_prompt
            or conversation.title
            or f"Conversation {conversation.id}"
        ).strip()

        summaries.append(
            {
                "id": conversation.id,
                "title": prompt,
                "prompt": prompt,
                "created_at": conversation.created_at,
            }
        )

    return summaries


# ----------------------------------------------------------------------
# 3️⃣ Page view – renders the chat UI
# ----------------------------------------------------------------------

@login_required(login_url="account:login")
@never_cache
def helper(request):
    """
    Render the main AI Helper page.

    If ``conversation_id`` is supplied, the selected conversation
    is loaded.

    The existing template receives the Message objects through
    ``history``.
    """

    conv_id = request.GET.get("conversation_id")

    if conv_id:
        conversation = get_object_or_404(
            Conversation,
            pk=conv_id,
            user=request.user,
        )

        messages = (
            conversation.messages
            .select_related("user")
        )

    else:
        conversation = None
        messages = []

    conversation_summaries = _conversation_summaries(
        request.user
    )

    return render(
        request,
        "aihelper/helper.html",
        {
            "history": messages,
            "conversations": conversation_summaries,
            "conversation_summaries": conversation_summaries,
            "active_conversation_id": conv_id,
        },
    )


# ----------------------------------------------------------------------
# 4️⃣ JSON: list of all user conversations
# ----------------------------------------------------------------------

@login_required(login_url="account:login")
@never_cache
def list_conversations(request):
    """
    Return a tiny JSON payload for the right-hand mini-map.
    """

    summaries = _conversation_summaries(
        request.user
    )

    payload = [
        {
            "id": item["id"],
            "title": item["title"],
            "prompt": item["prompt"],
            "created_at": item["created_at"].isoformat(),
        }
        for item in summaries
    ]

    return JsonResponse(
        {
            "conversations": payload,
        }
    )


# ----------------------------------------------------------------------
# 5️⃣ JSON: fetch a single conversation
# ----------------------------------------------------------------------
@login_required(login_url="account:login")
@never_cache
def get_conversation(request, pk):
    """
    Return all messages belonging to ``pk``. Used when the user clicks a
    conversation in the mini-map.
    """
    conv = get_object_or_404(
        Conversation,
        pk=pk,
        user=request.user,
    )

    msgs = list(
        conv.messages.values(
            "role",
            "content",
            "created_at",
            "source_type",
            "source_label",
            "source_metadata",
        )
    )

    return JsonResponse(
        {
            "conversation_id": conv.id,
            "title": conv.title,
            "messages": msgs,
        }
    )


# ----------------------------------------------------------------------
# 6️⃣ JSON API – answer a question
# ----------------------------------------------------------------------
@login_required(login_url="account:login")
def helper_api(request):
    """
    Accept a POST with a question, find relevant SLM content when available,
    call OpenAI, persist both messages and the answer source, then return
    the answer + source information to the frontend.
    """

    if request.method != "POST":
        return HttpResponseBadRequest("POST only")

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "Invalid JSON payload"},
            status=400,
        )

    question = (payload.get("question") or "").strip()
    level = payload.get("explanation_level", "simplified")
    conv_id = payload.get("conversation_id")

    if not question:
        return JsonResponse(
            {"error": "No question supplied"},
            status=400,
        )

    # ------------------------------------------------------------------
    # SOCRATIC MODE
    #
    # This branch MUST happen before:
    #   - system_prompt_for()
    #   - find_relevant_slm_context()
    #
    # Socratic mode has its own behavior and source handling.
    # ------------------------------------------------------------------
    if level == "socratic":

        if conv_id:
            conversation = get_object_or_404(
                Conversation,
                pk=conv_id,
                user=request.user,
            )
        else:
            conversation = Conversation.objects.create(
                user=request.user,
                title=question[:80],
            )

        return _handle_socratic_request(
            request=request,
            question=question,
            conversation=conversation,
        )

    # ------------------------------------------------------------------
    # 1. Resolve the system prompt.
    # ------------------------------------------------------------------
    try:
        system_prompt = system_prompt_for(level, question)
    except ValueError:
        log.warning(
            "Invalid explanation level %r - using simplified",
            level,
        )
        level = "simplified"
        system_prompt = system_prompt_for(level, question)

    # ------------------------------------------------------------------
    # 2. Find or create the conversation.
    # ------------------------------------------------------------------
    if conv_id:
        conversation = get_object_or_404(
            Conversation,
            pk=conv_id,
            user=request.user,
        )
    else:
        conversation = Conversation.objects.create(
            user=request.user,
            title=question[:80],
        )

    # ------------------------------------------------------------------
    # 3. Search the user's accessible SLM content.
    #
    # If relevant SLM material exists:
    #   source = "slm"
    #
    # Otherwise:
    #   source = "general"
    #
    # The source information is later stored in Message so it survives
    # page reloads and conversation reopening.
    # ------------------------------------------------------------------
    try:
        slm_result = find_relevant_slm_context(
            request.user,
            question,
        )
    except Exception:
        log.exception(
            "SLM context lookup failed for user=%s",
            request.user.pk,
        )

        slm_result = {
            "found": False,
            "sources": [],
            "context": "",
        }

    if slm_result.get("found"):
        answer_source = "slm"
        answer_source_label = "From your learning materials"
        source_metadata = slm_result.get("sources", [])
        slm_context = slm_result.get("context", "")

        # --------------------------------------------------------------
        # Tell the AI to use the user's learning materials as its
        # primary source.
        # --------------------------------------------------------------
        system_prompt = (
            f"{system_prompt}\n\n"
            "IMPORTANT LEARNING MATERIAL INSTRUCTION:\n"
            "Relevant learning materials from the user's accessible "
            "learning content are provided below.\n\n"
            "Use these learning materials as the primary source for "
            "answering the user's question. Base your answer on the "
            "provided material when it contains the information needed.\n"
            "Do not claim that the information came from the learning "
            "materials unless it is actually supported by them.\n"
            "If the material does not completely answer the question, "
            "you may supplement it with general knowledge, but do not "
            "invent information that is not supported.\n\n"
            "LEARNING MATERIAL:\n"
            f"{slm_context}"
        )

    else:
        answer_source = "general"
        answer_source_label = "General knowledge"
        source_metadata = []

        # --------------------------------------------------------------
        # No relevant SLM material was found.
        # --------------------------------------------------------------
        system_prompt = (
            f"{system_prompt}\n\n"
            "There is no relevant learning material available to answer "
            "this specific question. Answer using your general knowledge. "
            "Do not pretend that the answer came from the user's learning "
            "materials."
        )

    # ------------------------------------------------------------------
    # 4. Gather recent conversation history.
    # ------------------------------------------------------------------
    if conv_id:
        history = _last_n_turns(
            conversation,
            n_turns=8,
        )
    else:
        history = []

    # ------------------------------------------------------------------
    # 5. Build OpenAI messages.
    # ------------------------------------------------------------------
    openai_messages = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]

    openai_messages.extend(history)

    openai_messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    # ------------------------------------------------------------------
    # 6. Ask OpenAI.
    # ------------------------------------------------------------------
    try:
        ai_reply = _call_openai(
            openai_messages,
            level=level,
        )

    except Exception as exc:
        log.error(
            "OpenAI request failed - falling back to canned response: %s",
            exc,
        )

        ai_reply = (
            f"[{level.title()} explanation] "
            f"(fallback) Here is a short answer to: "
            f"“{question}”."
        )

    # ------------------------------------------------------------------
    # 7. Persist both user + AI messages.
    #
    # IMPORTANT:
    # The source fields are stored directly on the AI Message.
    # This is what makes the source indicator persistent after reload.
    # ------------------------------------------------------------------
    from django.db import transaction

    with transaction.atomic():

        Message.objects.bulk_create(
            [
                Message(
                    conversation=conversation,
                    user=request.user,
                    role="user",
                    content=question,
                ),

                Message(
                    conversation=conversation,
                    user=request.user,
                    role="ai",
                    content=ai_reply,

                    # Persistent source information
                    source_type=answer_source,
                    source_label=answer_source_label,
                    source_metadata=source_metadata,
                ),
            ]
        )

    # ------------------------------------------------------------------
    # 8. Keep the conversation title synchronized.
    # ------------------------------------------------------------------
    if not conversation.title:
        conversation.title = question[:80]
        conversation.save(
            update_fields=["title"]
        )

    # ------------------------------------------------------------------
    # 9. Return the answer + source information to JavaScript.
    # ------------------------------------------------------------------
    return JsonResponse(
        {
            "answer": ai_reply,

            "source": answer_source,
            "source_label": answer_source_label,
            "sources": source_metadata,

            "conversation_id": conversation.id,
            "title": conversation.title,
        }
    )