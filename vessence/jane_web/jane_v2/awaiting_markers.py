"""Stage 3 ``[[AWAITING:<topic>]]`` marker helpers.

Stage 3 may append a trailing marker to ask the next turn to resume a
specific follow-up. The marker is routing metadata, not user-visible text, so
streaming deltas need a tiny state machine that can strip it even when it
arrives split across chunks.
"""

from __future__ import annotations

import re


_AWAITING_RE = re.compile(
    r"\[\[AWAITING:\s*([A-Za-z0-9_\-\s]{1,200})\s*\]\]\s*\Z"
)


class AwaitingDeltaStripper:
    """Strip trailing ``[[AWAITING:<topic>]]`` markers from streamed deltas."""

    _MARKER_START = "[[AWAITING:"
    _AMBIGUOUS = len(_MARKER_START) - 1

    def __init__(self) -> None:
        self._buffer = ""
        self._suppress = False

    def feed(self, chunk: str) -> str:
        if self._suppress or not chunk:
            return ""

        combined = self._buffer + chunk
        start = combined.find(self._MARKER_START)
        if start >= 0:
            self._buffer = ""
            self._suppress = True
            return combined[:start]

        if len(combined) <= self._AMBIGUOUS:
            self._buffer = combined
            return ""

        safe_len = len(combined) - self._AMBIGUOUS
        out = combined[:safe_len]
        self._buffer = combined[safe_len:]
        return out

    def flush(self) -> str:
        if self._suppress:
            self._buffer = ""
            return ""
        out = self._buffer
        self._buffer = ""
        return out


def extract_awaiting_marker(text: str) -> tuple[str, str | None]:
    """Return ``(cleaned_text, topic)`` for a trailing awaiting marker.

    Markers inside the body are ignored. Only the final non-whitespace token can
    activate a Stage 3 follow-up, which protects normal quoted text from being
    interpreted as control metadata.
    """
    if not text or "[[AWAITING:" not in text:
        return text, None
    match = _AWAITING_RE.search(text)
    if not match:
        return text, None
    topic = match.group(1).strip().replace(" ", "_")[:60] or None
    cleaned = text[:match.start()].rstrip()
    return cleaned, topic
