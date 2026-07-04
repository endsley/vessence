"""Prompt context helpers for server-side email and calendar reads."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EmailReadQuery:
    limit: int
    query: str


def _email_limit_from_router_response(
    email_resp: str,
    *,
    default_limit: int,
    max_limit: int,
) -> int:
    limit_match = re.search(r"\b(\d+)\b", email_resp)
    if not limit_match:
        return default_limit
    return min(int(limit_match.group(1)), max_limit)


def _email_sender_query_from_router_response(email_resp: str, default_query: str) -> str:
    from_match = re.search(r"from:(\S+)", email_resp)
    if not from_match:
        return default_query
    return f"from:{from_match.group(1)}"


def email_read_query_from_router_response(
    router_response: str | None,
    *,
    default_limit: int = 10,
    max_limit: int = 20,
    default_query: str = "is:unread",
) -> EmailReadQuery:
    email_resp = (router_response or "").lower().strip()
    return EmailReadQuery(
        limit=_email_limit_from_router_response(
            email_resp,
            default_limit=default_limit,
            max_limit=max_limit,
        ),
        query=_email_sender_query_from_router_response(email_resp, default_query),
    )


def email_task_context(emails: list[dict[str, Any]]) -> str:
    if emails:
        return (
            "[EMAIL INBOX DATA \u2014 fetched server-side]\n"
            + json.dumps(emails, indent=2, default=str)
            + "\n[END EMAIL INBOX DATA]"
        )
    return "[EMAIL INBOX DATA]\nNo unread emails found.\n[END EMAIL INBOX DATA]"


def email_task_credentials_error_context(error: BaseException) -> str:
    return f"[EMAIL ERROR]\nGmail not set up: {error}\n[END EMAIL ERROR]"


def email_task_error_context(error: BaseException) -> str:
    return f"[EMAIL ERROR]\nFailed to fetch emails: {error}\n[END EMAIL ERROR]"


def email_delegate_context(emails: list[dict[str, Any]]) -> str:
    if emails:
        return (
            "\n\n[EMAIL INBOX DATA \u2014 fetched server-side just now]\n"
            + json.dumps(emails, indent=2, default=str)
            + "\n[END EMAIL INBOX DATA]\n\n"
            "Summarize these emails for the user. Triage: personal/important emails first, "
            "skip spam/promos. Quote sender and subject. If the user asked about a specific "
            "sender or count, honor that."
        )
    return (
        "\n\n[EMAIL INBOX DATA \u2014 fetched server-side just now]\n"
        "No unread emails found.\n"
        "[END EMAIL INBOX DATA]\n\n"
        "Tell the user their inbox is clear."
    )


def email_delegate_credentials_error_context(error: BaseException) -> str:
    return (
        "\n\n[EMAIL ERROR]\n"
        f"Gmail is not set up yet: {error}\n"
        "Tell the user they need to sign in with Google on the Vessence web UI "
        "to enable email access. The sign-in page is at their Jane web URL.\n"
        "[END EMAIL ERROR]"
    )


def email_delegate_error_context(error: BaseException) -> str:
    return (
        "\n\n[EMAIL ERROR]\n"
        f"Failed to fetch emails: {error}\n"
        "Apologize and suggest trying again.\n"
        "[END EMAIL ERROR]"
    )


def calendar_range_from_router_response(router_response: str | None, message: str) -> str:
    cal_range = (router_response or "today").strip().lower() or "today"
    return _calendar_range_override_from_message(message) or cal_range


def _calendar_range_override_from_message(message: str) -> str | None:
    msg_lower = (message or "").lower()
    if "tomorrow" in msg_lower:
        return "tomorrow"
    if "this week" in msg_lower:
        return "this_week"
    if "next week" in msg_lower:
        return "next_week"
    if "this weekend" in msg_lower or "weekend" in msg_lower:
        return "weekend"
    if "coming up" in msg_lower or "next 7" in msg_lower:
        return "next"
    return None


def calendar_task_context(events: list[dict[str, Any]], cal_range: str) -> str:
    if events:
        return (
            f"[CALENDAR DATA \u2014 range={cal_range}, fetched server-side]\n"
            + json.dumps(events, indent=2, default=str)
            + "\n[END CALENDAR DATA]"
        )
    return (
        f"[CALENDAR DATA \u2014 range={cal_range}]\n"
        f"No events found.\n[END CALENDAR DATA]"
    )


def calendar_task_credentials_error_context(error: BaseException) -> str:
    return (
        f"[CALENDAR ERROR]\nGoogle Calendar not set up: {error}\n"
        f"[END CALENDAR ERROR]"
    )


def calendar_task_error_context(error: BaseException) -> str:
    return (
        f"[CALENDAR ERROR]\nFailed to fetch calendar: {error}\n"
        f"[END CALENDAR ERROR]"
    )


def calendar_delegate_context(events: list[dict[str, Any]], cal_range: str) -> str:
    if events:
        return (
            f"\n\n[CALENDAR DATA \u2014 range={cal_range}, fetched server-side just now]\n"
            + json.dumps(events, indent=2, default=str)
            + "\n[END CALENDAR DATA]\n\n"
            "Summarize these events naturally. Count them, mention titles and start times, "
            "flag back-to-back meetings or conflicts. If the user asked about a specific "
            "person/topic, filter accordingly. Times are in the user's local timezone."
        )
    return (
        f"\n\n[CALENDAR DATA \u2014 range={cal_range}, fetched server-side just now]\n"
        "No events found.\n"
        "[END CALENDAR DATA]\n\n"
        f"Tell the user their {cal_range.replace('_', ' ')} is clear."
    )


def calendar_delegate_credentials_error_context(error: BaseException) -> str:
    return (
        "\n\n[CALENDAR ERROR]\n"
        f"Google Calendar is not set up: {error}\n"
        "Tell the user they need to sign in with Google on the Vessence web UI "
        "to enable calendar access.\n"
        "[END CALENDAR ERROR]"
    )


def calendar_delegate_error_context(error: BaseException) -> str:
    return (
        "\n\n[CALENDAR ERROR]\n"
        f"Failed to fetch calendar: {error}\n"
        "Apologize and suggest trying again.\n"
        "[END CALENDAR ERROR]"
    )
