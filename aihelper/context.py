import re
from html import unescape

from bs4 import BeautifulSoup
from django.db.models import Q

from slm.models import Subject, Module, PersonalMaterial


# Avoid attaching learning material unless it is a plausible match.
SLM_RELEVANCE_THRESHOLD = 0.18

# Limit how much content is sent from each source.
MAX_CONTEXT_CHARS = 7000

MAX_SOURCES = 5


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "do",
    "does",
    "for",
    "from",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "me",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "you",
    "your",
}


def html_to_text(html: str) -> str:
    """
    Convert extracted HTML into clean plain text.

    The SLM extractor stores HTML, but the AI should receive the actual
    learning content rather than markup.
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    for element in soup(["script", "style", "noscript"]):
        element.decompose()

    text = soup.get_text(" ", strip=True)
    text = unescape(text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_text(text: str) -> str:
    """
    Normalize text for relevance comparison.
    """
    text = (text or "").lower()

    text = re.sub(r"[^a-z0-9\s]", " ", text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def meaningful_words(text: str) -> set[str]:
    """
    Return useful words from a question/title/content.
    """
    normalized = normalize_text(text)

    return {
        word
        for word in normalized.split()
        if len(word) >= 3 and word not in STOP_WORDS
    }


def _score_text(question: str, title: str, content: str) -> float:
    """
    Calculate a lightweight local relevance score.

    This is deliberately NOT an AI call.

    We first determine whether the user's question has a meaningful
    relationship to an accessible SLM source. Only then do we send
    selected content to OpenAI.
    """
    question_words = meaningful_words(question)

    if not question_words:
        return 0.0

    title_words = meaningful_words(title)
    content_words = meaningful_words(content)

    if not content_words:
        return 0.0

    content_overlap = len(question_words & content_words) / len(question_words)

    title_overlap = 0.0

    if title_words:
        title_overlap = len(question_words & title_words) / len(question_words)

    normalized_question = normalize_text(question)
    normalized_title = normalize_text(title)

    phrase_bonus = 0.0

    if (
        normalized_question
        and len(normalized_question) >= 8
        and normalized_question in normalize_text(content)
    ):
        phrase_bonus = 0.35

    if (
        normalized_question
        and len(normalized_question) >= 5
        and normalized_question in normalized_title
    ):
        phrase_bonus = max(phrase_bonus, 0.25)

    score = (
        (content_overlap * 0.60)
        + (title_overlap * 0.25)
        + (phrase_bonus * 0.15)
    )

    return min(score, 1.0)


def accessible_subjects_for_user(user):
    """
    Return the same subject visibility boundary used by the SLM app.

    Student:
        - non-archived subjects
        - matching the student's year level

    Teacher:
        - non-archived subjects authored by that teacher

    Other authenticated users:
        - non-archived subjects
    """
    queryset = (
        Subject.objects
        .filter(is_archived=False)
        .select_related("author")
    )

    if getattr(user, "is_teacher_member", False):
        return queryset.filter(author=user)

    if getattr(user, "is_student_member", False):
        year_label = getattr(user, "year_level", None) or ""
        match = re.search(r"\d+", year_label)

        if not match:
            return queryset.none()

        return queryset.filter(year=match.group())

    return queryset


def accessible_modules_for_user(user):
    """
    Return only modules belonging to subjects the user can actually see.
    """
    subjects = accessible_subjects_for_user(user)

    return (
        Module.objects
        .filter(
            subject__in=subjects,
            is_archived=False,
        )
        .select_related("subject")
        .exclude(extracted_html="")
    )


def accessible_personal_materials_for_user(user):
    """
    Match the existing SLM personal-material visibility rules:

        - user's own materials
        - public materials from other users

    Archived materials are excluded.
    """
    return (
        PersonalMaterial.objects
        .filter(
            Q(author=user)
            | Q(visibility=PersonalMaterial.Visibility.PUBLIC),
            is_archived=False,
        )
        .select_related("author")
        .exclude(extracted_html="")
    )


def find_relevant_slm_context(user, question: str) -> dict:
    """
    Search the SLM content available to the current user.

    Returns:

        {
            "found": bool,
            "sources": [...],
            "context": "..."
        }

    Only searches content the user is allowed to access.
    """
    question = (question or "").strip()

    if not question:
        return {
            "found": False,
            "sources": [],
            "context": "",
        }

    candidates = []

    for module in accessible_modules_for_user(user):
        content = html_to_text(module.extracted_html)

        if not content:
            continue

        title = (
            f"{module.subject.subject_code} "
            f"{module.subject.subject_name} "
            f"Module {module.module_number} "
            f"{module.module_name}"
        )

        score = _score_text(
            question=question,
            title=title,
            content=content,
        )

        if score >= SLM_RELEVANCE_THRESHOLD:
            candidates.append(
                {
                    "kind": "module",
                    "score": score,
                    "title": module.module_name,
                    "subject_code": module.subject.subject_code,
                    "subject_name": module.subject.subject_name,
                    "module_number": module.module_number,
                    "content": content,
                    "object_id": module.id,
                }
            )

    for material in accessible_personal_materials_for_user(user):
        content = html_to_text(material.extracted_html)

        if not content:
            continue

        score = _score_text(
            question=question,
            title=material.title,
            content=content,
        )

        if score >= SLM_RELEVANCE_THRESHOLD:
            candidates.append(
                {
                    "kind": "personal_material",
                    "score": score,
                    "title": material.title,
                    "subject_code": None,
                    "subject_name": None,
                    "module_number": None,
                    "content": content,
                    "object_id": material.id,
                }
            )

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    candidates = candidates[:MAX_SOURCES]

    if not candidates:
        return {
            "found": False,
            "sources": [],
            "context": "",
        }

    context_parts = []
    source_metadata = []

    for index, item in enumerate(candidates, start=1):
        content = item["content"][:MAX_CONTEXT_CHARS]

        if item["kind"] == "module":
            source_name = (
                f"{item['subject_code']} – "
                f"{item['subject_name']} – "
                f"Module {item['module_number']}: "
                f"{item['title']}"
            )
        else:
            source_name = f"Personal Material: {item['title']}"

        context_parts.append(
            "\n".join(
                [
                    f"[SOURCE {index}]",
                    f"Type: {item['kind']}",
                    f"Title: {source_name}",
                    f"Relevance score: {item['score']:.3f}",
                    "",
                    content,
                    f"[/SOURCE {index}]",
                ]
            )
        )

        source_metadata.append(
            {
                "type": item["kind"],
                "id": item["object_id"],
                "title": item["title"],
                "subject_code": item["subject_code"],
                "subject_name": item["subject_name"],
                "module_number": item["module_number"],
                "relevance": round(item["score"], 3),
            }
        )

    return {
        "found": True,
        "sources": source_metadata,
        "context": "\n\n".join(context_parts),
    }