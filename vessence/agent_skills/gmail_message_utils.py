"""Message parsing helpers shared by Gmail cleanup scripts."""
from __future__ import annotations

import datetime as dt
import html
import re
from email.utils import getaddresses, parsedate_to_datetime
from zoneinfo import ZoneInfo


NY_TZ = ZoneInfo("America/New_York")


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
    return dt.datetime.fromtimestamp(timestamp, tz=NY_TZ).date()


def message_local_datetime(message: dict) -> dt.datetime | None:
    raw = message.get("internalDate")
    if not raw:
        return None
    try:
        timestamp = int(raw) / 1000
    except (TypeError, ValueError):
        return None
    return dt.datetime.fromtimestamp(timestamp, tz=NY_TZ)


def ny_aware_datetime(value: dt.datetime | None = None) -> dt.datetime:
    if value is None:
        return dt.datetime.now(NY_TZ)
    if value.tzinfo is None:
        return value.replace(tzinfo=NY_TZ)
    return value.astimezone(NY_TZ)


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
    return message_dt < ny_aware_datetime(now) - dt.timedelta(days=days)


def parse_ics_datetime(value: str, params: str = "") -> dt.datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    tz = NY_TZ
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


GOOGLE_CALENDAR_SUBJECT_RE = re.compile(
    r"@\s*"
    r"(?:[A-Z][a-z]{2}\s+)?"
    r"(?P<month>[A-Z][a-z]{2})\s+"
    r"(?P<day>\d{1,2}),\s+"
    r"(?P<year>\d{4})"
    r"(?:\s+"
    r"(?P<start>\d{1,2}(?::\d{2})?\s*(?:am|pm)?)"
    r"(?:\s*-\s*(?P<end>\d{1,2}(?::\d{2})?\s*(?:am|pm)?))?"
    r")?",
    flags=re.IGNORECASE,
)


def google_calendar_subject_match(subject: str) -> re.Match | None:
    return GOOGLE_CALENDAR_SUBJECT_RE.search(str(subject or ""))


def google_calendar_subject_date(match: re.Match) -> dt.date | None:
    try:
        return dt.datetime.strptime(
            f"{match.group('month')} {match.group('day')} {match.group('year')}",
            "%b %d %Y",
        ).date()
    except ValueError:
        return None


def google_calendar_subject_times(match: re.Match) -> tuple[dt.time, dt.time] | None:
    start_text = match.group("start")
    end_text = match.group("end")
    if not start_text:
        return None

    start_period_match = re.search(r"(am|pm)\s*$", start_text, flags=re.IGNORECASE)
    start_period = start_period_match.group(1).lower() if start_period_match else None
    start_time = parse_subject_time(start_text)
    end_time = parse_subject_time(end_text or start_text, fallback_period=start_period)
    if not start_time or not end_time:
        return None
    return start_time, end_time


def google_calendar_event_end_from_subject(subject: str) -> dt.datetime | None:
    match = google_calendar_subject_match(subject)
    if not match:
        return None

    event_date = google_calendar_subject_date(match)
    if not event_date:
        return None

    times = google_calendar_subject_times(match)
    if not times:
        return dt.datetime.combine(event_date, dt.time.max, tzinfo=NY_TZ)

    start_time, end_time = times
    event_end = dt.datetime.combine(event_date, end_time, tzinfo=NY_TZ)
    event_start = dt.datetime.combine(event_date, start_time, tzinfo=NY_TZ)
    if event_end < event_start:
        event_end += dt.timedelta(days=1)
    return event_end


def google_calendar_event_has_passed(message: dict, *, now: dt.datetime | None = None) -> bool | None:
    calendar_text = message_calendar_text(message)
    subject = header_map(message).get("subject", "")
    event_end = calendar_event_end_from_ics(calendar_text) or google_calendar_event_end_from_subject(subject)
    if not event_end:
        return None
    return event_end < ny_aware_datetime(now)
