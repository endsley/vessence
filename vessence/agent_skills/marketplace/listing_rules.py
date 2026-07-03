"""Pure listing parsing and filtering rules for Marketplace harvesting."""
from __future__ import annotations

import re


CURRENT_YEAR = 2026
MILES_PATTERNS = (
    re.compile(r"(\d{1,3}(?:,\d{3})+)\s*(?:mi(?:les)?\b|\.)", re.I),
    re.compile(r"(\d{2,3})\s*[kK]\s*(?:mi(?:les)?\b|\.)", re.I),
    re.compile(r"\b(\d{4,6})\s*mi(?:les)?\b", re.I),
    re.compile(r"\bmileage[^\d]{0,15}(\d{1,3}(?:,\d{3})+|\d{4,6})", re.I),
    re.compile(r"\bdriven\s+(\d{1,3}(?:,\d{3})+|\d{4,6})", re.I),
)
BAD_TITLE_KEYWORDS = (
    "salvage title",
    "rebuilt title",
    "reconstructed title",
    "branded title",
    "lemon title",
    "rebuilt/salvage",
)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "query"


def parse_year(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"\b(19\d{2}|20[0-2]\d)\b", value)
    return int(match.group()) if match else None


def parse_miles(text: str | None) -> int | None:
    if not text:
        return None
    for pattern in MILES_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        raw = match.group(1).replace(",", "")
        try:
            miles = int(raw)
        except ValueError:
            continue
        if pattern.pattern.startswith("(\\d{2,3})\\s*[kK]"):
            miles *= 1000
        if 100 <= miles <= 600_000:
            return miles
    return None


def is_suspicious(year: int | None, miles: int) -> tuple[bool, str]:
    if year is None or not miles:
        return False, ""
    age = CURRENT_YEAR - year
    if age <= 5:
        return False, ""
    avg = miles / max(age, 1)
    if avg < 3000:
        return True, f"implausibly low miles: {miles}mi / {age}yr = {avg:.0f}/yr"
    return False, ""


def title_filter_result(description: str, *, require_clean_title: bool = True) -> tuple[bool, bool, bool]:
    lower = description.lower()
    has_clean = "clean title" in lower
    has_bad = any(keyword in lower for keyword in BAD_TITLE_KEYWORDS)
    if require_clean_title:
        return has_clean and not has_bad, has_clean, has_bad
    return not has_bad, has_clean, has_bad
