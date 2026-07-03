"""Pure parsing helpers for the TODO-list Stage 2 handler."""
from __future__ import annotations

import re


_ADD_PATTERNS = [
    re.compile(r"\badd\b.*\b(?:to.?do|list|task)", re.I),
    re.compile(r"\badd\b.*\b(?:to my|for my|under)", re.I),
    re.compile(r"\bput\b.*\bon my\b.*\blist", re.I),
    re.compile(r"\badd a task\b", re.I),
    re.compile(r"\badd\b.{1,80}(?:urgent|clinic|home|student)", re.I),
]
_REMOVE_PATTERNS = [
    re.compile(r"\b(?:remove|delete|cross off|mark.?done|check off|scratch)\b", re.I),
    re.compile(r"\btake\b.*\boff\b.*\blist", re.I),
]


def detect_edit_intent(prompt: str) -> str | None:
    """Return 'add', 'remove', or None."""
    for pat in _ADD_PATTERNS:
        if pat.search(prompt):
            return "add"
    for pat in _REMOVE_PATTERNS:
        if pat.search(prompt):
            return "remove"
    return None


_PLACEHOLDER_ITEM_RE = re.compile(
    r"^(?:a|an|the|new)?\s*"
    r"(?:item|task|todo|to-do|thing|something)"
    r"(?:\s+(?:item|task|todo|to-do|thing))?$",
    re.I,
)


def is_placeholder_item_text(text: str | None) -> bool:
    """True when the extracted add text is a slot placeholder, not a task."""
    if not text:
        return False
    cleaned = re.sub(r"[.?!,;:]+$", "", text.strip())
    return bool(_PLACEHOLDER_ITEM_RE.match(cleaned))


def extract_item_text(prompt: str, edit_type: str) -> str | None:
    """Try to extract the item text from an add/remove request."""
    cleaned = prompt.strip()
    if edit_type == "add":
        match = re.search(r"""['"\u2018\u2019\u201c\u201d](.+?)['"\u2018\u2019\u201c\u201d]""", cleaned)
        if match:
            return match.group(1).strip()
        match = re.search(
            r"\b(?:the\s+)?(?:item|task|thing)\s+(?:is|should\s+be|would\s+be)\s+(.+)$",
            cleaned, re.I,
        )
        if match:
            candidate = match.group(1).strip().rstrip(".!?,")
            if candidate and not is_placeholder_item_text(candidate):
                return candidate
        match = re.search(r":\s*(.+)$", cleaned)
        if match:
            return match.group(1).strip()
        match = re.search(r"\badd\s+(.+?)(?:\s+to\s+(?:my|the)\b|\s+(?:under|for)\s+)", cleaned, re.I)
        if match:
            return match.group(1).strip()
        match = re.search(r"\badd\s+(.+)", cleaned, re.I)
        if match:
            text = match.group(1).strip()
            text = re.sub(r"\s+(?:to|on|under|for)\s+(?:my|the)\s+.*$", "", text, flags=re.I)
            return text if text and not is_placeholder_item_text(text) else None
    elif edit_type == "remove":
        match = re.search(r"""['"\u2018\u2019\u201c\u201d](.+?)['"\u2018\u2019\u201c\u201d]""", cleaned)
        if match:
            return match.group(1).strip()
        match = re.search(
            r"\b(?:remove|delete|cross off|check off|scratch)\s+(?:the\s+)?(.+?)(?:\s+(?:item|from|off)\b|$)",
            cleaned,
            re.I,
        )
        if match:
            text = match.group(1).strip()
            text = re.sub(r"\s+(?:from|on|off)\s+(?:my|the)\s+.*$", "", text, flags=re.I)
            return text if text else None
    return None
