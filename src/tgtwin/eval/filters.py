from __future__ import annotations

import re

URI_PATTERN = re.compile(r"\w+://\S+")
EMAIL_PATTERN = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
LINK_PATTERN = re.compile(r"(?i)\b(?:https?://|www\.|t\.me/|telegram\.me/)\S+")
PHONE_PATTERN = re.compile(r"(?<!\w)\+?\d[\d\s().-]{5,}\d(?!\w)")
LONG_TOKEN_PATTERN = re.compile(
    r"(?<!\w)(?=[A-Za-z0-9_=-]{20,}(?!\w))(?=[A-Za-z0-9_=-]*[A-Za-z_=-])[A-Za-z0-9_=-]{20,}(?!\w)"
)
LONG_NUMBER_PATTERN = re.compile(r"\d{6,}")


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def has_sensitive(text: str) -> bool:
    if URI_PATTERN.search(text) or EMAIL_PATTERN.search(text) or LINK_PATTERN.search(text):
        return True
    if LONG_TOKEN_PATTERN.search(text) or LONG_NUMBER_PATTERN.search(text):
        return True
    for match in PHONE_PATTERN.finditer(text):
        value = match.group(0)
        digits = sum(char.isdigit() for char in value)
        if digits >= 7 and any(char in "+().-" or char.isspace() for char in value):
            return True
    return False


def leaks_persona(reference: str, persona_text: str) -> bool:
    normalized_reference = normalize_text(reference)
    if len(normalized_reference) <= 6:
        return False
    return any(
        normalize_text(line) == normalized_reference for line in persona_text.splitlines()
    )
