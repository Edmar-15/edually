# aihelper/views.py
import json
import logging
from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required
from .explanations import system_prompt_for
from .models import Message, Conversation
import openai
from django.views.decorators.cache import never_cache

log = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# 0️⃣ Utility – fetch the most recent *n* turns (default 8) from a conversation
# ----------------------------------------------------------------------
def _last_n_turns(conversation: Conversation, n_turns: int = 8) -> list[dict]:
    """
    Return the most recent ``n_turns`` *pairs* (user  assistant) from *conversation*
    in the order expected by the OpenAI chat API.

    The ``Message`` model stores the AI side as ``role='ai'`` for historical
    reasons, but the OpenAI endpoint requires the string ``'assistant'``.
    This helper therefore **normalises the role on‑the‑fly** before returning
    the list.
    """
    # Grab the newest ``2 * n_turns`` rows (user  ai for each turn)
    recent_qs = (
        conversation.messages.select_related("user")
        .order_by("-created_at")                # newest first
        .values("role", "content")[: 2 * n_turns]
    )
    recent = list(recent_qs)
    # Reverse to chronological order (oldest → newest) for the model.
    recent.reverse()

    # ------------------------------------------------------------------
    # Map our internal ``ai`` role to the OpenAI‑accepted ``assistant`` value.
    # Any unexpected role falls back to ``user`` – that should never happen but
    # keeps the function safe.
    # ------------------------------------------------------------------
    openai_role_map = {"user": "user", "ai": "assistant"}

    return [
        {"role": openai_role_map.get(r["role"], "user"), "content": r["content"]}
        for r in recent
    ]

# ----------------------------------------------------------------------
# 1️⃣ Helper that actually contacts OpenAI Cloud
# ----------------------------------------------------------------------
def _call_openai(messages: list[dict], *, level: str = "simplified") -> str:
    """
    Calls the OpenAI chat completion endpoint and returns the assistant’s reply.

    * ``messages`` – already contains the system prompt, optional history and the
      current user question.\n
    * ``level`` – allows us to set a *temperature* that matches the desired\n
      tone (e.g. lower temperature for factual/technical answers, higher for\n
      Socratic probing).\n
    """
    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    # A tiny temperature map – feel free to adjust per‑model.
    temperature_by_level = {
        "simplified": 0.5,
        "technical":  0.2,
        "socratic":   0.8,   # a bit more exploratory / creative
    }
    temperature = temperature_by_level.get(level, 0.5)

    try:
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=1024,
        )
    except Exception as exc:  # pragma: no cover – exercised via test mock
        # Log the *full* exception (type, message, traceback) **and** the payload.
        log.exception(
            "OpenAI request failed – model=%s, temperature=%.2f, token_limit=%s, payload=%s",
            settings.OPENAI_MODEL,
            temperature,
            1024,
            messages,
        )
        # Re‑raise a generic error that the view catches later.
        raise RuntimeError("OpenAI request failed") from exc

    # Return the text of the sole choice.
    return resp.choices[0].message.content


def _conversation_summaries(user) -> list[dict]:
    """Build lightweight summaries with the first user prompt as the display text."""
    conversations = Conversation.objects.filter(user=user).prefetch_related("messages")
    summaries = []
    for conversation in conversations:
        first_user_prompt = (
            conversation.messages.filter(role="user")
            .order_by("created_at")
            .values_list("content", flat=True)
            .first()
        )
        prompt = (first_user_prompt or conversation.title or f"Conversation {conversation.id}").strip()
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
# 2️⃣ Page view – renders the chat UI
# ----------------------------------------------------------------------
@login_required(login_url="account:login")
@never_cache 
def helper(request):
    """
    Render the main page.
    *If* a ``conversation_id`` GET param is supplied we show that thread,
    otherwise we render an empty placeholder (the UI will create a new
    conversation when the first question is sent).
    """
    conv_id = request.GET.get("conversation_id")
    if conv_id:
        conversation = get_object_or_404(Conversation, pk=conv_id, user=request.user)
        messages = conversation.messages.select_related("user")
    else:
        conversation = None
        messages = []  # no messages yet

    # Load *all* conversations for the right‑hand mini‑map
    conversation_summaries = _conversation_summaries(request.user)

    return render(
        request,
        "aihelper/helper.html",
        {
            "history": messages,               # messages of the active thread
            "conversations": conversation_summaries,   # for the mini‑map
            "conversation_summaries": conversation_summaries,
            "active_conversation_id": conv_id,
        },
    )


# ----------------------------------------------------------------------
# 3️⃣ JSON: list of all user conversations (mini‑map)
# ----------------------------------------------------------------------
@login_required(login_url="account:login")
@never_cache 
def list_conversations(request):
    """Return a tiny JSON payload for the right‑hand mini‑map."""
    summaries = _conversation_summaries(request.user)
    payload = [
        {
            "id": item["id"],
            "title": item["title"],
            "prompt": item["prompt"],
            "created_at": item["created_at"].isoformat(),
        }
        for item in summaries
    ]
    return JsonResponse({"conversations": payload})


# ----------------------------------------------------------------------
# 4️⃣ JSON: fetch a single conversation (messages)
# ----------------------------------------------------------------------
@login_required(login_url="account:login")
@never_cache 
def get_conversation(request, pk):
    """
    Return all messages belonging to ``pk``.  Used when the user clicks a
    conversation in the mini‑map.
    """
    conv = get_object_or_404(Conversation, pk=pk, user=request.user)
    msgs = list(
        conv.messages.values("role", "content", "created_at")
    )
    return JsonResponse(
        {
            "conversation_id": conv.id,
            "title": conv.title,
            "messages": msgs,
        }
    )


# ----------------------------------------------------------------------
# 5️⃣ JSON API – answer a question (store both sides)
# ----------------------------------------------------------------------
@login_required(login_url="account:login")
def helper_api(request):
    """Accept a POST with a question, call OpenAI, store → return answer."""
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")

    payload = json.loads(request.body)

    question = payload.get("question")
    level   = payload.get("explanation_level", "simplified")
    conv_id = payload.get("conversation_id")          # may be None

    if not question:
        return JsonResponse({"error": "No question supplied"}, status=400)

    # ------------------------------------------------------------------
    # 1️⃣ Resolve the system prompt for the requested level.
    # ------------------------------------------------------------------
    try:
        system_prompt = system_prompt_for(level, question)
    except ValueError:          # unknown level – fallback to simplified
        log.warning("Invalid explanation level %r – using simplified", level)
        system_prompt = system_prompt_for("simplified", question)

    # ------------------------------------------------------------------
    # 2️⃣ Find or create the conversation we will write to
    # ------------------------------------------------------------------
    if conv_id:
        conversation = get_object_or_404(
            Conversation, pk=conv_id, user=request.user
        )
    else:
        conversation = Conversation.objects.create(
            user=request.user,
            title=question[:80],
        )

    # ------------------------------------------------------------------
    # 3️⃣ Gather recent history (up to 8 turns) if we have an existing
    #    conversation.  For brand‑new threads ``history`` is empty.
    # ------------------------------------------------------------------
    if conv_id:
        history = _last_n_turns(conversation, n_turns=8)
    else:
        history = []

    # Build the final OpenAI message list:
    #   system → (optional) history → current user question
    openai_messages = [{"role": "system", "content": system_prompt}]
    openai_messages.extend(history)
    openai_messages.append({"role": "user", "content": question})

    try:
        ai_reply = _call_openai(openai_messages, level=level)   # pass level for temp
    except Exception as exc:               # a list of dicts, the name is historical.
         log.error("OpenAI request failed – falling back to canned response: %s", exc)
         # Keep the fallback wording *consistent* with the chosen level.
         ai_reply = (
            f"[{level.title()} explanation] (fallback) Here is a short answer to: "
            f"“{question}”."
        )

    # ------------------------------------------------------------------
    # 5️⃣ Persist both user + AI messages inside the same conversation
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
                ),
            ]
        )
    # Keep the title in sync if this was the first message.
    if not conversation.title:
        conversation.title = question[:80]
        conversation.save(update_fields=["title"])

    return JsonResponse(
        {
            "answer":           ai_reply,
            "conversation_id": conversation.id,
            "title":            conversation.title,
        }
    )
