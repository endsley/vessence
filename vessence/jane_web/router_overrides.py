"""Keyword safety-net helpers for legacy Gemma router results."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RouterKeywordOverrideResult:
    classification: str | None
    response: str | None
    changes: tuple[tuple[str | None, str], ...] = ()


def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


EMAIL_KEYWORDS = ("email", "inbox", "gmail")
READ_ACTION_KEYWORDS = ("read", "check", "see", "show", "any new", "what")
CALENDAR_KEYWORDS = ("calendar", "agenda", "schedule")
CALENDAR_READ_ACTION_KEYWORDS = (
    "read",
    "check",
    "see",
    "show",
    "what's on",
    "what is on",
    "what do i have",
    "anything on",
    "pull up",
    "look at",
    "am i busy",
    "am i free",
    "my day look",
)
CALENDAR_READ_ANCHORS = ("calendar", "agenda", "my schedule")
MESSAGE_KEYWORDS = ("text msg", "text message", "texts", "sms")
SYNC_KEYWORDS = ("sync", "resync", "re-sync")
SYNC_MESSAGE_KEYWORDS = ("message", "messages", "texts", "sms", "text")


def _is_read_email_request(msg_lower: str) -> bool:
    return _has_any(msg_lower, EMAIL_KEYWORDS) and _has_any(msg_lower, READ_ACTION_KEYWORDS)


def _is_read_calendar_request(msg_lower: str) -> bool:
    return (
        _has_any(msg_lower, CALENDAR_KEYWORDS)
        and _has_any(msg_lower, CALENDAR_READ_ACTION_KEYWORDS)
        and _has_any(msg_lower, CALENDAR_READ_ANCHORS)
    )


def _is_read_messages_request(msg_lower: str) -> bool:
    return _has_any(msg_lower, MESSAGE_KEYWORDS) and _has_any(msg_lower, READ_ACTION_KEYWORDS)


def _is_sync_messages_request(msg_lower: str) -> bool:
    return _has_any(msg_lower, SYNC_KEYWORDS) and _has_any(msg_lower, SYNC_MESSAGE_KEYWORDS)


def apply_router_keyword_overrides(
    classification: str | None,
    router_response: str | None,
    message: str | None,
) -> RouterKeywordOverrideResult:
    """Apply deterministic keyword overrides to a legacy router result."""
    msg_lower = (message or "").lower()
    changes: list[tuple[str | None, str]] = []

    if classification != "read_email" and _is_read_email_request(msg_lower):
        old = classification
        classification = "read_email"
        router_response = "read_email"
        changes.append((old, classification))

    if classification != "read_calendar" and _is_read_calendar_request(msg_lower):
        old = classification
        classification = "read_calendar"
        router_response = "today"
        changes.append((old, classification))

    if (
        classification != "read_messages"
        and classification != "sync_messages"
        and _is_read_messages_request(msg_lower)
    ):
        old = classification
        classification = "read_messages"
        router_response = "read_inbox"
        changes.append((old, classification))

    if classification != "sync_messages" and _is_sync_messages_request(msg_lower):
        old = classification
        classification = "sync_messages"
        router_response = "sync"
        changes.append((old, classification))

    return RouterKeywordOverrideResult(
        classification=classification,
        response=router_response,
        changes=tuple(changes),
    )
