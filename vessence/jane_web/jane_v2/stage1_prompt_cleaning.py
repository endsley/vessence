"""Prompt cleanup helpers for Stage 1 classification."""

from __future__ import annotations

import re

from jane_web.jane_v2.tool_result_parser import strip_tool_result_prefix


_SYS_PREFIX_RE = re.compile(
    r"\[(SMS SEND REQUEST|PHONE TOOL RESULTS)[^\]]*\].*?\[END\s+[^\]]+\]\s*",
    re.DOTALL | re.IGNORECASE,
)
_SYS_TAIL_RE = re.compile(
    r"\n*\[(SMS SEND REQUEST|PHONE TOOL RESULTS)[\s\S]*$",
    re.IGNORECASE,
)
_SUBJECT_CHANGE_RE = re.compile(
    r"^\s*(?:"
    r"(?:i(?:'| a)?d\s+like\s+to\s+"
    r"|i\s+would\s+like\s+to\s+"
    r"|i\s+want\s+to\s+"
    r"|i\s+wanna\s+"
    r"|(?:let(?:'| a)?s|lets)\s+"
    r"|can\s+we\s+"
    r"|can\s+you\s+"
    r"|please\s+)?"
    r"(?:change|switch|shift|move|go)\s+(?:the\s+)?(?:subject|topic|conversation)\s+to\s+"
    r"|"
    r"(?:let(?:'| a)?s|lets)\s+(?:talk\s+about|discuss)\s+"
    r"|"
    r"(?:switching|changing)\s+(?:the\s+)?(?:subject|topic)(?:\s+to)?\s+"
    r")",
    re.IGNORECASE,
)
_PLURAL_FIXUPS = {
    r"\bweathers\b": "weather",
}


def strip_stage1_system_markers(prompt: str) -> str:
    """Strip system/result blocks so Stage 1 sees the user's actual words."""
    cleaned = strip_tool_result_prefix(prompt)
    cleaned = _SYS_PREFIX_RE.sub("", cleaned)
    cleaned = _SYS_TAIL_RE.sub("", cleaned)
    cleaned = _SUBJECT_CHANGE_RE.sub("", cleaned, count=1)
    for pat, repl in _PLURAL_FIXUPS.items():
        cleaned = re.sub(pat, repl, cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or prompt
