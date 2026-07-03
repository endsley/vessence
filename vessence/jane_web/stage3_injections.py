"""Helpers for removing Stage 3 brain-only prompt injections before persistence."""

from __future__ import annotations

import re


_STAGE3_CLASS_PROTOCOL_RE = re.compile(
    r"<class_protocol[^>]*>.*?</class_protocol>\s*", re.DOTALL
)
_STAGE3_EXTRACTED_PARAMS_RE = re.compile(
    r"\[EXTRACTED PARAMS\].*?(?=\n\n|\Z)", re.DOTALL
)
_STAGE3_CONV_STATE_RE = re.compile(
    r"\[CURRENT CONVERSATION STATE\].*?\[END CURRENT CONVERSATION STATE\]\s*",
    re.DOTALL,
)
_STAGE3_VOICE_HINT_RE = re.compile(
    r"\(voice request — .*?\)\s*", re.DOTALL
)


def strip_stage3_injections(message: str) -> str:
    """Remove Stage 3 context blocks that should not be saved as user text."""
    if not message:
        return message
    text = _STAGE3_CLASS_PROTOCOL_RE.sub("", message)
    text = _STAGE3_EXTRACTED_PARAMS_RE.sub("", text)
    text = _STAGE3_CONV_STATE_RE.sub("", text)
    text = _STAGE3_VOICE_HINT_RE.sub("", text)
    return text.strip()
