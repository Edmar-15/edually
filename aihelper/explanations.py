def get_simplified_prompt(question: str) -> str:
    """
    Return a *system* prompt for a **simplified** answer.

    The model receives the raw ``question`` in the system message so it can
    tailor the tone without having to guess the topic from the user message
    alone.  The assistant must answer in **Markdown** and keep the language
    accessible to a high‑school student.
    """
    # NOTE: ``question`` is interpolated only for context – we never expose it
    # to the model as a “user” turn.
    return (
        "You are an educational AI tutor.  **Goal:** give a short, jargon‑free "
        "explanation that a high‑school student can understand.\n"
        "• Use plain language, everyday analogies and concrete examples.\n"
        "• Keep sentences under 25 words.\n"
        "• Respond *only* in Markdown – no HTML tags.\n"
        f"**Question:** {question}"
    )


def get_technical_prompt(question: str) -> str:
    """
    Return a *system* prompt for a **technical** answer.

    The user already knows the basics, so we can use proper terminology,
    formulas, and short examples.  Markdown formatting is required.
    """
    return (
        "You are an educational AI tutor.  **Goal:** give a concise but technically "
        "accurate answer.\n"
        "• Use correct terminology and include any relevant formulae.\n"
        "• Provide a brief example or two if it helps clarity.\n"
        "• Output **Markdown only**.\n"
        f"**Question:** {question}"
    )


def get_socratic_prompt(question: str) -> str:
    """
    Return a *system* prompt for a **Socratic** style interaction.

    The model must *only* ask a single probing question, wait for the user’s
    response, and continue the dialogue.  If the user asks for a hint the
    assistant may give a short clue; only when the user explicitly says
    “I give up” (or an equivalent phrase) should the assistant reveal the
    full solution.  All answers must be in Markdown.
    """
    return (
        "You are an educational AI tutor that follows the Socratic method.\n"
        "• **Never** give the final answer right away.\n"
        "• Respond to the user’s question with **one** probing question that "
        "helps them think about the problem.\n"
        "• After the user replies, ask a follow‑up question that deepens the "
        "reasoning.  Continue this pattern.\n"
        "• If the user explicitly requests a *hint*, give a short clue; "
        "if they say *I give up* or ask for the solution, provide the full "
        "answer.\n"
        "• Output **Markdown only**.\n"
        f"**Question:** {question}"
    )


# ----------------------------------------------------------------------
# Mapping from ``explanation_level`` → prompt‑builder.
# ----------------------------------------------------------------------
PROMPT_FOR_LEVEL = {
    "simplified": get_simplified_prompt,
    "technical":  get_technical_prompt,
    "socratic":  get_socratic_prompt,
}


def system_prompt_for(level: str, question: str) -> str:
    """
    Public entry point used by ``views.helper_api``.

    * ``level`` – comes from the JSON payload; defaults to ``simplified`` in the
      view.\n
    * ``question`` – the raw user question, injected into the system prompt.\n
    * Raises :class:`ValueError` if the level is unknown.\n
    """
    try:
        fn = PROMPT_FOR_LEVEL[level]
    except KeyError as exc:
        raise ValueError(f"Unsupported explanation level: {level!r}") from exc
    return fn(question)