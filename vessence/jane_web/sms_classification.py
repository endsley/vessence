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


def classify_synced_message(body: str, *, is_contact: bool) -> str:
    """Return the synced_messages.msg_type value used by the Android SMS sync route."""
    if is_contact:
        return "personal"

    body_lower = (body or "").lower()
    if any(keyword in body_lower for keyword in _REMINDER_KEYWORDS):
        return "reminder"
    if any(keyword in body_lower for keyword in _SPAM_KEYWORDS):
        return "spam"
    if any(keyword in body_lower for keyword in _NOTIFICATION_KEYWORDS):
        return "notification"
    return "unknown"
