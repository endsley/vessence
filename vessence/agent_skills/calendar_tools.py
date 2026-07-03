"""calendar_tools.py — Google Calendar API integration for Jane.

CRUD for events on the user's primary Google Calendar. The OAuth access
token (with the calendar.events scope) is reused from the Gmail token
file — Google issues one token per consent covering all granted scopes,
so email_oauth's refresh machinery works here unchanged.

Usage (server-side, via Jane's intent dispatcher):
    list_events(time_min_iso, time_max_iso, max_results=20)
    create_event(summary, start_iso, end_iso, description="", reminders_minutes=None)
    update_event(event_id, **fields)
    delete_event(event_id)
    quick_add(text)   # Google parses "Dinner with Kathia Saturday 7pm"

All times are ISO-8601 strings with timezone, e.g. "2026-04-15T18:00:00-04:00".
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from agent_skills.email_oauth import refresh_token_if_needed
from agent_skills.calendar_time_helpers import (
    dt_to_iso_utc as _dt_to_iso_utc,
    reminder_overrides_body as _reminder_overrides_body,
    resolve_range_for_now as _resolve_range_for_now,
    to_local_naive_iso as _to_local_naive_iso,
)

_logger = logging.getLogger(__name__)

_PRIMARY = "primary"

def _detect_system_tz_name() -> str:
    try:
        import subprocess
        out = subprocess.run(
            ["timedatectl", "show", "-p", "Timezone", "--value"],
            capture_output=True, text=True, timeout=2,
        )
        name = out.stdout.strip()
        if name:
            return name
    except Exception:
        pass
    try:
        link = os.readlink("/etc/localtime")
        if "zoneinfo/" in link:
            return link.split("zoneinfo/", 1)[1]
    except Exception:
        pass
    return "UTC"


_LOCAL_TZ_NAME = os.environ.get("JANE_LOCAL_TZ") or _detect_system_tz_name()


def _local_tz():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(_LOCAL_TZ_NAME)
    except Exception:
        return timezone.utc


def resolve_range(range_hint: str | None) -> tuple[datetime, datetime]:
    """Turn a natural-language range hint into a (start, end) pair of
    timezone-aware datetimes in the user's local timezone.

    Accepts: today, tomorrow, this_week, next_week, weekend, next,
    next_30_days, next_60_days, next_90_days, monday..sunday (resolves
    to the upcoming occurrence — today if today matches, else the next
    1-6 days), YYYY-MM-DD. Unknown hints fall back to today.
    """
    tz = _local_tz()
    return _resolve_range_for_now(range_hint, datetime.now(tz))


def list_events_in_range(
    range_hint: str | None = "today",
    max_results: int = 25,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """High-level read helper used by the v2 dispatcher / proxy.

    Resolves `range_hint` to a (start, end) window in the local timezone,
    then fetches events from the primary calendar.
    """
    start, end = resolve_range(range_hint)
    return list_events(
        time_min_iso=_dt_to_iso_utc(start),
        time_max_iso=_dt_to_iso_utc(end),
        max_results=max_results,
        user_id=user_id,
    )


def _service(user_id: str | None = None, require_write: bool = False):
    token_data = refresh_token_if_needed(user_id)
    if token_data is None:
        raise RuntimeError(
            "No Google credentials available. Sign in with Google first."
        )
    granted = set(token_data.get("scope", "").split())
    read_scopes = {
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/calendar.events.readonly",
        "https://www.googleapis.com/auth/calendar",
    }
    write_scopes = {
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/calendar",
    }
    need = write_scopes if require_write else read_scopes
    if not (granted & need):
        raise RuntimeError(
            "Google Calendar access not granted. Reconnect Google on the "
            "Vessence web UI and grant calendar access when prompted."
        )
    creds = Credentials(
        token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def list_events(
    time_min_iso: str,
    time_max_iso: str | None = None,
    max_results: int = 20,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    svc = _service(user_id)
    params = {
        "calendarId": _PRIMARY,
        "timeMin": time_min_iso,
        "maxResults": max_results,
        "singleEvents": True,
        "orderBy": "startTime",
    }
    if time_max_iso:
        params["timeMax"] = time_max_iso
    resp = svc.events().list(**params).execute()
    return [_slim(e) for e in resp.get("items", [])]


def create_event(
    summary: str,
    start_iso: str,
    end_iso: str,
    description: str = "",
    reminders_minutes: list[int] | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    svc = _service(user_id, require_write=True)
    body: dict[str, Any] = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": _to_local_naive_iso(start_iso), "timeZone": _LOCAL_TZ_NAME},
        "end": {"dateTime": _to_local_naive_iso(end_iso), "timeZone": _LOCAL_TZ_NAME},
    }
    if reminders_minutes is not None:
        body["reminders"] = _reminder_overrides_body(reminders_minutes)
    event = svc.events().insert(calendarId=_PRIMARY, body=body).execute()
    _logger.info("Created calendar event %s: %s", event.get("id"), summary)
    return _slim(event)


def quick_add(text: str, user_id: str | None = None) -> dict[str, Any]:
    """Natural-language event creation — Google parses the text itself.

    Example: quick_add("Dinner with Kathia Saturday 7pm")
    """
    svc = _service(user_id)
    event = svc.events().quickAdd(calendarId=_PRIMARY, text=text).execute()
    _logger.info("Quick-added event %s from %r", event.get("id"), text)
    return _slim(event)


def update_event(
    event_id: str,
    summary: str | None = None,
    start_iso: str | None = None,
    end_iso: str | None = None,
    description: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    svc = _service(user_id, require_write=True)
    patch: dict[str, Any] = {}
    if summary is not None:
        patch["summary"] = summary
    if description is not None:
        patch["description"] = description
    if start_iso is not None:
        patch["start"] = {"dateTime": _to_local_naive_iso(start_iso), "timeZone": _LOCAL_TZ_NAME}
    if end_iso is not None:
        patch["end"] = {"dateTime": _to_local_naive_iso(end_iso), "timeZone": _LOCAL_TZ_NAME}
    if not patch:
        raise ValueError("update_event called with no fields to change.")
    event = svc.events().patch(
        calendarId=_PRIMARY, eventId=event_id, body=patch,
    ).execute()
    return _slim(event)


def delete_event(event_id: str, user_id: str | None = None) -> bool:
    svc = _service(user_id)
    svc.events().delete(calendarId=_PRIMARY, eventId=event_id).execute()
    _logger.info("Deleted calendar event %s", event_id)
    return True


def _slim(event: dict[str, Any]) -> dict[str, Any]:
    start = event.get("start", {})
    end = event.get("end", {})
    return {
        "id": event.get("id"),
        "summary": event.get("summary", ""),
        "description": event.get("description", ""),
        "start": start.get("dateTime") or start.get("date"),
        "end": end.get("dateTime") or end.get("date"),
        "html_link": event.get("htmlLink"),
    }
