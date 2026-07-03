"""Pure Gmail cleanup query helpers."""

from __future__ import annotations

import datetime as dt
import re
from zoneinfo import ZoneInfo


def previous_local_day(now: dt.datetime | None = None) -> dt.date:
    tz = ZoneInfo("America/New_York")
    now = now or dt.datetime.now(tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    return now.astimezone(tz).date() - dt.timedelta(days=1)


def gmail_date(value: dt.date) -> str:
    return value.strftime("%Y/%m/%d")


def sender_cleanup_prefix(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or "sender_cleanup"


def build_sender_query(
    *,
    recipient: str,
    day: dt.date,
    from_query: str,
    include_trash: bool,
) -> str:
    query_start = day - dt.timedelta(days=1)
    query_end = day + dt.timedelta(days=2)
    parts = [
        "in:anywhere" if include_trash else "",
        f"to:{recipient}",
        f"from:{from_query}",
        f"after:{gmail_date(query_start)}",
        f"before:{gmail_date(query_end)}",
        "-in:spam",
    ]
    if not include_trash:
        parts.append("-in:trash")
    return " ".join(part for part in parts if part)


def build_older_sender_query(
    *,
    recipient: str,
    from_query: str,
    older_than_days: int,
    include_trash: bool,
    extra_terms: tuple[str, ...] = (),
) -> str:
    parts = [
        "in:anywhere" if include_trash else "",
        f"to:{recipient}",
        f"from:{from_query}",
        *extra_terms,
        f"older_than:{int(older_than_days)}d",
        "-in:spam",
    ]
    if not include_trash:
        parts.append("-in:trash")
    return " ".join(part for part in parts if part)


def build_google_calendar_query(
    *,
    recipient: str,
    from_query: str,
    include_trash: bool,
) -> str:
    parts = [
        "in:anywhere" if include_trash else "",
        f"to:{recipient}",
        f"from:{from_query}",
        "-in:spam",
    ]
    if not include_trash:
        parts.append("-in:trash")
    return " ".join(part for part in parts if part)


def build_unread_cleanup_query(
    *,
    older_than_days: int,
    include_trash: bool,
) -> str:
    parts = [
        "in:anywhere" if include_trash else "",
        "is:unread",
        f"older_than:{int(older_than_days)}d",
        "-in:spam",
    ]
    if not include_trash:
        parts.append("-in:trash")
    return " ".join(part for part in parts if part)
