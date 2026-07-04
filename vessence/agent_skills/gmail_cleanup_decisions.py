"""Pure Gmail cleanup decision helpers."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from agent_skills.gmail_cleanup_queries import sender_cleanup_prefix
from agent_skills.gmail_message_utils import (
    google_calendar_event_has_passed,
    header_map,
    message_is_older_than_days,
    sender_matches_cleanup_rule,
    sender_matches_fragments,
)


@dataclass(frozen=True)
class CleanupDecision:
    outcome: str
    should_trash: bool
    subject: str
    sender: str = ""


def trash_outcome(prefix: str, dry_run: bool) -> str:
    return f"{prefix}_would_trash" if dry_run else f"{prefix}_trashed"


def evaluate_sender_cleanup_message(
    message: dict,
    *,
    label: str,
    sender_fragments: tuple[str, ...],
    older_than_days: int,
    dry_run: bool,
    sender_domains: tuple[str, ...] = (),
    subject_fragments: tuple[str, ...] = (),
    required_label_ids: tuple[str, ...] = (),
    now: dt.datetime | None = None,
) -> CleanupDecision:
    headers = header_map(message)
    sender = headers.get("from", "")
    subject = headers.get("subject", "(no subject)")
    prefix = sender_cleanup_prefix(label)

    if not sender_matches_cleanup_rule(sender, sender_fragments, sender_domains):
        return CleanupDecision(f"{prefix}_skipped", False, subject, sender)
    if required_label_ids and not set(required_label_ids).issubset(set(message.get("labelIds") or [])):
        return CleanupDecision(f"{prefix}_skipped_labels", False, subject, sender)
    if subject_fragments and not any(fragment.lower() in subject.lower() for fragment in subject_fragments):
        return CleanupDecision(f"{prefix}_skipped_subject", False, subject, sender)
    if not message_is_older_than_days(message, older_than_days, now=now):
        return CleanupDecision(f"{prefix}_too_recent", False, subject, sender)

    return CleanupDecision(trash_outcome(prefix, dry_run), True, subject, sender)


def evaluate_google_calendar_cleanup_message(
    message: dict,
    *,
    sender_fragments: tuple[str, ...],
    dry_run: bool,
    now: dt.datetime | None = None,
) -> CleanupDecision:
    headers = header_map(message)
    sender = headers.get("from", "")
    subject = headers.get("subject", "(no subject)")
    if not sender_matches_fragments(sender, sender_fragments):
        return CleanupDecision("google_calendar_skipped", False, subject, sender)

    event_has_passed = google_calendar_event_has_passed(message, now=now)
    if event_has_passed is None:
        return CleanupDecision("google_calendar_no_event_date", False, subject, sender)
    if not event_has_passed:
        return CleanupDecision("google_calendar_future_event", False, subject, sender)

    return CleanupDecision(trash_outcome("google_calendar", dry_run), True, subject, sender)


def evaluate_unread_cleanup_message(
    message: dict,
    *,
    older_than_days: int,
    dry_run: bool,
    now: dt.datetime | None = None,
) -> CleanupDecision:
    headers = header_map(message)
    sender = headers.get("from", "")
    subject = headers.get("subject", "(no subject)")
    if "UNREAD" not in (message.get("labelIds") or []):
        return CleanupDecision("old_unread_skipped_read", False, subject, sender)
    if not message_is_older_than_days(message, older_than_days, now=now):
        return CleanupDecision("old_unread_too_recent", False, subject, sender)

    return CleanupDecision(trash_outcome("old_unread", dry_run), True, subject, sender)
