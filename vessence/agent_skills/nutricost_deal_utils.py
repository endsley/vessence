"""Nutricost marketing email parsing helpers."""
from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import html
import re

from agent_skills.gmail_message_utils import header_map, message_text


NUTRICOST_FROM = "support@nutricost.com"
DEAL_ALERT_DEDUPLICATION_WINDOW = dt.timedelta(days=3)


@dataclass(frozen=True)
class DealAlertContent:
    subject: str
    body: str


def default_monitor_state() -> dict:
    return {"alerted_message_ids": [], "recent_deal_alerts": []}


def alerted_message_ids(state: dict) -> set:
    return set((state or {}).get("alerted_message_ids", []))


def record_alerted_message(state: dict, message_id: str) -> None:
    alerted = alerted_message_ids(state)
    alerted.add(message_id)
    state["alerted_message_ids"] = sorted(alerted)


def deal_key(discount: int, text: str) -> str:
    """Return a stable identity for an advertised deal.

    A promo code distinguishes separate offers with the same percentage. When
    no code is advertised, the percentage is the only reliable deal identity
    available in a marketing message.
    """
    normalized = " ".join(text.lower().split())
    code_patterns = (
        r"\b(?:use|with|enter)\s+(?:promo(?:tional)?\s+)?code\s*[:#-]?\s*[\"']?([a-z0-9]{4,24})\b",
        r"\b(?:promo(?:tional)?\s+)?code\s*[:#-]\s*[\"']?([a-z0-9]{4,24})\b",
    )
    for pattern in code_patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            return f"discount:{discount};code:{match.group(1).upper()}"
    return f"discount:{discount}"


def _as_utc(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


def _alerted_at(entry: object) -> dt.datetime | None:
    if not isinstance(entry, dict):
        return None
    value = entry.get("alerted_at")
    if not isinstance(value, str):
        return None
    try:
        return _as_utc(dt.datetime.fromisoformat(value))
    except ValueError:
        return None


def deal_alerted_within(
    state: dict,
    key: str,
    *,
    now: dt.datetime,
    window: dt.timedelta = DEAL_ALERT_DEDUPLICATION_WINDOW,
) -> bool:
    """Whether the same deal was emailed during the deduplication window."""
    cutoff = _as_utc(now) - window
    for entry in (state or {}).get("recent_deal_alerts", []):
        if not isinstance(entry, dict) or entry.get("deal_key") != key:
            continue
        alerted_at = _alerted_at(entry)
        if alerted_at is not None and alerted_at >= cutoff:
            return True
    return False


def record_deal_alert(
    state: dict,
    *,
    message_id: str,
    key: str,
    alerted_at: dt.datetime,
    window: dt.timedelta = DEAL_ALERT_DEDUPLICATION_WINDOW,
) -> None:
    """Record an alert and retain only history relevant to duplicate checks."""
    record_alerted_message(state, message_id)
    recorded_at = _as_utc(alerted_at)
    cutoff = recorded_at - window
    history = []
    for entry in state.get("recent_deal_alerts", []):
        existing_at = _alerted_at(entry)
        if existing_at is not None and existing_at >= cutoff:
            history.append(entry)
    history.append({"deal_key": key, "alerted_at": recorded_at.isoformat()})
    state["recent_deal_alerts"] = history


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


def best_detected_discount(text: str) -> int:
    discounts = extract_discounts(text)
    return max(discounts) if discounts else 0


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


def nutricost_message_text(message: dict, subject: str) -> str:
    return "\n\n".join([subject, message.get("snippet", ""), message_text(message)])


def build_deal_alert_content(
    *,
    subject: str,
    message_date: str,
    discount: int,
    links: list[str],
    message_id: str,
) -> DealAlertContent:
    link_text = "\n".join(f"- {url}" for url in links) or "- No deal link found in the message body."
    body = (
        f"Nutricost deal found.\n\n"
        f"Discount detected: {discount}%\n"
        f"Original subject: {subject}\n"
        f"Original date: {message_date}\n"
        f"Gmail message ID: {message_id}\n\n"
        f"Links:\n{link_text}\n"
    )
    return DealAlertContent(subject=f"Nutricost {discount}% deal", body=body)
