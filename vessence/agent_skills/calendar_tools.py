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
from typing import Any

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from agent_skills.email_oauth import refresh_token_if_needed

_logger = logging.getLogger(__name__)

_PRIMARY = "primary"


def _service(user_id: str | None = None):
    token_data = refresh_token_if_needed(user_id)
    if token_data is None:
        raise RuntimeError(
            "No Google credentials available. Sign in with Google first."
        )
    granted = set(token_data.get("scope", "").split())
    write_scopes = {
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/calendar",
    }
    if not (granted & write_scopes):
        raise RuntimeError(
            "Calendar write scope not granted. Re-sign in with Google to "
            "grant calendar access."
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
    svc = _service(user_id)
    body: dict[str, Any] = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_iso},
        "end": {"dateTime": end_iso},
    }
    if reminders_minutes is not None:
        if len(reminders_minutes) > 5:
            raise ValueError("Google Calendar allows at most 5 reminder overrides.")
        for m in reminders_minutes:
            if not isinstance(m, int) or m < 0 or m > 40320:
                raise ValueError(
                    f"Reminder minutes must be int in [0, 40320]; got {m!r}."
                )
        body["reminders"] = {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": m} for m in reminders_minutes
            ],
        }
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
    svc = _service(user_id)
    patch: dict[str, Any] = {}
    if summary is not None:
        patch["summary"] = summary
    if description is not None:
        patch["description"] = description
    if start_iso is not None:
        patch["start"] = {"dateTime": start_iso}
    if end_iso is not None:
        patch["end"] = {"dateTime": end_iso}
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
