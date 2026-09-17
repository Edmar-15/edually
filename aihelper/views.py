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
    Return all messages belonging to ``pk``.

    IMPORTANT:
    Source information is returned here so the frontend can restore
    the SLM/general indicator after a reload.
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
    Accept a POST with a question.

    Processing flow:

        1. Resolve explanation level.
        2. Find/create conversation.
        3. Search the user's accessible SLM materials.
        4. If relevant SLM context exists:
               answer using SLM context.
           Otherwise:
               answer using general knowledge.
        5. Call OpenAI.
        6. Save user + AI messages.
        7. Persist source information on the AI message.
        8. Return answer + source information to frontend.
    """

    if request.method != "POST":
        return HttpResponseBadRequest("POST only")

    # ---------------------------------------------------------------
    # Parse request JSON
    # ---------------------------------------------------------------

    try:
        payload = json.loads(request.body)

    except json.JSONDecodeError:
        return JsonResponse(
            {
                "error": "Invalid JSON",
            },
            status=400,
        )

    question = payload.get("question")

    level = payload.get(
        "explanation_level",
        "simplified",
    )

    conv_id = payload.get(
        "conversation_id"
    )

    if not question:
        return JsonResponse(
            {
                "error": "No question supplied",
            },
            status=400,
        )

    question = str(question).strip()

    if not question:
        return JsonResponse(
            {
                "error": "No question supplied",
            },
            status=400,
        )

    # ---------------------------------------------------------------
    # 1️⃣ Resolve the base system prompt
    # ---------------------------------------------------------------

    try:
        base_system_prompt = system_prompt_for(
            level,
            question,
        )

    except ValueError:
        log.warning(
            "Invalid explanation level %r – using simplified",
            level,
        )

        level = "simplified"

        base_system_prompt = system_prompt_for(
            "simplified",
            question,
        )

    # ---------------------------------------------------------------
    # 2️⃣ Find or create the conversation
    # ---------------------------------------------------------------

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

    # ---------------------------------------------------------------
    # 3️⃣ Search accessible SLM content
    # ---------------------------------------------------------------
    #
    # This is intentionally done BEFORE OpenAI is called.
    #
    # find_relevant_slm_context() is responsible for:
    #
    #   - checking the user's accessible subjects
    #   - checking accessible modules
    #   - checking accessible personal materials
    #   - checking relevance
    #   - returning only relevant context
    #
    # If retrieval fails, we safely fall back to general knowledge
    # rather than breaking the AI Helper.
    # ---------------------------------------------------------------

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

    # ---------------------------------------------------------------
    # 4️⃣ Decide answer source
    # ---------------------------------------------------------------

    if slm_result.get("found"):

        answer_source = "slm"

        answer_source_label = (
            "From your learning materials"
        )

        system_prompt = (
            f"{base_system_prompt}\n\n"

            "IMPORTANT SOURCE INSTRUCTION:\n"
            "Relevant learning material was found in the "
            "user's accessible EduAlly SLM content.\n\n"

            "Use the supplied SLM material as the PRIMARY "
            "SOURCE for answering the user's question.\n\n"

            "Do not claim that information came from an SLM "
            "source unless it is supported by the supplied "
            "material.\n\n"

            "You may explain, simplify, summarize, or connect "
            "ideas from the supplied material, but do not "
            "contradict it.\n\n"

            "If the supplied material does not actually contain "
            "the answer, do not pretend that it does.\n\n"

            "ACCESSIBLE SLM MATERIAL:\n"
            "----------------------------------------\n"
            f"{slm_result.get('context', '')}\n"
            "----------------------------------------"
        )

    else:

        answer_source = "general"

        answer_source_label = (
            "General knowledge"
        )

        system_prompt = (
            f"{base_system_prompt}\n\n"

            "IMPORTANT SOURCE INSTRUCTION:\n"
            "No sufficiently relevant material was found in "
            "the user's accessible EduAlly SLM content.\n\n"

            "Answer the question using general knowledge.\n\n"

            "Do not claim that the answer came from an "
            "EduAlly learning module or personal material.\n\n"

            "The response should be educational, accurate, "
            "and clear."
        )

    # ---------------------------------------------------------------
    # 5️⃣ Gather recent conversation history
    # ---------------------------------------------------------------

    if conv_id:

        history = _last_n_turns(
            conversation,
            n_turns=8,
        )

    else:

        history = []

    # ---------------------------------------------------------------
    # 6️⃣ Build final OpenAI message list
    # ---------------------------------------------------------------

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

    # ---------------------------------------------------------------
    # 7️⃣ Ask OpenAI
    # ---------------------------------------------------------------

    try:

        ai_reply = _call_openai(
            openai_messages,
            level=level,
        )

    except Exception as exc:

        log.error(
            (
                "OpenAI request failed – falling back "
                "to canned response: %s"
            ),
            exc,
        )

        ai_reply = (
            f"[{level.title()} explanation] "
            f"(fallback) Here is a short answer to: "
            f"“{question}”."
        )

    # ---------------------------------------------------------------
    # 8️⃣ Persist both sides of the conversation
    # ---------------------------------------------------------------
    #
    # The important change is that the AI Message now permanently
    # stores:
    #
    #   source_type
    #   source_label
    #   source_metadata
    #
    # This is what makes the source indicator survive reloads.
    # ---------------------------------------------------------------

    source_metadata = slm_result.get(
        "sources",
        [],
    )

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

                    # Persistent source information.
                    source_type=answer_source,
                    source_label=answer_source_label,
                    source_metadata=source_metadata,
                ),
            ]
        )

    # ---------------------------------------------------------------
    # 9️⃣ Keep conversation title in sync
    # ---------------------------------------------------------------

    if not conversation.title:

        conversation.title = question[:80]

        conversation.save(
            update_fields=["title"]
        )

    # ---------------------------------------------------------------
    # 🔟 Return answer + source information
    # ---------------------------------------------------------------

    return JsonResponse(
        {
            "answer": ai_reply,

            # Used immediately by the current frontend response.
            "source": answer_source,

            "source_label": answer_source_label,

            "sources": source_metadata,

            "conversation_id": conversation.id,

            "title": conversation.title,
        }
    )