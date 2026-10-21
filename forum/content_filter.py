import re
import unicodedata


BAD_WORDS = {
    # Filipino
    "gago", "gaga", "tanga", "bobo", "boang",
    "ulol", "bwisit", "buwisit", "hayop",
    "pakyu", "pisti", "putang ina", "putangina",
    "pota", "pota ka", "siraulo", "sira ulo",
    "takusa", "bastos", "tang ina",
    "tae", "taena", "urupak",
    "kupal", "hinampak",

    # English
    "stupid", "idiot", "dumb", "moron",
    "loser", "fool",
    "asshole", "jerk", "shut up", "damn",
    "crap", "hell", "bitch", "whore",
    "slut", "freak", "retard", "idiotic",
    "stupid ka",

    # Additional profanity
    "fuck", "fucking", "motherfucker",
    "shit", "bullshit",
}

BAD_WORD_WARNING = (
    "Your message contains inappropriate language. "
    "Please revise it before posting."
)

SPAM_WARNING = (
    "Your message appears to contain spam or excessive "
    "random symbols. Please revise it before posting."
)

# Common character substitutions
CHAR_MAP = str.maketrans({
    "@": "a",
    "4": "a",
    "0": "o",
    "3": "e",
    "1": "i",
    "$": "s",
    "5": "s",
})

# Detect punctuation inserted inside words
SEPARATOR_PATTERN = re.compile(
    r"(?<=[a-z0-9])[._*!~-]+(?=[a-z0-9])"
)


def normalize_text(text):
    """Normalize text for consistent word matching."""
    text = unicodedata.normalize(
        "NFKC", text or ""
    ).casefold()

    text = text.translate(CHAR_MAP)

    return re.sub(r"[^a-z0-9]+", " ", text).strip()


# Compile patterns once
BAD_WORD_PATTERNS = tuple(
    re.compile(
        rf"(?<![a-z0-9]){re.escape(normalize_text(word))}"
        rf"(?![a-z0-9])"
    )
    for word in BAD_WORDS
)

# Detect profanity separated by spaces:
# "f u c k", "b o b o", etc.
SPACED_BAD_WORD_PATTERNS = tuple(
    re.compile(
        r"(?<![a-z0-9])"
        + r"\s+".join(
            re.escape(char)
            for char in normalize_text(word)
        )
        + r"(?![a-z0-9])"
    )
    for word in BAD_WORDS
    if " " not in normalize_text(word)
    and 4 <= len(normalize_text(word)) <= 12
)

def contains_bad_words(text):
    """Detect prohibited words and common obfuscations."""
    if not text:
        return False

    prepared = unicodedata.normalize(
        "NFKC", text
    ).casefold().translate(CHAR_MAP)

    # Normal text
    normal = normalize_text(prepared)

    # Text with punctuation inserted between letters
    compact = normalize_text(
        SEPARATOR_PATTERN.sub("", prepared)
    )

    return (
        any(
            pattern.search(candidate)
            for candidate in (normal, compact)
            for pattern in BAD_WORD_PATTERNS
        )
        or any(
            pattern.search(normal)
            for pattern in SPACED_BAD_WORD_PATTERNS
        )
    )


def contains_spam(text):
    """
    Detect obvious spam while avoiding false positives
    in common programming examples and URLs.
    """
    text = (text or "").strip()

    if not text:
        return False

    # Ignore recognizable URLs and simple quoted-string
    # function calls for spam detection only.
    # Profanity is still checked against the original text.
    scan_text = re.sub(
        r"\bhttps?://[^\s]+",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    scan_text = re.sub(
        r"""\b[A-Za-z_]\w*\(\s*(?:"[^"\n]*"|'[^'\n]*')\s*\)""",
        " ",
        scan_text,
    )

    characters = [
        char for char in scan_text
        if not char.isspace()
    ]

    # Rule 1: Long sequences containing only symbols.
    if len(characters) >= 12:
        if all(not char.isalnum() for char in characters):
            return True

    # Rule 2: Long suspicious tokens mixing
    # numbers, letters, and repeated symbols.
    for token in scan_text.split():
        if len(token) < 20:
            continue

        has_numbers = bool(re.search(r"\d{4,}", token))
        has_letters = bool(re.search(r"[a-zA-Z]{5,}", token))
        has_symbol_run = bool(re.search(r"[^\w\s]{5,}", token))

        if has_numbers and has_letters and has_symbol_run:
            return True

    # Rule 3: Short messages dominated by symbols.
    if len(scan_text.split()) <= 2 and len(characters) >= 20:
        symbol_count = sum(
            not char.isalnum()
            for char in characters
        )

        symbol_ratio = symbol_count / len(characters)

        if symbol_count >= 8 and symbol_ratio >= 0.35:
            return True

    return False


def check_content(text):
    """Return a warning when content violates a rule."""
    if contains_bad_words(text):
        return BAD_WORD_WARNING

    if contains_spam(text):
        return SPAM_WARNING

    return None
