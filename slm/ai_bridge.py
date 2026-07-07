# slm/ai_bridge.py
import logging
from aihelper.explanations import system_prompt_for
from aihelper.views import _call_ollama   # reuse the private function that actually calls Ollama

log = logging.getLogger(__name__)

def ask_ai_one_level(question: str, level: str) -> str:
    """
    Calls the AI **once** for the requested level (``simplified`` or ``technical``)
    and returns the raw HTML answer.
    """
    try:
        system_prompt = system_prompt_for(level, question)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": question},
        ]
        return _call_ollama(messages)
    except Exception as exc:                     # pragma: no cover
        log.error("Ollama failed for level %s: %s", level, exc)
        return f"[{level.title()} fallback] Here is a brief answer to “{question}”."
