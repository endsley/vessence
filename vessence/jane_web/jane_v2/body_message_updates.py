"""Chat body message update helpers for the v2 pipeline."""

from __future__ import annotations

from typing import Any


def copy_body_with_message(
    body: Any,
    message: str,
    *,
    mutate_without_copy: bool = False,
) -> Any:
    """Return a chat body with `message` replaced.

    Pydantic v2 uses `model_copy`; Pydantic v1 uses `copy`. The v2 pipeline
    historically mutates bare test doubles when neither API exists, while
    Stage 3 injection wrappers only require the copy APIs.
    """
    try:
        return body.model_copy(update={"message": message})
    except AttributeError:
        if hasattr(body, "copy"):
            return body.copy(update={"message": message})
        if mutate_without_copy:
            setattr(body, "message", message)
            return body
        raise


def append_body_message(body: Any, extra: str) -> Any:
    """Append `extra` to `body.message`, preserving legacy mutable fallback."""
    if not extra:
        return body
    new_message = (getattr(body, "message", "") or "") + extra
    return copy_body_with_message(body, new_message, mutate_without_copy=True)


def prepend_body_message(body: Any, extra: str) -> Any:
    """Prepend `extra` above `body.message`, inserting one blank line if needed."""
    if not extra:
        return body
    existing = getattr(body, "message", "") or ""
    sep = "\n\n" if existing and not extra.endswith("\n\n") else ""
    new_message = extra + sep + existing
    return copy_body_with_message(body, new_message, mutate_without_copy=True)
