# slm/ai_bridge.py

import logging

from aihelper.explanations import system_prompt_for
from aihelper.views import _call_openai

log = logging.getLogger(__name__)


def ask_ai_one_level(
    question: str,
    level: str,
    context: str = "",
) -> str:
    """
    Calls the AI once for the requested level.

    The selected text is kept as the main question while the
    surrounding SLM content is supplied as grounding context.
    """

    try:
        context = (context or "").strip()

        system_prompt = system_prompt_for(level, question)

        grounded_prompt = (
            f"{system_prompt}\n\n"
            "GROUNDING RULES:\n"
            "- Use the provided SLM context as the primary source.\n"
            "- Explain the selected text according to its meaning "
            "in the provided SLM context.\n"
            "- Keep the explanation relevant to the selected text.\n"
            "- Do not introduce unrelated concepts.\n"
            "- Do not invent information that is not supported by "
            "the SLM context.\n"
            "- If the provided context is insufficient, state that "
            "briefly instead of guessing.\n"
        )

        messages = [
            {
                "role": "system",
                "content": grounded_prompt,
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

    except Exception as exc:  # pragma: no cover
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