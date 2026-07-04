#!/usr/bin/env python3
"""Daily Nutricost marketing deal monitor.

At 5 AM, scan yesterday's Nutricost marketing emails. Trash messages whose
largest advertised discount is below the threshold. For qualifying messages,
send Chieh a link from the juliaprocess Gmail account. Also trash any
CrunchLabs messages from the same local-day window, older Amazon, Google Maps,
LinkedIn, Redfin, or approved low-priority newsletter/promotion messages after
their retention window, and Google Calendar messages whose event date/time has
passed. Finally, trash unread messages older than three weeks.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - dotenv is present in Jane runtime
    load_dotenv = None

from jane.config import ENV_FILE_PATH, VESSENCE_DATA_HOME
from agent_skills.email_tools import get_gmail_service, send_email
from agent_skills.gmail_message_utils import (
    calendar_event_end_from_ics,
    decode_body_data,
    google_calendar_event_end_from_subject,
    google_calendar_event_has_passed,
    header_map,
    message_calendar_text,
    message_is_older_than_days,
    message_local_date,
    message_local_datetime,
    message_text,
    parse_ics_datetime,
    parse_subject_time,
    parsed_message_date,
    sender_matches_cleanup_rule,
    sender_matches_domains,
    sender_matches_fragments,
    strip_html,
    unfold_ics_lines,
    walk_parts,
)
from agent_skills.gmail_cleanup_queries import (
    build_google_calendar_query as _build_google_calendar_query,
    build_older_sender_query as _build_older_sender_query,
    build_sender_query as _build_sender_query,
    build_unread_cleanup_query as _build_unread_cleanup_query,
    gmail_date,
    previous_local_day,
    sender_cleanup_prefix as _sender_cleanup_prefix,
)
from agent_skills.gmail_cleanup_decisions import (
    evaluate_google_calendar_cleanup_message,
    evaluate_sender_cleanup_message,
    evaluate_unread_cleanup_message,
)
from agent_skills.gmail_cleanup_counts import (
    count_message_outcomes,
    merge_outcome_counts,
)
from agent_skills.nutricost_deal_utils import (
    NUTRICOST_FROM,
    alerted_message_ids,
    best_detected_discount,
    build_deal_alert_content,
    clean_url,
    default_monitor_state,
    extract_deal_links,
    extract_discounts,
    is_marketing_message,
    nutricost_message_text,
    record_alerted_message,
)


RECIPIENT = "chieh.t.wu@gmail.com"
READER_ACCOUNT = "chieh.t.wu@gmail.com"
ALERT_SENDER = "juliaprocess@gmail.com"
CRUNCHLABS_FROM_QUERY = "crunchlabs"
CRUNCHLABS_SENDER_FRAGMENT = "crunchlabs"
AMAZON_FROM_QUERY = "(amazon.com OR amazonaws.com OR amazon.science)"
AMAZON_SENDER_FRAGMENTS: tuple[str, ...] = ()
AMAZON_SENDER_DOMAINS = ("amazon.com", "amazonaws.com", "amazon.science")
GOOGLE_MAPS_FROM_QUERY = "(googlemaps OR maps-noreply OR localguides)"
GOOGLE_MAPS_SENDER_FRAGMENTS = ("google maps", "googlemaps", "maps.google", "localguides", "local guides")
LINKEDIN_FROM_QUERY = "linkedin"
LINKEDIN_SENDER_FRAGMENTS = ("linkedin",)
GOOGLE_CALENDAR_FROM_QUERY = "(calendar-notification OR googlecalendar)"
GOOGLE_CALENDAR_SENDER_FRAGMENTS = ("calendar-notification", "google calendar", "googlecalendar")
REDFIN_FROM_QUERY = "redfin"
REDFIN_SENDER_FRAGMENTS = ("redfin",)
SENDER_CLEANUP_RETENTION_DAYS = 2
REDFIN_CLEANUP_RETENTION_DAYS = 3
LOW_PRIORITY_CLEANUP_RETENTION_DAYS = 3
UNREAD_CLEANUP_RETENTION_DAYS = 21
STATE_PATH = Path(VESSENCE_DATA_HOME) / "data" / "nutricost_deal_monitor.json"

LOGGER = logging.getLogger("nutricost_deal_monitor")


@dataclass(frozen=True)
class SenderCleanupSpec:
    label: str
    from_query: str
    sender_fragments: tuple[str, ...]
    sender_domains: tuple[str, ...] = ()
    retention_days: int = SENDER_CLEANUP_RETENTION_DAYS
    query_terms: tuple[str, ...] = ()
    subject_fragments: tuple[str, ...] = ()
    required_label_ids: tuple[str, ...] = ()


SENDER_CLEANUP_SPECS: tuple[SenderCleanupSpec, ...] = (
    SenderCleanupSpec(
        "Amazon",
        AMAZON_FROM_QUERY,
        AMAZON_SENDER_FRAGMENTS,
        sender_domains=AMAZON_SENDER_DOMAINS,
    ),
    SenderCleanupSpec("Google Maps", GOOGLE_MAPS_FROM_QUERY, GOOGLE_MAPS_SENDER_FRAGMENTS),
    SenderCleanupSpec(
        "LinkedIn",
        LINKEDIN_FROM_QUERY,
        LINKEDIN_SENDER_FRAGMENTS,
        retention_days=LOW_PRIORITY_CLEANUP_RETENTION_DAYS,
        query_terms=("category:social",),
        required_label_ids=("CATEGORY_SOCIAL",),
    ),
    SenderCleanupSpec(
        "Redfin",
        REDFIN_FROM_QUERY,
        REDFIN_SENDER_FRAGMENTS,
        retention_days=REDFIN_CLEANUP_RETENTION_DAYS,
    ),
    SenderCleanupSpec(
        "The Covery Promotions",
        "woburn@thecovery.com",
        ("woburn@thecovery.com",),
        retention_days=LOW_PRIORITY_CLEANUP_RETENTION_DAYS,
        query_terms=("category:promotions",),
        required_label_ids=("CATEGORY_PROMOTIONS",),
    ),
    SenderCleanupSpec(
        "Museum of Science Promotions",
        "friends@e.mos.org",
        ("friends@e.mos.org",),
        retention_days=LOW_PRIORITY_CLEANUP_RETENTION_DAYS,
        query_terms=("category:promotions",),
        required_label_ids=("CATEGORY_PROMOTIONS",),
    ),
    SenderCleanupSpec(
        "Spotify Promotions",
        "no-reply@spotify.com",
        ("no-reply@spotify.com",),
        retention_days=LOW_PRIORITY_CLEANUP_RETENTION_DAYS,
        query_terms=("category:promotions",),
        required_label_ids=("CATEGORY_PROMOTIONS",),
    ),
    SenderCleanupSpec(
        "Discord Missed Messages",
        "noreply@discord.com",
        ("noreply@discord.com",),
        retention_days=LOW_PRIORITY_CLEANUP_RETENTION_DAYS,
        query_terms=('subject:"You missed messages"',),
        required_label_ids=("CATEGORY_UPDATES",),
        subject_fragments=("you missed messages",),
    ),
    SenderCleanupSpec(
        "Boston Globe Newsletters",
        "(newsletters@bostonglobe.com OR newsletters@email.bostonglobe.com)",
        ("newsletters@bostonglobe.com", "newsletters@email.bostonglobe.com"),
        retention_days=LOW_PRIORITY_CLEANUP_RETENTION_DAYS,
        required_label_ids=("CATEGORY_UPDATES",),
    ),
    SenderCleanupSpec(
        "LifespanIO Newsletters",
        "pr@lifespan.io",
        ("pr@lifespan.io",),
        retention_days=LOW_PRIORITY_CLEANUP_RETENTION_DAYS,
        query_terms=('subject:"Weekly News"',),
        required_label_ids=("CATEGORY_UPDATES",),
        subject_fragments=("weekly news",),
    ),
    SenderCleanupSpec(
        "Glassdoor Updates",
        "noreply@glassdoor.com",
        ("noreply@glassdoor.com",),
        retention_days=LOW_PRIORITY_CLEANUP_RETENTION_DAYS,
        query_terms=('subject:"employee reviews"',),
        required_label_ids=("CATEGORY_UPDATES",),
        subject_fragments=("employee reviews",),
    ),
)


def bootstrap_env() -> None:
    """Load cron-safe runtime env and vault-backed secrets."""
    if load_dotenv:
        load_dotenv(ENV_FILE_PATH)

    try:
        from agent_skills.secret_store import SecretStore

        store = SecretStore()
        if store.is_unlocked():
            for key in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
                value = store.get(key)
                if value and not os.getenv(key):
                    os.environ[key] = value
    except Exception as exc:
        LOGGER.warning("SecretStore bootstrap failed: %s", exc)


def load_state() -> dict:
    if not STATE_PATH.exists():
        return default_monitor_state()
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return default_monitor_state()


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = STATE_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp_path.replace(STATE_PATH)


def list_message_ids(service, query: str) -> list[str]:
    ids: list[str] = []
    page_token = None
    while True:
        request = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=100,
            pageToken=page_token,
        )
        response = request.execute()
        ids.extend(item["id"] for item in response.get("messages", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return ids


def read_message(service, message_id: str) -> dict:
    return service.users().messages().get(userId="me", id=message_id, format="full").execute()


def trash_message(service, message_id: str, dry_run: bool) -> None:
    if dry_run:
        LOGGER.info("DRY RUN: would trash %s", message_id)
        return
    service.users().messages().trash(userId="me", id=message_id).execute()
    LOGGER.info("Trashed %s", message_id)


def send_deal_alert(
    *,
    subject: str,
    message_date: str,
    discount: int,
    links: list[str],
    message_id: str,
    dry_run: bool,
) -> None:
    content = build_deal_alert_content(
        subject=subject,
        message_date=message_date,
        discount=discount,
        links=links,
        message_id=message_id,
    )
    if dry_run:
        LOGGER.info("DRY RUN: would send alert from %s: %s", ALERT_SENDER, content.subject)
        LOGGER.info("DRY RUN alert body:\n%s", content.body)
        return
    result = send_email(
        to=RECIPIENT,
        subject=content.subject,
        body=content.body,
        from_email=ALERT_SENDER,
    )
    LOGGER.info("Sent alert from %s: %s", result.get("from_email", ALERT_SENDER), result.get("message_id"))


def process_message(service, message_id: str, day: dt.date, threshold: int, dry_run: bool, state: dict) -> str:
    message = read_message(service, message_id)
    local_date = message_local_date(message)
    if local_date != day:
        LOGGER.info("Skipped out-of-scope message %s: local_date=%s", message_id, local_date)
        return "out_of_scope"

    headers = header_map(message)
    subject = headers.get("subject", "(no subject)")
    text = nutricost_message_text(message, subject)

    if not is_marketing_message(message, text):
        LOGGER.info("Skipped non-marketing Nutricost message %s: %s", message_id, subject)
        return "skipped"

    best_discount = best_detected_discount(text)
    LOGGER.info("Message %s best discount=%s subject=%s", message_id, best_discount, subject)

    if best_discount < threshold:
        trash_message(service, message_id, dry_run=dry_run)
        return "trashed" if not dry_run else "would_trash"

    if message_id in alerted_message_ids(state):
        LOGGER.info("Already alerted for qualifying message %s", message_id)
        return "already_alerted"

    send_deal_alert(
        subject=subject,
        message_date=parsed_message_date(headers),
        discount=best_discount,
        links=extract_deal_links(text),
        message_id=message_id,
        dry_run=dry_run,
    )
    if not dry_run:
        record_alerted_message(state, message_id)
    return "alerted" if not dry_run else "would_alert"


def process_crunchlabs_message(service, message_id: str, day: dt.date, dry_run: bool) -> str:
    message = read_message(service, message_id)
    local_date = message_local_date(message)
    if local_date != day:
        LOGGER.info("Skipped out-of-scope CrunchLabs message %s: local_date=%s", message_id, local_date)
        return "crunchlabs_out_of_scope"

    headers = header_map(message)
    sender = headers.get("from", "")
    subject = headers.get("subject", "(no subject)")
    if CRUNCHLABS_SENDER_FRAGMENT not in sender.lower():
        LOGGER.info("Skipped non-CrunchLabs message %s: from=%s subject=%s", message_id, sender, subject)
        return "crunchlabs_skipped"

    trash_message(service, message_id, dry_run=dry_run)
    LOGGER.info("Trashed CrunchLabs message %s: %s", message_id, subject)
    return "crunchlabs_trashed" if not dry_run else "crunchlabs_would_trash"


def process_sender_cleanup_message(
    service,
    message_id: str,
    *,
    label: str,
    sender_fragments: tuple[str, ...],
    older_than_days: int,
    dry_run: bool,
    sender_domains: tuple[str, ...] = (),
    subject_fragments: tuple[str, ...] = (),
    required_label_ids: tuple[str, ...] = (),
    now: dt.datetime | None = None,
) -> str:
    message = read_message(service, message_id)
    prefix = _sender_cleanup_prefix(label)
    decision = evaluate_sender_cleanup_message(
        message,
        label=label,
        sender_fragments=sender_fragments,
        sender_domains=sender_domains,
        older_than_days=older_than_days,
        dry_run=dry_run,
        subject_fragments=subject_fragments,
        required_label_ids=required_label_ids,
        now=now,
    )

    if decision.outcome == f"{prefix}_skipped":
        LOGGER.info("Skipped non-%s message %s: from=%s subject=%s", label, message_id, decision.sender, decision.subject)
        return decision.outcome
    if decision.outcome == f"{prefix}_skipped_labels":
        LOGGER.info(
            "Skipped %s message without required labels %s: id=%s subject=%s",
            label,
            required_label_ids,
            message_id,
            decision.subject,
        )
        return decision.outcome
    if decision.outcome == f"{prefix}_skipped_subject":
        LOGGER.info("Skipped %s message without subject match %s: %s", label, message_id, decision.subject)
        return decision.outcome
    if decision.outcome == f"{prefix}_too_recent":
        LOGGER.info("Skipped recent %s message %s: subject=%s", label, message_id, decision.subject)
        return decision.outcome

    trash_message(service, message_id, dry_run=dry_run)
    action = "Would trash" if dry_run else "Trashed"
    LOGGER.info("%s %s message older than %d days %s: %s", action, label, older_than_days, message_id, decision.subject)
    return decision.outcome


def process_google_calendar_message(
    service,
    message_id: str,
    *,
    dry_run: bool,
    now: dt.datetime | None = None,
) -> str:
    message = read_message(service, message_id)
    decision = evaluate_google_calendar_cleanup_message(
        message,
        sender_fragments=GOOGLE_CALENDAR_SENDER_FRAGMENTS,
        dry_run=dry_run,
        now=now,
    )
    if decision.outcome == "google_calendar_skipped":
        LOGGER.info("Skipped non-Google Calendar message %s: from=%s subject=%s", message_id, decision.sender, decision.subject)
        return decision.outcome
    if decision.outcome == "google_calendar_no_event_date":
        LOGGER.info("Skipped Google Calendar message with no parseable event date %s: %s", message_id, decision.subject)
        return decision.outcome
    if decision.outcome == "google_calendar_future_event":
        LOGGER.info("Skipped future Google Calendar event message %s: %s", message_id, decision.subject)
        return decision.outcome

    trash_message(service, message_id, dry_run=dry_run)
    LOGGER.info("Trashed Google Calendar message for passed event %s: %s", message_id, decision.subject)
    return decision.outcome


def process_unread_cleanup_message(
    service,
    message_id: str,
    *,
    older_than_days: int,
    dry_run: bool,
    now: dt.datetime | None = None,
) -> str:
    message = read_message(service, message_id)
    decision = evaluate_unread_cleanup_message(
        message,
        older_than_days=older_than_days,
        dry_run=dry_run,
        now=now,
    )
    if decision.outcome == "old_unread_skipped_read":
        LOGGER.info("Skipped read message from unread cleanup %s: %s", message_id, decision.subject)
        return decision.outcome
    if decision.outcome == "old_unread_too_recent":
        LOGGER.info("Skipped recent unread message %s: %s", message_id, decision.subject)
        return decision.outcome

    trash_message(service, message_id, dry_run=dry_run)
    LOGGER.info("Trashed unread message older than %d days %s: %s", older_than_days, message_id, decision.subject)
    return decision.outcome


def count_nutricost_messages(
    service,
    message_ids: list[str],
    day: dt.date,
    *,
    threshold: int,
    dry_run: bool,
    state: dict,
    log_failure=None,
) -> dict[str, int]:
    return count_message_outcomes(
        message_ids,
        lambda message_id: process_message(service, message_id, day, threshold, dry_run, state),
        failure_outcome="failed",
        log_failure=log_failure,
    )


def count_crunchlabs_messages(
    service,
    message_ids: list[str],
    day: dt.date,
    *,
    dry_run: bool,
    log_failure=None,
) -> dict[str, int]:
    return count_message_outcomes(
        message_ids,
        lambda message_id: process_crunchlabs_message(service, message_id, day, dry_run),
        failure_outcome="crunchlabs_failed",
        log_failure=log_failure,
    )


def count_google_calendar_messages(
    service,
    message_ids: list[str],
    *,
    dry_run: bool,
    now: dt.datetime | None = None,
    log_failure=None,
) -> dict[str, int]:
    return count_message_outcomes(
        message_ids,
        lambda message_id: process_google_calendar_message(service, message_id, dry_run=dry_run, now=now),
        failure_outcome="google_calendar_failed",
        log_failure=log_failure,
    )


def count_sender_cleanup_messages(
    service,
    message_ids: list[str],
    spec: SenderCleanupSpec,
    *,
    dry_run: bool,
    now: dt.datetime | None = None,
    log_failure=None,
) -> dict[str, int]:
    return count_message_outcomes(
        message_ids,
        lambda message_id: process_sender_cleanup_message(
            service,
            message_id,
            label=spec.label,
            sender_fragments=spec.sender_fragments,
            sender_domains=spec.sender_domains,
            older_than_days=spec.retention_days,
            dry_run=dry_run,
            subject_fragments=spec.subject_fragments,
            required_label_ids=spec.required_label_ids,
            now=now,
        ),
        failure_outcome=f"{_sender_cleanup_prefix(spec.label)}_failed",
        log_failure=log_failure,
    )


def count_unread_cleanup_messages(
    service,
    message_ids: list[str],
    *,
    older_than_days: int,
    dry_run: bool,
    now: dt.datetime | None = None,
    log_failure=None,
) -> dict[str, int]:
    return count_message_outcomes(
        message_ids,
        lambda message_id: process_unread_cleanup_message(
            service,
            message_id,
            older_than_days=older_than_days,
            dry_run=dry_run,
            now=now,
        ),
        failure_outcome="old_unread_failed",
        log_failure=log_failure,
    )


def build_sender_query(day: dt.date, from_query: str, include_trash: bool) -> str:
    # Gmail date queries are not enough for local-day precision. Use a wider
    # search window, then filter by each message's internalDate in New York.
    return _build_sender_query(
        recipient=RECIPIENT,
        day=day,
        from_query=from_query,
        include_trash=include_trash,
    )


def build_query(day: dt.date, include_trash: bool) -> str:
    return build_sender_query(day, NUTRICOST_FROM, include_trash)


def build_crunchlabs_query(day: dt.date, include_trash: bool) -> str:
    return build_sender_query(day, CRUNCHLABS_FROM_QUERY, include_trash)


def build_older_sender_query(
    from_query: str,
    older_than_days: int,
    include_trash: bool,
    extra_terms: tuple[str, ...] = (),
) -> str:
    return _build_older_sender_query(
        recipient=RECIPIENT,
        from_query=from_query,
        older_than_days=older_than_days,
        include_trash=include_trash,
        extra_terms=extra_terms,
    )


def build_google_calendar_query(include_trash: bool) -> str:
    return _build_google_calendar_query(
        recipient=RECIPIENT,
        from_query=GOOGLE_CALENDAR_FROM_QUERY,
        include_trash=include_trash,
    )


def build_unread_cleanup_query(older_than_days: int, include_trash: bool) -> str:
    return _build_unread_cleanup_query(
        older_than_days=older_than_days,
        include_trash=include_trash,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="Local date to scan, YYYY-MM-DD. Defaults to yesterday.")
    parser.add_argument("--threshold", type=int, default=30, help="Minimum percent discount to alert on.")
    parser.add_argument("--dry-run", action="store_true", help="Log actions without deleting or sending.")
    parser.add_argument("--include-trash", action="store_true", help="Include Trash in the search. Useful for tests.")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    bootstrap_env()

    day = dt.date.fromisoformat(args.date) if args.date else previous_local_day()
    query = build_query(day, include_trash=args.include_trash)
    LOGGER.info("Scanning Nutricost messages for %s with query: %s", day.isoformat(), query)

    service = get_gmail_service(user_id=READER_ACCOUNT)
    message_ids = list_message_ids(service, query)
    LOGGER.info("Found %d candidate message(s)", len(message_ids))
    state = load_state()
    counts: dict[str, int] = {}
    merge_outcome_counts(
        counts,
        count_nutricost_messages(
            service,
            message_ids,
            day,
            threshold=args.threshold,
            dry_run=args.dry_run,
            state=state,
            log_failure=lambda message_id, exc: LOGGER.exception("Failed processing %s: %s", message_id, exc),
        ),
    )

    crunchlabs_query = build_crunchlabs_query(day, include_trash=args.include_trash)
    LOGGER.info("Scanning CrunchLabs messages for %s with query: %s", day.isoformat(), crunchlabs_query)
    crunchlabs_message_ids = list_message_ids(service, crunchlabs_query)
    LOGGER.info("Found %d CrunchLabs candidate message(s)", len(crunchlabs_message_ids))
    merge_outcome_counts(
        counts,
        count_crunchlabs_messages(
            service,
            crunchlabs_message_ids,
            day,
            dry_run=args.dry_run,
            log_failure=lambda message_id, exc: LOGGER.exception(
                "Failed processing CrunchLabs message %s: %s",
                message_id,
                exc,
            ),
        ),
    )

    for spec in SENDER_CLEANUP_SPECS:
        cleanup_query = build_older_sender_query(
            spec.from_query,
            spec.retention_days,
            include_trash=args.include_trash,
            extra_terms=spec.query_terms,
        )
        LOGGER.info("Scanning %s messages with query: %s", spec.label, cleanup_query)
        cleanup_message_ids = list_message_ids(service, cleanup_query)
        LOGGER.info("Found %d %s candidate message(s)", len(cleanup_message_ids), spec.label)
        merge_outcome_counts(
            counts,
            count_sender_cleanup_messages(
                service,
                cleanup_message_ids,
                spec,
                dry_run=args.dry_run,
                log_failure=lambda message_id, exc, spec=spec: LOGGER.exception(
                    "Failed processing %s message %s: %s",
                    spec.label,
                    message_id,
                    exc,
                ),
            ),
        )

    google_calendar_query = build_google_calendar_query(include_trash=args.include_trash)
    LOGGER.info("Scanning Google Calendar messages with query: %s", google_calendar_query)
    google_calendar_message_ids = list_message_ids(service, google_calendar_query)
    LOGGER.info("Found %d Google Calendar candidate message(s)", len(google_calendar_message_ids))
    merge_outcome_counts(
        counts,
        count_google_calendar_messages(
            service,
            google_calendar_message_ids,
            dry_run=args.dry_run,
            log_failure=lambda message_id, exc: LOGGER.exception(
                "Failed processing Google Calendar message %s: %s",
                message_id,
                exc,
            ),
        ),
    )

    unread_query = build_unread_cleanup_query(UNREAD_CLEANUP_RETENTION_DAYS, include_trash=args.include_trash)
    LOGGER.info("Scanning unread messages older than %d days with query: %s", UNREAD_CLEANUP_RETENTION_DAYS, unread_query)
    unread_message_ids = list_message_ids(service, unread_query)
    LOGGER.info("Found %d old unread candidate message(s)", len(unread_message_ids))
    merge_outcome_counts(
        counts,
        count_unread_cleanup_messages(
            service,
            unread_message_ids,
            older_than_days=UNREAD_CLEANUP_RETENTION_DAYS,
            dry_run=args.dry_run,
            log_failure=lambda message_id, exc: LOGGER.exception(
                "Failed processing old unread message %s: %s",
                message_id,
                exc,
            ),
        ),
    )

    if not args.dry_run:
        save_state(state)
    LOGGER.info("Done: %s", counts)
    return 1 if any(str(key).endswith("failed") for key in counts) else 0


if __name__ == "__main__":
    raise SystemExit(main())
