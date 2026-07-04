"""Shared SMS metadata helpers for read/delete message escalation contexts."""
from __future__ import annotations

import datetime
from collections.abc import Callable


def format_message_timestamp(
    timestamp_ms: int,
    *,
    fromtimestamp_fn: Callable[[float], datetime.datetime] = datetime.datetime.fromtimestamp,
) -> str:
    return fromtimestamp_fn(timestamp_ms / 1000).strftime("%m/%d %I:%M %p").lstrip("0")


def message_kind(row: dict) -> str:
    return "contact" if row.get("is_contact") else (row.get("msg_type") or "unknown")


def message_direction_label(sender_raw: str) -> str:
    if sender_raw.startswith("Me → "):
        other = sender_raw[len("Me → "):].strip()
        return f"SENT by user to {other}"
    return f"RECEIVED from {sender_raw}"


def format_synced_message_line(
    index: int,
    row: dict,
    body: str,
    *,
    fromtimestamp_fn: Callable[[float], datetime.datetime] = datetime.datetime.fromtimestamp,
) -> str:
    ts = format_message_timestamp(row["timestamp_ms"], fromtimestamp_fn=fromtimestamp_fn)
    sender_raw = row["sender"] or "Unknown"
    return f"{index}. [{ts}] ({message_direction_label(sender_raw)}) ({message_kind(row)}): {body}"
