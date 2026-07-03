"""Low-signal memory filters used by memory retrieval."""

from __future__ import annotations

import re

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
    text = re.sub(r"\s+", " ", str(doc or "")).strip()
    topic = str((meta or {}).get("topic", "")).strip().lower()
    memory_type = str((meta or {}).get("memory_type", "")).strip().lower()
    if memory_type == "short_term_theme":
        return True
    if topic == "context_snapshot":
        return True
    protocol_hit = any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in LOW_SIGNAL_SHORT_TERM_PROTOCOL_PATTERNS
    )
    if not protocol_hit:
        return False
    if re.search(r"^\*{0,2}\s*class protocol:", text, re.IGNORECASE):
        return True
    return any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in LOW_SIGNAL_SHORT_TERM_META_PREFIX_PATTERNS
    ) or any(
        marker in text.lower()
        for marker in (
            "<class_protocol",
            "[extracted params]",
            "[current conversation state]",
            "[standing brain mode]",
        )
    )
