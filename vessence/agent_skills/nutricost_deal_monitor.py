#!/usr/bin/env python3
"""Daily Nutricost marketing deal monitor.

At 5 AM, scan yesterday's Nutricost marketing emails. Trash messages whose
largest advertised discount is below the threshold. For qualifying messages,
send Chieh a link from the juliaprocess Gmail account.
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
from email.utils import parsedate_to_datetime
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
STATE_PATH = Path(VESSENCE_DATA_HOME) / "data" / "nutricost_deal_monitor.json"

LOGGER = logging.getLogger("nutricost_deal_monitor")


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


def build_query(day: dt.date, include_trash: bool) -> str:
    # Gmail date queries are not enough for local-day precision. Use a wider
    # search window, then filter by each message's internalDate in New York.
    query_start = day - dt.timedelta(days=1)
    query_end = day + dt.timedelta(days=2)
    parts = [
        "in:anywhere" if include_trash else "",
        f"to:{RECIPIENT}",
        f"from:{NUTRICOST_FROM}",
        f"after:{gmail_date(query_start)}",
        f"before:{gmail_date(query_end)}",
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
    if not message_ids:
        return 0

    state = load_state()
    counts: dict[str, int] = {}
    for message_id in message_ids:
        try:
            outcome = process_message(service, message_id, day, args.threshold, args.dry_run, state)
        except Exception as exc:
            LOGGER.exception("Failed processing %s: %s", message_id, exc)
            outcome = "failed"
        counts[outcome] = counts.get(outcome, 0) + 1

    if not args.dry_run:
        save_state(state)
    LOGGER.info("Done: %s", counts)
    return 1 if counts.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
