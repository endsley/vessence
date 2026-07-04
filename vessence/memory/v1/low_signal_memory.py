"""Low-signal memory filters used by memory retrieval."""

from __future__ import annotations

import re

from memory.v1.conversation_text import compact_whitespace

LOW_SIGNAL_SHARED_PREFIXES = (
    "prompt list verbatim",
    "logged in with google",
    "user logged in with google account",
    "shortcut: yolo",
    "ui includes yolo shortcut",
    "main pre-response latency points",
    "still here. what do you want to work on next?",
    "noise_check_ok",
)
LOW_SIGNAL_SHORT_TERM_META_PREFIX_PATTERNS = (
    r"^i need clarification\b",
    r"^there(?:'|’)s no conversation turn to summarize\b",
    r"^no action needed\b",
    r"^i notice there(?:'|’)s a mismatch here\b",
)
LOW_SIGNAL_SHORT_TERM_PROTOCOL_PATTERNS = (
    r"^\[context snapshot\b",
    r"^\*{0,2}\s*class protocol:",
    r"<class_protocol\b",
    r"\[extracted params\]",
    r"\[current conversation state\]",
    r"\[standing brain mode\]",
    r"\bclass protocol metadata\b",
    r"\bdocumentation \(belongs in code/config\)\b",
    r"\bprovided (?:class )?protocol\b",
    r"\bclass protocol you provided\b",
    r"\bnew turn.*class protocol metadata\b",
)
LOW_SIGNAL_SHORT_TERM_INLINE_MARKERS = (
    "<class_protocol",
    "[extracted params]",
    "[current conversation state]",
    "[standing brain mode]",
)
CLASS_PROTOCOL_HEADER_RE = r"^\*{0,2}\s*class protocol:"


def _matches_any(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def has_inline_protocol_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in LOW_SIGNAL_SHORT_TERM_INLINE_MARKERS)


def is_low_signal_short_term_protocol_text(text: str) -> bool:
    if not _matches_any(LOW_SIGNAL_SHORT_TERM_PROTOCOL_PATTERNS, text):
        return False
    if re.search(CLASS_PROTOCOL_HEADER_RE, text, re.IGNORECASE):
        return True
    return _matches_any(LOW_SIGNAL_SHORT_TERM_META_PREFIX_PATTERNS, text) or has_inline_protocol_marker(text)


def is_low_signal_shared_memory(doc: str, meta: dict | None) -> bool:
    text = str(doc or "").strip().lower()
    if not text:
        return True
    if any(text.startswith(prefix) for prefix in LOW_SIGNAL_SHARED_PREFIXES):
        return True
    topic = str((meta or {}).get("topic", "")).lower()
    if topic in {"prompt_list", "audit_flow", "performance_logs"}:
        return True
    return False


def is_low_signal_short_term_memory(doc: str, meta: dict | None) -> bool:
    text = compact_whitespace(doc)
    topic = str((meta or {}).get("topic", "")).strip().lower()
    memory_type = str((meta or {}).get("memory_type", "")).strip().lower()
    if memory_type == "short_term_theme":
        return True
    if topic == "context_snapshot":
        return True
    return is_low_signal_short_term_protocol_text(text)
