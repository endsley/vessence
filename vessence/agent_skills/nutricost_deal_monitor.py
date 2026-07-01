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
import html
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - dotenv is present in Jane runtime
    load_dotenv = None

from jane.config import ENV_FILE_PATH, VESSENCE_DATA_HOME
from agent_skills.email_tools import get_gmail_service, send_email


RECIPIENT = "chieh.t.wu@gmail.com"
READER_ACCOUNT = "chieh.t.wu@gmail.com"
ALERT_SENDER = "juliaprocess@gmail.com"
NUTRICOST_FROM = "support@nutricost.com"
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


def previous_local_day(now: dt.datetime | None = None) -> dt.date:
    tz = ZoneInfo("America/New_York")
    now = now or dt.datetime.now(tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    return (now.astimezone(tz).date() - dt.timedelta(days=1))


def gmail_date(value: dt.date) -> str:
    return value.strftime("%Y/%m/%d")


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"alerted_message_ids": []}
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return {"alerted_message_ids": []}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = STATE_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp_path.replace(STATE_PATH)


def header_map(message: dict) -> dict[str, str]:
    headers = message.get("payload", {}).get("headers", [])
    return {h.get("name", "").lower(): h.get("value", "") for h in headers}


def decode_body_data(part: dict) -> str:
    import base64

    data = part.get("body", {}).get("data", "")
    if not data:
        return ""
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")


def walk_parts(payload: dict) -> list[dict]:
    parts = [payload]
    for part in payload.get("parts", []) or []:
        parts.extend(walk_parts(part))
    return parts


def strip_html(raw_html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw_html)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def unfold_ics_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw_line.startswith((" ", "\t")) and lines:
            lines[-1] += raw_line[1:]
        else:
            lines.append(raw_line)
    return lines


def message_text(message: dict) -> str:
    payload = message.get("payload", {})
    plain_chunks = []
    html_chunks = []
    for part in walk_parts(payload):
        mime_type = part.get("mimeType", "")
        if mime_type == "text/plain":
            plain_chunks.append(decode_body_data(part))
        elif mime_type == "text/html":
            html_chunks.append(strip_html(decode_body_data(part)))

    if plain_chunks:
        return "\n\n".join(chunk for chunk in plain_chunks if chunk)
    return "\n\n".join(chunk for chunk in html_chunks if chunk)


def message_calendar_text(message: dict) -> str:
    chunks: list[str] = []
    for part in walk_parts(message.get("payload", {})):
        mime_type = str(part.get("mimeType") or "").lower()
        filename = str(part.get("filename") or "").lower()
        if mime_type in {"text/calendar", "application/ics"} or filename.endswith((".ics", ".ical")):
            chunks.append(decode_body_data(part))
    return "\n".join(chunk for chunk in chunks if chunk)


def is_marketing_message(message: dict, text: str) -> bool:
    headers = header_map(message)
    sender = headers.get("from", "")
    if NUTRICOST_FROM not in sender.lower():
        return False
    signals = " ".join(
        [
            headers.get("list-unsubscribe", ""),
            headers.get("list-unsubscribe-post", ""),
            headers.get("feedback-id", ""),
            headers.get("x-kmail-account", ""),
            text[:3000],
        ]
    ).lower()
    return any(
        signal in signals
        for signal in (
            "list-unsubscribe",
            "unsubscribe",
            "klaviyo",
            "kmail",
            "no longer want to receive these emails",
        )
    )


def extract_discounts(text: str) -> list[int]:
    matches: list[int] = []
    patterns = [
        r"\b(\d{1,3})\s*%\s*(?:off|sitewide|discount|deal|savings)?\b",
        r"\b(\d{1,3})\s*percent\s*(?:off|sitewide|discount|deal|savings)?\b",
    ]
    for pattern in patterns:
        for raw in re.findall(pattern, text, flags=re.IGNORECASE):
            value = int(raw)
            if 1 <= value <= 95:
                matches.append(value)
    return matches


def clean_url(url: str) -> str:
    return html.unescape(url).strip().rstrip(").,;\"'")


def extract_deal_links(text: str) -> list[str]:
    urls = [clean_url(match) for match in re.findall(r"https?://[^\s<>)]+", text)]
    excluded = (
        "unsubscribe",
        "manage.kmail-lists.com",
        "facebook.com",
        "instagram.com",
        "youtube.com",
        "tiktok.com",
        "cloudfront.net",
        "our-mission-guarantee",
        "our-misson-guarantee",
    )
    preferred = [
        url
        for url in urls
        if "nutricost.com" in url.lower()
        and not any(fragment in url.lower() for fragment in excluded)
    ]
    fallback = [
        url
        for url in urls
        if not any(fragment in url.lower() for fragment in excluded)
    ]

    deduped: list[str] = []
    for url in preferred + fallback:
        if url not in deduped:
            deduped.append(url)
    return deduped[:5]


def parsed_message_date(headers: dict[str, str]) -> str:
    raw = headers.get("date", "")
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).isoformat()
    except Exception:
        return raw


def message_local_date(message: dict) -> dt.date | None:
    raw = message.get("internalDate")
    if not raw:
        return None
    try:
        timestamp = int(raw) / 1000
    except (TypeError, ValueError):
        return None
    return dt.datetime.fromtimestamp(timestamp, tz=ZoneInfo("America/New_York")).date()


def message_local_datetime(message: dict) -> dt.datetime | None:
    raw = message.get("internalDate")
    if not raw:
        return None
    try:
        timestamp = int(raw) / 1000
    except (TypeError, ValueError):
        return None
    return dt.datetime.fromtimestamp(timestamp, tz=ZoneInfo("America/New_York"))


def sender_matches_fragments(sender: str, fragments: tuple[str, ...]) -> bool:
    sender_lower = str(sender or "").lower()
    return any(fragment.lower() in sender_lower for fragment in fragments)


def sender_matches_domains(sender: str, domains: tuple[str, ...]) -> bool:
    allowed_domains = tuple(domain.lower().lstrip("@") for domain in domains if domain)
    if not allowed_domains:
        return False

    sender_domains: list[str] = []
    for _, address in getaddresses([str(sender or "")]):
        if "@" in address:
            sender_domains.append(address.rsplit("@", 1)[1].strip().lower())

    for sender_domain in sender_domains:
        for allowed_domain in allowed_domains:
            if sender_domain == allowed_domain or sender_domain.endswith(f".{allowed_domain}"):
                return True
    return False


def sender_matches_cleanup_rule(
    sender: str,
    fragments: tuple[str, ...],
    domains: tuple[str, ...] = (),
) -> bool:
    return sender_matches_fragments(sender, fragments) or sender_matches_domains(sender, domains)


def message_is_older_than_days(
    message: dict,
    days: int,
    *,
    now: dt.datetime | None = None,
) -> bool:
    message_dt = message_local_datetime(message)
    if not message_dt:
        return False
    tz = ZoneInfo("America/New_York")
    now = now or dt.datetime.now(tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    return message_dt < now.astimezone(tz) - dt.timedelta(days=days)


def parse_ics_datetime(value: str, params: str = "") -> dt.datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    tz = ZoneInfo("America/New_York")
    value_is_date = "VALUE=DATE" in str(params or "").upper()
    if re.fullmatch(r"\d{8}", raw):
        try:
            parsed_date = dt.datetime.strptime(raw, "%Y%m%d").date()
        except ValueError:
            return None
        return dt.datetime.combine(parsed_date, dt.time.min, tzinfo=tz)

    raw = raw.rstrip("Z")
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M"):
        try:
            parsed = dt.datetime.strptime(raw, fmt)
            return parsed.replace(tzinfo=ZoneInfo("UTC" if value.endswith("Z") else "America/New_York")).astimezone(tz)
        except ValueError:
            continue
    if value_is_date:
        return parse_ics_datetime(raw[:8])
    return None


def calendar_event_end_from_ics(text: str) -> dt.datetime | None:
    event_started = False
    dtstart: dt.datetime | None = None
    dtend: dt.datetime | None = None
    for line in unfold_ics_lines(text):
        clean = line.strip()
        if clean == "BEGIN:VEVENT":
            event_started = True
            dtstart = None
            dtend = None
            continue
        if clean == "END:VEVENT" and event_started:
            return dtend or dtstart
        if not event_started:
            continue
        match = re.match(r"^(DTSTART|DTEND)(?P<params>;[^:]*)?:(?P<value>.+)$", clean, flags=re.IGNORECASE)
        if not match:
            continue
        parsed = parse_ics_datetime(match.group("value"), match.group("params") or "")
        if not parsed:
            continue
        if match.group(1).upper() == "DTEND":
            dtend = parsed
        else:
            dtstart = parsed
    return dtend or dtstart


def parse_subject_time(value: str, fallback_period: str | None = None) -> dt.time | None:
    match = re.fullmatch(r"\s*(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<period>am|pm)?\s*", value, flags=re.IGNORECASE)
    if not match:
        return None
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or "0")
    period = (match.group("period") or fallback_period or "").lower()
    if minute > 59 or hour < 1 or hour > 23:
        return None
    if period:
        if hour > 12:
            return None
        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0
    return dt.time(hour, minute)


def google_calendar_event_end_from_subject(subject: str) -> dt.datetime | None:
    match = re.search(
        r"@\s*"
        r"(?:[A-Z][a-z]{2}\s+)?"
        r"(?P<month>[A-Z][a-z]{2})\s+"
        r"(?P<day>\d{1,2}),\s+"
        r"(?P<year>\d{4})"
        r"(?:\s+"
        r"(?P<start>\d{1,2}(?::\d{2})?\s*(?:am|pm)?)"
        r"(?:\s*-\s*(?P<end>\d{1,2}(?::\d{2})?\s*(?:am|pm)?))?"
        r")?",
        str(subject or ""),
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    try:
        event_date = dt.datetime.strptime(
            f"{match.group('month')} {match.group('day')} {match.group('year')}",
            "%b %d %Y",
        ).date()
    except ValueError:
        return None

    start_text = match.group("start")
    end_text = match.group("end")
    if not start_text:
        return dt.datetime.combine(event_date, dt.time.max, tzinfo=ZoneInfo("America/New_York"))

    start_period_match = re.search(r"(am|pm)\s*$", start_text, flags=re.IGNORECASE)
    start_period = start_period_match.group(1).lower() if start_period_match else None
    start_time = parse_subject_time(start_text)
    end_time = parse_subject_time(end_text or start_text, fallback_period=start_period)
    if not start_time or not end_time:
        return None

    event_end = dt.datetime.combine(event_date, end_time, tzinfo=ZoneInfo("America/New_York"))
    event_start = dt.datetime.combine(event_date, start_time, tzinfo=ZoneInfo("America/New_York"))
    if event_end < event_start:
        event_end += dt.timedelta(days=1)
    return event_end


def google_calendar_event_has_passed(message: dict, *, now: dt.datetime | None = None) -> bool | None:
    calendar_text = message_calendar_text(message)
    subject = header_map(message).get("subject", "")
    event_end = calendar_event_end_from_ics(calendar_text) or google_calendar_event_end_from_subject(subject)
    if not event_end:
        return None
    tz = ZoneInfo("America/New_York")
    now = now or dt.datetime.now(tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    return event_end < now.astimezone(tz)


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
    link_text = "\n".join(f"- {url}" for url in links) or "- No deal link found in the message body."
    body = (
        f"Nutricost deal found.\n\n"
        f"Discount detected: {discount}%\n"
        f"Original subject: {subject}\n"
        f"Original date: {message_date}\n"
        f"Gmail message ID: {message_id}\n\n"
        f"Links:\n{link_text}\n"
    )
    alert_subject = f"Nutricost {discount}% deal"
    if dry_run:
        LOGGER.info("DRY RUN: would send alert from %s: %s", ALERT_SENDER, alert_subject)
        LOGGER.info("DRY RUN alert body:\n%s", body)
        return
    result = send_email(
        to=RECIPIENT,
        subject=alert_subject,
        body=body,
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
    text = "\n\n".join([subject, message.get("snippet", ""), message_text(message)])

    if not is_marketing_message(message, text):
        LOGGER.info("Skipped non-marketing Nutricost message %s: %s", message_id, subject)
        return "skipped"

    discounts = extract_discounts(text)
    best_discount = max(discounts) if discounts else 0
    LOGGER.info("Message %s best discount=%s subject=%s", message_id, best_discount, subject)

    if best_discount < threshold:
        trash_message(service, message_id, dry_run=dry_run)
        return "trashed" if not dry_run else "would_trash"

    alerted = set(state.get("alerted_message_ids", []))
    if message_id in alerted:
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
        alerted.add(message_id)
        state["alerted_message_ids"] = sorted(alerted)
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
    headers = header_map(message)
    sender = headers.get("from", "")
    subject = headers.get("subject", "(no subject)")
    prefix = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or "sender_cleanup"

    if not sender_matches_cleanup_rule(sender, sender_fragments, sender_domains):
        LOGGER.info("Skipped non-%s message %s: from=%s subject=%s", label, message_id, sender, subject)
        return f"{prefix}_skipped"
    if required_label_ids and not set(required_label_ids).issubset(set(message.get("labelIds") or [])):
        LOGGER.info(
            "Skipped %s message without required labels %s: id=%s subject=%s",
            label,
            required_label_ids,
            message_id,
            subject,
        )
        return f"{prefix}_skipped_labels"
    if subject_fragments and not any(fragment.lower() in subject.lower() for fragment in subject_fragments):
        LOGGER.info("Skipped %s message without subject match %s: %s", label, message_id, subject)
        return f"{prefix}_skipped_subject"
    if not message_is_older_than_days(message, older_than_days, now=now):
        LOGGER.info("Skipped recent %s message %s: subject=%s", label, message_id, subject)
        return f"{prefix}_too_recent"

    trash_message(service, message_id, dry_run=dry_run)
    action = "Would trash" if dry_run else "Trashed"
    LOGGER.info("%s %s message older than %d days %s: %s", action, label, older_than_days, message_id, subject)
    return f"{prefix}_trashed" if not dry_run else f"{prefix}_would_trash"


def process_google_calendar_message(
    service,
    message_id: str,
    *,
    dry_run: bool,
    now: dt.datetime | None = None,
) -> str:
    message = read_message(service, message_id)
    headers = header_map(message)
    sender = headers.get("from", "")
    subject = headers.get("subject", "(no subject)")
    if not sender_matches_fragments(sender, GOOGLE_CALENDAR_SENDER_FRAGMENTS):
        LOGGER.info("Skipped non-Google Calendar message %s: from=%s subject=%s", message_id, sender, subject)
        return "google_calendar_skipped"

    event_has_passed = google_calendar_event_has_passed(message, now=now)
    if event_has_passed is None:
        LOGGER.info("Skipped Google Calendar message with no parseable event date %s: %s", message_id, subject)
        return "google_calendar_no_event_date"
    if not event_has_passed:
        LOGGER.info("Skipped future Google Calendar event message %s: %s", message_id, subject)
        return "google_calendar_future_event"

    trash_message(service, message_id, dry_run=dry_run)
    LOGGER.info("Trashed Google Calendar message for passed event %s: %s", message_id, subject)
    return "google_calendar_trashed" if not dry_run else "google_calendar_would_trash"


def process_unread_cleanup_message(
    service,
    message_id: str,
    *,
    older_than_days: int,
    dry_run: bool,
    now: dt.datetime | None = None,
) -> str:
    message = read_message(service, message_id)
    subject = header_map(message).get("subject", "(no subject)")
    if "UNREAD" not in (message.get("labelIds") or []):
        LOGGER.info("Skipped read message from unread cleanup %s: %s", message_id, subject)
        return "old_unread_skipped_read"
    if not message_is_older_than_days(message, older_than_days, now=now):
        LOGGER.info("Skipped recent unread message %s: %s", message_id, subject)
        return "old_unread_too_recent"

    trash_message(service, message_id, dry_run=dry_run)
    LOGGER.info("Trashed unread message older than %d days %s: %s", older_than_days, message_id, subject)
    return "old_unread_trashed" if not dry_run else "old_unread_would_trash"


def build_sender_query(day: dt.date, from_query: str, include_trash: bool) -> str:
    # Gmail date queries are not enough for local-day precision. Use a wider
    # search window, then filter by each message's internalDate in New York.
    query_start = day - dt.timedelta(days=1)
    query_end = day + dt.timedelta(days=2)
    parts = [
        "in:anywhere" if include_trash else "",
        f"to:{RECIPIENT}",
        f"from:{from_query}",
        f"after:{gmail_date(query_start)}",
        f"before:{gmail_date(query_end)}",
        "-in:spam",
    ]
    if not include_trash:
        parts.append("-in:trash")
    return " ".join(part for part in parts if part)


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
    parts = [
        "in:anywhere" if include_trash else "",
        f"to:{RECIPIENT}",
        f"from:{from_query}",
        *extra_terms,
        f"older_than:{int(older_than_days)}d",
        "-in:spam",
    ]
    if not include_trash:
        parts.append("-in:trash")
    return " ".join(part for part in parts if part)


def build_google_calendar_query(include_trash: bool) -> str:
    parts = [
        "in:anywhere" if include_trash else "",
        f"to:{RECIPIENT}",
        f"from:{GOOGLE_CALENDAR_FROM_QUERY}",
        "-in:spam",
    ]
    if not include_trash:
        parts.append("-in:trash")
    return " ".join(part for part in parts if part)


def build_unread_cleanup_query(older_than_days: int, include_trash: bool) -> str:
    parts = [
        "in:anywhere" if include_trash else "",
        "is:unread",
        f"older_than:{int(older_than_days)}d",
        "-in:spam",
    ]
    if not include_trash:
        parts.append("-in:trash")
    return " ".join(part for part in parts if part)


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
    for message_id in message_ids:
        try:
            outcome = process_message(service, message_id, day, args.threshold, args.dry_run, state)
        except Exception as exc:
            LOGGER.exception("Failed processing %s: %s", message_id, exc)
            outcome = "failed"
        counts[outcome] = counts.get(outcome, 0) + 1

    crunchlabs_query = build_crunchlabs_query(day, include_trash=args.include_trash)
    LOGGER.info("Scanning CrunchLabs messages for %s with query: %s", day.isoformat(), crunchlabs_query)
    crunchlabs_message_ids = list_message_ids(service, crunchlabs_query)
    LOGGER.info("Found %d CrunchLabs candidate message(s)", len(crunchlabs_message_ids))
    for message_id in crunchlabs_message_ids:
        try:
            outcome = process_crunchlabs_message(service, message_id, day, args.dry_run)
        except Exception as exc:
            LOGGER.exception("Failed processing CrunchLabs message %s: %s", message_id, exc)
            outcome = "crunchlabs_failed"
        counts[outcome] = counts.get(outcome, 0) + 1

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
        for message_id in cleanup_message_ids:
            try:
                outcome = process_sender_cleanup_message(
                    service,
                    message_id,
                    label=spec.label,
                    sender_fragments=spec.sender_fragments,
                    sender_domains=spec.sender_domains,
                    older_than_days=spec.retention_days,
                    dry_run=args.dry_run,
                    subject_fragments=spec.subject_fragments,
                    required_label_ids=spec.required_label_ids,
                )
            except Exception as exc:
                LOGGER.exception("Failed processing %s message %s: %s", spec.label, message_id, exc)
                outcome = f"{re.sub(r'[^a-z0-9]+', '_', spec.label.lower()).strip('_')}_failed"
            counts[outcome] = counts.get(outcome, 0) + 1

    google_calendar_query = build_google_calendar_query(include_trash=args.include_trash)
    LOGGER.info("Scanning Google Calendar messages with query: %s", google_calendar_query)
    google_calendar_message_ids = list_message_ids(service, google_calendar_query)
    LOGGER.info("Found %d Google Calendar candidate message(s)", len(google_calendar_message_ids))
    for message_id in google_calendar_message_ids:
        try:
            outcome = process_google_calendar_message(service, message_id, dry_run=args.dry_run)
        except Exception as exc:
            LOGGER.exception("Failed processing Google Calendar message %s: %s", message_id, exc)
            outcome = "google_calendar_failed"
        counts[outcome] = counts.get(outcome, 0) + 1

    unread_query = build_unread_cleanup_query(UNREAD_CLEANUP_RETENTION_DAYS, include_trash=args.include_trash)
    LOGGER.info("Scanning unread messages older than %d days with query: %s", UNREAD_CLEANUP_RETENTION_DAYS, unread_query)
    unread_message_ids = list_message_ids(service, unread_query)
    LOGGER.info("Found %d old unread candidate message(s)", len(unread_message_ids))
    if args.dry_run:
        if unread_message_ids:
            counts["old_unread_would_trash"] = counts.get("old_unread_would_trash", 0) + len(unread_message_ids)
        LOGGER.info("DRY RUN: would trash %d unread message(s) older than %d days", len(unread_message_ids), UNREAD_CLEANUP_RETENTION_DAYS)
    else:
        for message_id in unread_message_ids:
            try:
                trash_message(service, message_id, dry_run=False)
                outcome = "old_unread_trashed"
            except Exception as exc:
                LOGGER.exception("Failed processing old unread message %s: %s", message_id, exc)
                outcome = "old_unread_failed"
            counts[outcome] = counts.get(outcome, 0) + 1

    if not args.dry_run:
        save_state(state)
    LOGGER.info("Done: %s", counts)
    return 1 if any(str(key).endswith("failed") for key in counts) else 0


if __name__ == "__main__":
    raise SystemExit(main())
