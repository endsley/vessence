"""Reply phrase policy for pending_action_resolver.py."""

from __future__ import annotations

import re


HIGH_PRECISION_INTERRUPT_RE = re.compile(
    r"(?:"
    r"^\s*what(?:'s|\s+is)?\s+(?:the\s+)?time\b"
    r"|^\s*what\s+time\s+is\s+it\b"
    r"|^\s*(?:tell|give)\s+me\s+the\s+time\b"
    r"|^\s*what(?:'s|\s+is)?\s+(?:the\s+)?weather\b"
    r"|^\s*(?:how(?:'s|\s+is)\s+)?(?:the\s+)?weather\b"
    r"|^\s*(?:set|start)\s+(?:a|the)?\s*timer\b"
    r"|^\s*(?:cancel|stop)\s+(?:the|my)\s+timer\b"
    r"|^\s*(?:text|message|sms|send\s+(?:a\s+)?text\s+to)\b"
    r"|^\s*tell\s+(?:\w+\s+){0,3}(?:that|hi|hello|to\s+)"
    r")",
    re.IGNORECASE,
)

CONFIRM_PHRASES = {
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "okey",
    "send it", "send it please", "do it", "go ahead", "go",
    "send", "send that", "send that please", "please send it",
    "that's right", "confirmed", "confirm", "sounds good", "perfect",
    "ship it", "looks good", "that works", "good to go", "fire away",
}

EDIT_PREFIXES = (
    "add ", "append ", "also say ", "also add ", "also ",
    "make it ", "change it to ", "change the ", "replace ",
    "say ", "reword ", "rewrite ", "rephrase ", "instead say ",
    "remove ", "drop ", "take out ", "shorten it", "lengthen it",
    "make it shorter", "make it longer", "make it more ",
    "tell them ", "tell her ", "tell him ", "tell it ",
    "actually ",
)

STAGE3_CANCEL_STRONG = {
    "cancel", "cancel that", "cancel it", "never mind", "nevermind",
    "forget it", "drop it", "abort", "scratch that", "stop",
}

CANCEL_PHRASES = {
    "no", "nope", "nah", "cancel", "cancel that", "cancel it",
    "never mind", "nevermind", "stop", "don't", "dont",
    "don't send", "dont send", "don't send it", "dont send it",
    "abort", "forget it", "drop it", "scratch that",
}

PIVOT_PHRASES = (
    "different issue", "different topic", "different subject",
    "different question", "another issue", "another topic",
    "another subject", "another question",
    "change the subject", "change the topic", "change subject",
    "switch the subject", "switch the topic", "switch subject",
    "new subject", "new topic",
    "focus on (?:a |the )?different",
    "focus on (?:a |the )?another",
    "not about that", "not about this",
    "not what i asked", "not what i meant", "not what i was asking",
    "that(?:'| a)?s not what i",
    "forget that,? (?:let(?:'| a)?s|lets|what about|how about)",
    "never mind that,? (?:let(?:'| a)?s|lets|what about|how about)",
    "(?:can we|let(?:'| a)?s|lets) (?:talk about|discuss) (?:something|a different)",
    "move on to",
    "change of subject", "change of topic",
)

PIVOT_RE = re.compile(
    r"\b(?:" + "|".join(PIVOT_PHRASES) + r")\b",
    re.IGNORECASE,
)

PUNCT_RE = re.compile(r"[.!?,\s]+$")


def is_high_precision_interrupt(text: str) -> bool:
    if not text or not text.strip():
        return False
    return bool(HIGH_PRECISION_INTERRUPT_RE.search(text.strip()))


def is_topic_pivot(text: str) -> bool:
    if not text:
        return False
    return bool(PIVOT_RE.search(text))


def normalize_reply(text: str) -> str:
    return PUNCT_RE.sub("", (text or "").strip().lower())


def is_confirm(text: str) -> bool:
    return normalize_reply(text) in CONFIRM_PHRASES


def is_cancel(text: str) -> bool:
    return normalize_reply(text) in CANCEL_PHRASES


def has_edit_prefix(normalized: str) -> bool:
    return any(normalized.startswith(prefix.rstrip().lower()) for prefix in EDIT_PREFIXES)


def is_edit_intent(text: str) -> bool:
    normalized = normalize_reply(text)
    if not normalized or normalized in CONFIRM_PHRASES or normalized in CANCEL_PHRASES:
        return False
    return has_edit_prefix(normalized)
