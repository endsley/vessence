"""Shared phrase normalization for small intent matchers."""

from __future__ import annotations

import re
from collections.abc import Container


PUNCT_RE = re.compile(r"[^\w\s']")


def normalize_phrase(text: str) -> str:
    return PUNCT_RE.sub("", text.strip().lower())


def phrase_in_set(text: str | None, phrases: Container[str]) -> bool:
    if not text:
        return False
    return normalize_phrase(text) in phrases
