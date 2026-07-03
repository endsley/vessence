"""Memory summary normalization for Jane context construction."""

from __future__ import annotations


NO_RELEVANT_CONTEXT = "No relevant context found."


def normalize_memory_summary(
    memory_summary: str,
    fallback_summary: str | None = None,
    *,
    max_chars: int = 6000,
) -> str:
    summary = (memory_summary or "").strip()
    if summary and summary != NO_RELEVANT_CONTEXT:
        return summary[:max_chars]
    fallback = (fallback_summary or "").strip()
    if fallback and fallback != NO_RELEVANT_CONTEXT:
        return fallback[:max_chars]
    return ""
