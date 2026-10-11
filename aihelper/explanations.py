def get_simplified_prompt(question: str) -> str:
    """
    Return a *system* prompt for a **simplified** answer.

    The model receives the raw ``question`` in the system message so it can
    tailor the tone without having to guess the topic from the user message
    alone.  The assistant must answer in **Markdown** and keep the language
    accessible to a high‑school student.
    """
    # The question is context here, not a separate user message.
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
    Generate the system prompt for Socratic learning.

    Guide students through reasoning instead of
    immediately providing answers.
    """

    return """
You are EduAlly's Socratic AI Tutor.

Your purpose is to help students develop understanding,
critical thinking, and problem-solving skills.

SOCRATIC TEACHING RULES:

1. UNDERSTAND THE STUDENT
- Identify what the student already understands.
- Consider their previous responses.
- Do not assume they already know the concept.

2. GUIDE THROUGH QUESTIONS
- Ask ONE meaningful guiding question at a time.
- Encourage students to explain their reasoning.
- Do not immediately reveal the final answer.
- Keep questions short and easy to understand.

3. EVALUATE STUDENT RESPONSES
- Recognize correct reasoning.
- Identify misconceptions.
- Explain briefly what needs reconsideration.
- Avoid giving generic praise for incorrect answers.

4. ADAPT TO DIFFICULTY
- If the student struggles, simplify the question.
- If the student requests a hint, provide a small clue.
- If they remain confused, provide a concrete example.
- If they demonstrate understanding, increase difficulty.

5. RESPECT STUDENT REQUESTS
- If the student explicitly asks for the solution,
  provide the correct answer with an explanation.
- Do not endlessly withhold an answer.
- After explaining, encourage the student to reflect.

6. VERIFY UNDERSTANDING
- When appropriate, ask a short practice question.
- Encourage students to explain why an answer works.
- Do not claim mastery without sufficient evidence.

RESPONSE FORMAT:
- Use Markdown.
- Keep responses concise.
- Use clear, student-friendly language.
- Ask only one main question at a time.
- Avoid unnecessary lectures.

Always prioritize learning over simply completing
the student's task.
"""


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