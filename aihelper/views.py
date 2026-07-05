# ----------------------------------------------------------------------
# aihelper/views.py
# ----------------------------------------------------------------------
import json
import logging

from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required

from .models import Message

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
# Page view – renders the chat UI with historic messages
# ----------------------------------------------------------------------
@login_required(login_url="account:login")
def helper(request):
    """
    Render the main page.
    The template reads the user's message history from the DB.
    """
    history = Message.objects.filter(user=request.user)
    return render(request, "aihelper/helper.html", {"history": history})


# ----------------------------------------------------------------------
# JSON API endpoint – talks to Ollama Cloud
# ----------------------------------------------------------------------
@login_required(login_url="account:login")
def helper_api(request):
    """Accepts a POST with a question, calls Ollama Cloud, stores & returns the answer."""
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")

    payload = json.loads(request.body)
    user_input = payload.get("question")
    level = payload.get("explanation_level", "easy")   # easy / technical / advanced

    if not user_input:
        return JsonResponse({"error": "No question supplied"}, status=400)

    # --------------------------------------------------------------
    # Helper that actually contacts Ollama Cloud
    # --------------------------------------------------------------
    def _call_ollama(question: str, level: str) -> str:
        """
        Sends *question* to Ollama Cloud and returns the model's answer.
        All configuration lives in ``settings.py``.
        """
        if OllamaClient is None:
            raise RuntimeError("ollama Python client not installed")

        client = OllamaClient(
            host=settings.OLLAMA_HOST,
            headers={"Authorization": f"Bearer {settings.OLLAMA_API_KEY}"},
        )

        # System prompt incorporates the chosen explanation level
        system_prompt = (
            f"You are an educational assistant. Provide a {level} explanation."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]

        # Non‑streaming request – easy to work with in a normal view
        resp = client.chat(
            model=settings.OLLAMA_MODEL,
            messages=messages,
            stream=False,
        )
        # ``resp`` looks like: {"message": {"role": "...", "content": "..."}}
        return resp["message"]["content"]

    # --------------------------------------------------------------
    # Try the real LLM; on any exception fall back to a safe canned reply
    # --------------------------------------------------------------
    try:
        ai_reply = _call_ollama(user_input, level)
    except Exception as exc:               # pragma: no cover – exercised via test mock
        log.error("Ollama request failed – falling back to canned response: %s", exc)
        ai_reply = (
            f"[{level.title()} explanation] "
            f"(fallback) Here is a short answer to: “{user_input}”."
        )

    # --------------------------------------------------------------
    # Persist both sides of the conversation so the sidebar can rebuild
    # --------------------------------------------------------------
    Message.objects.bulk_create(
        [
            Message(user=request.user, role="user", content=user_input),
            Message(user=request.user, role="ai", content=ai_reply),
        ]
    )

    return JsonResponse({"answer": ai_reply})
