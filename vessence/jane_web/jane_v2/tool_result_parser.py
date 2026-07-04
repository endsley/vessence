r"""Shared parser for the [TOOL_RESULT:{json}] prefix Android prepends to
follow-up turns when a phone tool completes/fails/cancels.

The legacy approach used a regex (`\[TOOL_RESULT:\{[^}]*\}\]`), which
silently fails on any tool result containing nested JSON objects — i.e.
basically every real result, since payloads have a `"data": {...}` block.
A miss leaves the entire JSON blob in the prompt that reaches the Stage 1
classifier, polluting the embedding with words like "messages",
"notifications", "tool", "completed" and producing wildly wrong votes.

This module uses brace-counting + string-escape tracking — the same
technique as `ToolMarkerExtractor` — so nested objects and string values
containing `}]` are parsed correctly. Any malformed marker stops the scan
and the remaining text (with the bad marker intact) is returned as the
cleaned message, so failures surface visibly rather than being dropped.
"""

from __future__ import annotations

import json

from jane_web.client_tool_json import find_json_object_end

_TOOL_RESULT_OPEN = "[TOOL_RESULT:"
_TOOL_RESULT_CLOSE = "]"


def _leading_tool_result_marker_bounds(cleaned: str) -> tuple[int, int, int] | None:
    stripped = cleaned.lstrip()
    if not stripped.startswith(_TOOL_RESULT_OPEN):
        return None
    json_start = len(cleaned) - len(stripped) + len(_TOOL_RESULT_OPEN)
    while json_start < len(cleaned) and cleaned[json_start] in " \t":
        json_start += 1
    if json_start >= len(cleaned) or cleaned[json_start] != "{":
        return None
    json_end = find_json_object_end(cleaned, json_start)
    if json_end is None:
        return None
    marker_end = json_end
    while marker_end < len(cleaned) and cleaned[marker_end] in " \t":
        marker_end += 1
    if marker_end >= len(cleaned) or cleaned[marker_end] != _TOOL_RESULT_CLOSE:
        return None
    return json_start, json_end, marker_end


def extract_tool_results(user_message: str) -> tuple[str, list[dict]]:
    """Strip leading `[TOOL_RESULT:{json}]` markers from a user message.

    Returns ``(clean_message, list_of_parsed_results)``.
    """
    results: list[dict] = []
    cleaned = user_message or ""
    while True:
        bounds = _leading_tool_result_marker_bounds(cleaned)
        if bounds is None:
            break
        json_start, json_end, marker_end = bounds
        try:
            payload = json.loads(cleaned[json_start:json_end])
        except Exception:
            break
        if not isinstance(payload, dict):
            break
        results.append(payload)
        cleaned = cleaned[marker_end + 1:].lstrip()
    return cleaned, results


def strip_tool_result_prefix(user_message: str) -> str:
    """Convenience wrapper for callers that only need the cleaned text."""
    cleaned, _ = extract_tool_results(user_message)
    return cleaned
