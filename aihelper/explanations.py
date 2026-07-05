# aihelper/explanations.py
"""
Utility functions that generate the system‑prompt for each explanation level.

The functions are deliberately tiny – they receive the *raw user question* and
return the string that should be used as the ``system`` message when talking
to Ollama.  Keeping them separate makes prompt‑engineering a first‑class
concern: you can edit the wording, add few‑shot examples, or even load the
prompt from a DB/file without touching the view logic.
"""

def get_simplified_prompt(question: str) -> str:
    """
    Return a short, jargon‑free explanation prompt.

    The assistant should talk to a beginner and avoid technical terms unless
    the user explicitly asks for them.
    """
    return (
        "You are an educational assistant. Provide a **simplified** "
        "explanation that a high‑school student can understand. "
        "Avoid jargon, keep sentences short, and use everyday analogies."
    )


def get_technical_prompt(question: str) -> str:
    """
    Return a more detailed, semi‑technical explanation.

    Target audience: someone with a basic background in the subject,
    comfortable with terminology but not an expert.
    """
    return (
        "You are an educational assistant. Provide a **technical** "
        "explanation that includes the correct terminology, relevant formulas "
        "or definitions, and brief examples. Keep the answer concise but "
        "accurate."
    )


def get_socratic_prompt(question: str) -> str:
    """
    Return a **Socratic** style prompt.

    Instead of dumping the answer, the assistant should guide the learner
    by asking a series of progressively deeper questions, encouraging the
    user to reason out the solution themselves.  The assistant may provide
    brief hints or clarifications **only when the user asks**.
    """
    return (
        "You are an educational assistant that uses the Socratic method. "
        "When given a question, respond *first* with a probing question that "
        "helps the learner think about the problem. Follow up with additional "
        "guided questions, offering hints only if the learner asks for them. "
        "The goal is to lead the learner step‑by‑step to the correct answer "
        "without stating the full solution outright."
    )


# ----------------------------------------------------------------------
# Helper: map the incoming ``explanation_level`` string to the right
# function.  Adding a new level later is as easy as dropping a new entry.
# ----------------------------------------------------------------------
PROMPT_FOR_LEVEL = {
    "simplified": get_simplified_prompt,
    "technical":  get_technical_prompt,
    "socratic":   get_socratic_prompt,
}


def system_prompt_for(level: str, question: str) -> str:
    """
    Public entry point used by ``views.helper_api``.
    *level* comes from the JSON payload (defaults to ``simplified``).  
    Raises ``KeyError`` if the level is unknown – the view will catch it
    and fall back to a safe default.
    """
    try:
        fn = PROMPT_FOR_LEVEL[level]
    except KeyError as exc:
        raise ValueError(f"Unsupported explanation level: {level!r}") from exc
    return fn(question)
