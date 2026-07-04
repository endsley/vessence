"""Conversation classification rules for Facebook Marketplace cleanup."""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Conversation:
    href: str
    title: str
    raw_text: str
    label: str = ""
    age_days: int | None = None


@dataclass(frozen=True)
class Decision:
    action: str
    reason: str


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def normalize_title(value: str) -> str:
    text = _clean_text(value)
    text = re.sub(r"^group chat:\s*", "", text, flags=re.I)
    text = text.replace("\u00b7", " ").replace("\\u00b7", " ").replace(":", " ")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def is_protected_title(title: str, keep_titles: Iterable[str]) -> bool:
    normalized = normalize_title(title)
    for keep_title in keep_titles:
        keep = normalize_title(keep_title)
        if keep and (normalized == keep or keep in normalized):
            return True
    return False


def extract_title(label: str, raw_text: str) -> str:
    label = _clean_text(label)
    if label:
        return re.sub(r"^group chat:\s*", "", label, flags=re.I).strip()
    first_line = str(raw_text or "").replace("\r", "\n").split("\n")[0]
    return _clean_text(first_line)


def conversation_from_row(row: dict) -> Conversation | None:
    raw_text = _clean_text(row.get("text", ""))
    label = _clean_text(row.get("label", ""))
    title = extract_title(label, raw_text)
    href = str(row.get("href") or "")
    if not href or not title:
        return None
    return Conversation(
        href=href,
        title=title,
        raw_text=raw_text,
        label=label,
        age_days=parse_relative_age_days(raw_text),
    )


RECENT_UNIT_AGE_DAYS = {
    "m": 0,
    "min": 0,
    "mins": 0,
    "minute": 0,
    "minutes": 0,
    "h": 0,
    "hr": 0,
    "hrs": 0,
    "hour": 0,
    "hours": 0,
    "d": 1,
    "day": 1,
    "days": 1,
    "w": 7,
    "wk": 7,
    "wks": 7,
    "week": 7,
    "weeks": 7,
    "mo": 30,
    "mon": 30,
    "month": 30,
    "months": 30,
    "y": 365,
    "yr": 365,
    "yrs": 365,
    "year": 365,
    "years": 365,
}
MONTH_LABELS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
WEEKDAY_LABELS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _relative_unit_age_days(amount_text: str, unit: str) -> int:
    return int(amount_text) * RECENT_UNIT_AGE_DAYS[unit]


def _relative_unit_matches_age_days(matches: list[tuple[str, str]]) -> int | None:
    parsed = [_relative_unit_age_days(amount_text, unit) for amount_text, unit in matches]
    return max(parsed) if parsed else None


def _month_label_age_days(cleaned: str, now: dt.datetime) -> int | None:
    for month_name in MONTH_LABELS:
        match = re.search(rf"\b{month_name}\s+(\d{{1,2}})(?:,\s*(\d{{4}}))?\b", cleaned)
        if not match:
            continue
        month = dt.datetime.strptime(month_name, "%b").month
        year = int(match.group(2) or now.year)
        seen = dt.date(year, month, int(match.group(1)))
        if seen > now.date():
            seen = dt.date(year - 1, month, int(match.group(1)))
        return max((now.date() - seen).days, 0)
    return None


def _weekday_label_age_days(cleaned: str, now: dt.datetime) -> int | None:
    weekday_match = re.search(
        r"\b(mon|tue|wed|thu|fri|sat|sun)(?:day)?\b",
        cleaned,
    )
    if not weekday_match:
        return None
    weekday = WEEKDAY_LABELS.index(weekday_match.group(1)[:3])
    age = (now.weekday() - weekday) % 7
    return age or None


def parse_relative_age_days(text: str, *, now: dt.datetime | None = None) -> int | None:
    """Parse Facebook list timestamps such as 4d, 1w, Yesterday, or Jun 25."""
    cleaned = _clean_text(text).casefold()
    if not cleaned:
        return None

    if re.search(r"\btoday\b|\bnow\b", cleaned):
        return 0
    if re.search(r"\byesterday\b", cleaned):
        return 1

    matches = re.findall(
        r"(?<![a-z0-9])(\d{1,3})\s*"
        r"(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|"
        r"w|wk|wks|week|weeks|mo|mon|month|months|y|yr|yrs|year|years)"
        r"\b",
        cleaned,
    )
    unit_age_days = _relative_unit_matches_age_days(matches)
    if unit_age_days is not None:
        return unit_age_days

    now = now or dt.datetime.now()
    month_age_days = _month_label_age_days(cleaned, now)
    if month_age_days is not None:
        return month_age_days

    return _weekday_label_age_days(cleaned, now)


SOLD_OR_GONE_PATTERNS = (
    re.compile(r"\b[A-Za-z][A-Za-z0-9' -]{0,40}\s+sold\s+.{3,120}", re.I),
    re.compile(r"\b(marked|set|listed).{0,50}\bsold\b", re.I),
    re.compile(r"\b(has been|was|already|just|now)\s+sold\b", re.I),
    re.compile(r"\b(i|we|you)\s+(sold|have sold|just sold|already sold)\b", re.I),
    re.compile(r"\b(no longer|not)\s+available\b", re.I),
    re.compile(r"\bitem\s+(is\s+)?unavailable\b", re.I),
    re.compile(r"\blisting\s+(is\s+)?unavailable\b", re.I),
    re.compile(r"\bremoved\s+(the\s+)?listing\b", re.I),
    re.compile(r"\bit(?:'s| is)\s+gone\b", re.I),
)


def looks_sold_or_gone(text: str) -> bool:
    cleaned = _clean_text(text)
    if not cleaned:
        return False
    if re.fullmatch(r".*\bis\s+(it|this|that)\s+sold\??\s*", cleaned, flags=re.I):
        return False
    return any(pattern.search(cleaned) for pattern in SOLD_OR_GONE_PATTERNS)


def classify_conversation(
    conversation: Conversation,
    *,
    keep_titles: Iterable[str],
    stale_days: int = 3,
) -> Decision:
    if is_protected_title(conversation.title, keep_titles):
        return Decision("keep", "protected_title")
    if looks_sold_or_gone(conversation.raw_text):
        return Decision("delete", "sold_or_gone_signal")
    if conversation.age_days is not None and conversation.age_days >= stale_days:
        return Decision("delete", f"stale_{conversation.age_days}d")
    return Decision("keep", "no_delete_signal")


def classify_conversations(
    conversations: Iterable[Conversation],
    *,
    keep_titles: Iterable[str],
    stale_days: int = 3,
) -> list[tuple[Conversation, Decision]]:
    return [
        (
            conversation,
            classify_conversation(
                conversation,
                keep_titles=keep_titles,
                stale_days=stale_days,
            ),
        )
        for conversation in conversations
    ]


def select_delete_candidates(
    classified: Iterable[tuple[Conversation, Decision]],
    *,
    max_delete: int,
) -> list[tuple[Conversation, Decision]]:
    candidates = [
        (conversation, decision)
        for conversation, decision in classified
        if decision.action == "delete"
    ]
    delete_limit = max(max_delete, 0)
    if delete_limit:
        return candidates[:delete_limit]
    return []
