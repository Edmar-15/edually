# slm/ai_bridge.py
import logging
from aihelper.explanations import system_prompt_for
from aihelper.views import _call_openai   # reuse the private function that actually calls Ollama

log = logging.getLogger(__name__)

def ask_ai_one_level(
    question: str,
    level: str,
    context: str = "",
) -> str:
    """
    Generate a single explanation grounded in the relevant SLM content.
    """

    try:
        context = (context or "").strip()

        system_prompt = system_prompt_for(
            level,
            question,
        )

        messages = [
            {
                "role": "system",
                "content": (
                    f"{system_prompt}\n\n"
                    "GROUNDING RULES:\n"
                    "- Use the provided SLM context as the primary source.\n"
                    "- Explain the selected text according to its meaning "
                    "in that SLM context.\n"
                    "- Do not introduce unrelated concepts.\n"
                    "- Do not rely on outside information when the SLM "
                    "context provides the needed meaning.\n"
                    "- If the context is insufficient, say so briefly "
                    "instead of inventing details."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Selected text:\n"
                    f"{question}\n\n"
                    f"Relevant SLM content:\n"
                    f"{context}"
                ),
            },
        ]

        return _call_openai(messages)

    except Exception as exc:
        log.error(
            "AI failed for level %s: %s",
            level,
            exc,
        )

        return (
            f"[{level.title()} fallback] "
            f"Unable to generate an explanation for "
            f"“{question}”."
        )
