"""Pure helpers for SMS readback and TalkingPoints wrapper extraction."""
from __future__ import annotations

from typing import Any
import base64
import re
from urllib.parse import urlparse

from jane.sanitizers import strip_client_tool_markers


TALKINGPOINTS_URL_RE = re.compile(
    r"https?://(?:app|families)\.talkingpts\.org/(?:U|m)/[A-Za-z0-9_.$%-]+",
    re.IGNORECASE,
)
WRAPPER_BODY_RE = re.compile(
    r"\b(?:has sent you a message|view the full message|full message here)\b",
    re.IGNORECASE,
)
MUSIC_PLAY_MARKER_RE = re.compile(r"\[MUSIC_PLAY:", re.IGNORECASE)
MAX_READBACK_CHARS = 1200


def find_talkingpoints_url(text: str) -> str | None:
    match = TALKINGPOINTS_URL_RE.search(text or "")
    return match.group(0) if match else None


def looks_like_wrapper(body: str) -> bool:
    return bool(WRAPPER_BODY_RE.search(body or ""))


def sanitize_untrusted_text(text: str) -> str:
    text = strip_client_tool_markers(text or "") or ""
    return MUSIC_PLAY_MARKER_RE.sub("[MUSIC-PLAY-STRIPPED:", text)


def truncate_readback(text: str) -> str:
    text = sanitize_untrusted_text(text)
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= MAX_READBACK_CHARS:
        return text
    return text[:MAX_READBACK_CHARS].rstrip() + "..."


def decode_urlsafe_base64(value: str) -> str | None:
    try:
        padding = "=" * ((4 - len(value) % 4) % 4)
        decoded = base64.urlsafe_b64decode((value + padding).encode("ascii")).decode(
            "utf-8"
        )
    except Exception:
        return None
    return decoded if "_$_" in decoded else None


def talkingpoints_code_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) >= 2 and path_parts[0] in {"U", "m"}:
        return path_parts[1].strip().strip("/") or None
    return None


def talkingpoints_code_candidates_from_urls(urls: list[str]) -> list[str]:
    candidates: list[str] = []

    def add(value: str | None) -> None:
        if not value:
            return
        value = value.strip().strip("/")
        if value and value not in candidates:
            candidates.append(value)

    for url in urls:
        add(talkingpoints_code_from_url(url))

    for code in list(candidates):
        add(decode_urlsafe_base64(code))

    return candidates


def clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = re.sub(r"\s+", " ", value).strip()
    return text or None


def looks_like_error_message(text: str) -> bool:
    lowered = (text or "").lower()
    return any(
        phrase in lowered
        for phrase in (
            "oops, an error occurred",
            "invalid",
            "not found",
            "expired",
        )
    )


def extract_talkingpoints_message(data: Any) -> str | None:
    if isinstance(data, dict):
        teacher = clean_text(data.get("teacherName") or data.get("teacher_name"))
        message = clean_text(data.get("message"))
        if teacher and message and not looks_like_error_message(message):
            return f"{teacher}: {message}"

        contact = data.get("contact")
        if isinstance(contact, dict):
            extracted = extract_talkingpoints_message(contact)
            if extracted:
                return extracted

        nested = data.get("data")
        if isinstance(nested, (dict, list)):
            extracted = extract_talkingpoints_message(nested)
            if extracted:
                return extracted

        for value in data.values():
            if isinstance(value, (dict, list)):
                extracted = extract_talkingpoints_message(value)
                if extracted:
                    return extracted
    elif isinstance(data, list):
        for item in data:
            extracted = extract_talkingpoints_message(item)
            if extracted:
                return extracted
    return None


def readback_cache_ttl_seconds(
    *,
    resolved: Any,
    success_ttl_seconds: int,
    failed_ttl_seconds: int,
) -> int:
    return success_ttl_seconds if resolved else failed_ttl_seconds


def readback_cache_entry_is_fresh(*, checked_at: float, now: float, ttl_seconds: int) -> bool:
    return now - checked_at <= ttl_seconds


def cache_entry_readback_value(
    entry: Any,
    *,
    now: float,
    success_ttl_seconds: int,
    failed_ttl_seconds: int,
    cache_miss: Any,
) -> str | Any | None:
    if not isinstance(entry, dict):
        return cache_miss
    checked_at = float(entry.get("checked_at") or 0)
    resolved = entry.get("resolved")
    ttl = readback_cache_ttl_seconds(
        resolved=resolved,
        success_ttl_seconds=success_ttl_seconds,
        failed_ttl_seconds=failed_ttl_seconds,
    )
    if not readback_cache_entry_is_fresh(checked_at=checked_at, now=now, ttl_seconds=ttl):
        return cache_miss
    return resolved or None
