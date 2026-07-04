"""Shared guard predicates for message-oriented Stage 2 handlers."""

from __future__ import annotations


ARCHITECTURE_GUARD_WORDS = (
    "architecture",
    "infrastructure",
    "pipeline",
    "handler",
    "classifier",
    "stage",
)


def contains_architecture_phrase(prompt: str) -> bool:
    p_lower = (prompt or "").lower()
    return any(word in p_lower for word in ARCHITECTURE_GUARD_WORDS)
