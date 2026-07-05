# aihelper/views.py
import json
import logging
from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required
from .explanations import system_prompt_for
from .models import Message, Conversation

# ----------------------------------------------------------------------
# Optional lazy import of the Ollama SDK – makes the module importable
# even if the package is not installed (useful for CI).
# ----------------------------------------------------------------------
try:
    from ollama import Client as OllamaClient
except Exception:          # pragma: no cover – defensive fallback
    OllamaClient = None

log = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Helper that actually contacts Ollama Cloud
# ----------------------------------------------------------------------
def _call_ollama(question: str, system_prompt: str) -> str:
    """
    Sends *question* to Ollama Cloud using the supplied *system_prompt*.
    """
    if OllamaClient is None:
        raise RuntimeError("ollama Python client not installed")

    client = OllamaClient(
        host=settings.OLLAMA_HOST,
        headers={"Authorization": f"Bearer {settings.OLLAMA_API_KEY}"},
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": question},
    ]

    resp = client.chat(
        model=settings.OLLAMA_MODEL,
        messages=messages,
        stream=False,
    )
    return resp["message"]["content"]


# ----------------------------------------------------------------------
# 1️⃣ Page view – renders the chat UI
# ----------------------------------------------------------------------
@login_required(login_url="account:login")
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
    conversations = Conversation.objects.filter(user=request.user)

    return render(
        request,
        "aihelper/helper.html",
        {
            "history": messages,               # messages of the active thread
            "conversations": conversations,   # for the mini‑map
            "active_conversation_id": conv_id,
        },
    )


# ----------------------------------------------------------------------
# 2️⃣ JSON: list of all user conversations (mini‑map)
# ----------------------------------------------------------------------
@login_required(login_url="account:login")
def list_conversations(request):
    """Return a tiny JSON payload for the right‑hand mini‑map."""
    conversations = Conversation.objects.filter(user=request.user).values(
        "id", "title", "created_at"
    )
    # Turn ``created_at`` into iso‑string for the front‑end
    payload = [
        {
            "id": c["id"],
            "title": c["title"] or f"Conversation {c['id']}",
            "created_at": c["created_at"].isoformat(),
        }
        for c in conversations
    ]
    return JsonResponse({"conversations": payload})


# ----------------------------------------------------------------------
# 3️⃣ JSON: fetch a single conversation (messages)
# ----------------------------------------------------------------------
@login_required(login_url="account:login")
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
# 4️⃣ JSON API – answer a question (store both sides)
# ----------------------------------------------------------------------
@login_required(login_url="account:login")
def helper_api(request):
    """Accept a POST with a question, call Ollama, store → return answer."""
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")

    payload = json.loads(request.body)

    question = payload.get("question")
    # ← Payload.get already gives you a default if the key is missing.
    level   = payload.get("explanation_level", "simplified")
    conv_id = payload.get("conversation_id")          # may be None

    if not question:
        return JsonResponse({"error": "No question supplied"}, status=400)

    # ------------------------------------------------------------------
    # 1️⃣ Resolve the system prompt for the requested level.
    # ------------------------------------------------------------------
    try:
        system_prompt = system_prompt_for(level, question)
    except ValueError as exc:          # unknown level – fallback to simplified
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
    # 3️⃣ Call Ollama (fallback on error)
    # ------------------------------------------------------------------
    try:
        ai_reply = _call_ollama(question, system_prompt)
    except Exception as exc:               # pragma: no cover – exercised via test mock
        log.error("Ollama request failed – falling back to canned response: %s", exc)
        # Keep the fallback wording *consistent* with the chosen level.
        ai_reply = (
            f"[{level.title()} explanation] (fallback) Here is a short answer to: "
            f"“{question}”."
        )

    # ------------------------------------------------------------------
    # 4️⃣ Persist both user + AI messages inside the same conversation
    # ------------------------------------------------------------------
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
            "conversation_id":  conversation.id,
            "title":            conversation.title,
        }
    )