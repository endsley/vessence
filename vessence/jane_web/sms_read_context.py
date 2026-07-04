"""Helpers for injecting synced SMS readback context into the brain prompt."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Iterable, Mapping


@dataclass(frozen=True)
class SmsReadQuery:
    days: int
    limit: int
    sender_filter: str | None


def sms_read_query_from_router_response(
    router_response: str | None,
    *,
    default_days: int = 5,
    default_limit: int = 30,
    max_limit: int = 50,
) -> SmsReadQuery:
    """Parse the legacy router response into SMS DB query parameters."""
    sms_resp = (router_response or "").lower().strip()
    sender_filter = None
    sms_parts = sms_resp.replace("read_inbox", "").replace("read_messages", "").strip()
    if sms_parts and not sms_parts.isdigit():
        sender_filter = sms_parts.strip()
    limit = default_limit
    limit_match = re.search(r"\b(\d+)\b", sms_resp)
    if limit_match:
        limit = min(int(limit_match.group(1)), max_limit)
    return SmsReadQuery(days=default_days, limit=limit, sender_filter=sender_filter)


def _synced_sms_since_ms(query: SmsReadQuery, *, now_fn: Callable[[], float] = time.time) -> int:
    return int((now_fn() - query.days * 86400) * 1000)


def _synced_sms_rows(conn: Any, query: SmsReadQuery, *, since_ms: int) -> Iterable[Mapping[str, Any]]:
    if query.sender_filter:
        filter_q = f"%{query.sender_filter}%"
        return conn.execute(
            """SELECT sender, body, timestamp_ms, is_read, is_contact, msg_type
               FROM synced_messages
               WHERE timestamp_ms > ? AND (sender LIKE ? OR body LIKE ?)
               ORDER BY timestamp_ms DESC LIMIT ?""",
            (since_ms, filter_q, filter_q, query.limit),
        ).fetchall()
    return conn.execute(
        """SELECT sender, body, timestamp_ms, is_read, is_contact, msg_type
           FROM synced_messages
           WHERE timestamp_ms > ?
           ORDER BY timestamp_ms DESC LIMIT ?""",
        (since_ms, query.limit),
    ).fetchall()


def fetch_sms_readback_messages(
    conn: Any,
    query: SmsReadQuery,
    *,
    now_fn: Callable[[], float] = time.time,
    enrich_fn: Callable[[Iterable[Mapping[str, Any]]], list[dict[str, Any]]] | None = None,
    fromtimestamp_fn=datetime.fromtimestamp,
) -> list[dict[str, Any]]:
    """Fetch, enrich, and annotate synced SMS rows for readback contexts."""
    if enrich_fn is None:
        from jane_web.message_readback import enrich_synced_messages_for_readback
        enrich_fn = enrich_synced_messages_for_readback
    rows = _synced_sms_rows(conn, query, since_ms=_synced_sms_since_ms(query, now_fn=now_fn))
    messages = enrich_fn([dict(row) for row in rows])
    return add_sms_display_times(messages, fromtimestamp_fn=fromtimestamp_fn)


def add_sms_display_times(
    messages: list[dict[str, Any]],
    *,
    fromtimestamp_fn=datetime.fromtimestamp,
) -> list[dict[str, Any]]:
    """Add the existing human-readable `time` field to SMS records in place."""
    for message in messages:
        try:
            message["time"] = fromtimestamp_fn(message["timestamp_ms"] / 1000).strftime("%b %d %I:%M %p")
        except Exception:
            pass
    return messages


def sms_task_context(messages: list[dict[str, Any]]) -> str:
    if messages:
        return (
            "[SMS INBOX DATA — fetched from synced messages DB]\n"
            + json.dumps(messages, indent=2, default=str)
            + "\n[END SMS INBOX DATA]\n\n"
            "msg_type guide: personal=important contacts, reminder=appointments, "
            "notification=shipping/delivery, spam=skip, unknown=mention if important."
            " Use body_for_readback as the text to read to the user. If "
            "body_resolution is unresolved_talkingpoints_link, say the linked "
            "message could not be opened automatically instead of reading the "
            "wrapper notification as the message."
        )
    return "[SMS INBOX DATA]\nNo text messages found in the last 5 days.\n[END SMS INBOX DATA]"


def sms_task_error_context(error: BaseException) -> str:
    return f"[SMS ERROR]\nFailed to fetch messages: {error}\n[END SMS ERROR]"


def sms_inbox_context(messages: list[dict[str, Any]]) -> str:
    if messages:
        return (
            "\n\n[SMS INBOX DATA — fetched from synced messages DB]\n"
            + json.dumps(messages, indent=2, default=str)
            + "\n[END SMS INBOX DATA]\n\n"
            "Summarize these text messages. Each message has a msg_type field:\n"
            "- 'personal' (is_contact=true): from known contacts — read these first, they're important\n"
            "- 'reminder': appointments, due dates, renewals — mention briefly\n"
            "- 'notification': shipping, delivery, order updates — mention briefly\n"
            "- 'spam': promotions, deals, marketing — skip unless user asks\n"
            "- 'unknown': unrecognized sender — mention only if content seems important\n"
            "Use body_for_readback as the text to read to the user. If "
            "body_resolution is unresolved_talkingpoints_link, say the linked "
            "message could not be opened automatically instead of reading the "
            "wrapper notification as the message.\n"
            "Group personal messages by sender. If the user asked about a specific person, focus on those."
        )
    return (
        "\n\n[SMS INBOX DATA — fetched from synced messages DB]\n"
        "No text messages found in the last 5 days.\n"
        "[END SMS INBOX DATA]\n\n"
        "Tell the user no recent text messages were found. "
        "If messages haven't synced yet, suggest they open the Vessence app on their phone."
    )


def sms_read_error_context(error: BaseException) -> str:
    return (
        "\n\n[SMS ERROR]\n"
        f"Failed to fetch messages from DB: {error}\n"
        "Apologize and suggest the user open the Vessence app to trigger a sync.\n"
        "[END SMS ERROR]"
    )
