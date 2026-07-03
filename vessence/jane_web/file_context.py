"""Helpers for resolving follow-up file context."""

from __future__ import annotations


FOLLOWUP_FILE_MARKERS = (
    "delete it",
    "remove it",
    "rename it",
    "move it",
    "open it",
    "show it",
    "send it",
    "that file",
    "that image",
    "that photo",
    "that picture",
    "the image",
    "the photo",
    "the picture",
    "the file",
    "this image",
    "this photo",
    "this picture",
)


def resolve_file_context_value(
    *,
    message: str,
    file_context: str | None,
    recent_file_context: str | None,
) -> tuple[str | None, str]:
    """Return (resolved_context, source), where source is request/recent/empty."""
    if file_context:
        return file_context, "request"
    lowered = (message or "").strip().lower()
    if recent_file_context and any(marker in lowered for marker in FOLLOWUP_FILE_MARKERS):
        return recent_file_context, "recent"
    return file_context, ""
