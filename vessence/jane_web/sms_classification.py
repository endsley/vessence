"""Classification helpers for synced SMS messages."""

from __future__ import annotations


_REMINDER_KEYWORDS = (
    "reminder",
    "appointment",
    "scheduled",
    "alert",
    "expir",
    "renew",
    "due",
    "payment",
)
_SPAM_KEYWORDS = (
    "off",
    "deal",
    "sale",
    "promo",
    "free",
    "win",
    "click",
    "subscribe",
    "unsubscribe",
    "opt out",
    "reply stop",
)
_NOTIFICATION_KEYWORDS = ("shipped", "deliver", "tracking", "order", "package")


def _contains_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def classify_synced_message(body: str, *, is_contact: bool) -> str:
    """Return the synced_messages.msg_type value used by the Android SMS sync route."""
    if is_contact:
        return "personal"

    body_lower = (body or "").lower()
    if _contains_any_keyword(body_lower, _REMINDER_KEYWORDS):
        return "reminder"
    if _contains_any_keyword(body_lower, _SPAM_KEYWORDS):
        return "spam"
    if _contains_any_keyword(body_lower, _NOTIFICATION_KEYWORDS):
        return "notification"
    return "unknown"
