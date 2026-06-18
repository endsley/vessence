"""Prepare synced SMS rows for Jane readback."""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_TALKINGPOINTS_URL_RE = re.compile(
    r"https?://(?:app|families)\.talkingpts\.org/(?:U|m)/[A-Za-z0-9_.$%-]+",
    re.IGNORECASE,
)
_WRAPPER_BODY_RE = re.compile(
    r"\b(?:has sent you a message|view the full message|full message here)\b",
    re.IGNORECASE,
)
_CLIENT_TOOL_MARKER_RE = re.compile(r"\[\[CLIENT_TOOL:", re.IGNORECASE)
_MUSIC_PLAY_MARKER_RE = re.compile(r"\[MUSIC_PLAY:", re.IGNORECASE)
_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
_FAILED_CACHE_TTL_SECONDS = 60 * 60
_REQUEST_TIMEOUT_SECONDS = 6
_MAX_READBACK_CHARS = 1200
_CACHE_MISS = object()


def enrich_synced_messages_for_readback(
    messages: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [enrich_synced_message_for_readback(message) for message in messages]


def enrich_synced_message_for_readback(message: Mapping[str, Any]) -> dict[str, Any]:
    enriched = dict(message)
    body = str(enriched.get("body") or "").strip()
    readback = body
    resolution = "sms_body"

    url = _find_talkingpoints_url(body)
    if url:
        resolved = resolve_talkingpoints_link(url)
        if resolved:
            readback = resolved
            resolution = "talkingpoints_link"
        elif _looks_like_wrapper(body):
            readback = (
                "[UNRESOLVED TalkingPoints wrapper] The SMS notification points "
                "to a TalkingPoints link, but the linked message content could "
                "not be opened automatically. Do not read the notification text "
                "as the actual message body."
            )
            resolution = "unresolved_talkingpoints_link"
        else:
            resolution = "unresolved_talkingpoints_link"

    enriched["body_for_readback"] = _truncate_readback(readback)
    if resolution != "sms_body":
        enriched["body_resolution"] = resolution
        enriched["source_url"] = url
    return enriched


def body_for_readback_prompt(message: Mapping[str, Any], max_chars: int = 800) -> str:
    enriched = enrich_synced_message_for_readback(message)
    body = str(enriched.get("body_for_readback") or enriched.get("body") or "").strip()
    if len(body) > max_chars:
        return body[:max_chars].rstrip() + "..."
    return body


def resolve_talkingpoints_link(url: str) -> str | None:
    url = (url or "").strip()
    if not url:
        return None

    cached = _read_cache_entry(url)
    if cached is not _CACHE_MISS:
        return cached or None

    resolved: str | None = None
    try:
        for code in _talkingpoints_code_candidates(url):
            resolved = _resolve_talkingpoints_code(code)
            if resolved:
                break
        if not resolved:
            resolved = _extract_static_page_text(url)
    except Exception as e:
        logger.info("TalkingPoints resolver failed for %s: %s", url, e)
        resolved = None

    _write_cache_entry(url, resolved)
    return resolved


def _find_talkingpoints_url(text: str) -> str | None:
    match = _TALKINGPOINTS_URL_RE.search(text or "")
    return match.group(0) if match else None


def _looks_like_wrapper(body: str) -> bool:
    return bool(_WRAPPER_BODY_RE.search(body or ""))


def _truncate_readback(text: str) -> str:
    text = _sanitize_untrusted_text(text)
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= _MAX_READBACK_CHARS:
        return text
    return text[:_MAX_READBACK_CHARS].rstrip() + "..."


def _sanitize_untrusted_text(text: str) -> str:
    text = _CLIENT_TOOL_MARKER_RE.sub("[[CLIENT-TOOL-STRIPPED:", text or "")
    return _MUSIC_PLAY_MARKER_RE.sub("[MUSIC-PLAY-STRIPPED:", text)


def _talkingpoints_code_candidates(url: str) -> list[str]:
    candidates: list[str] = []

    def add(value: str | None) -> None:
        if not value:
            return
        value = value.strip().strip("/")
        if value and value not in candidates:
            candidates.append(value)

    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) >= 2 and path_parts[0] in {"U", "m"}:
        add(path_parts[1])

    try:
        import requests

        response = requests.get(
            url,
            headers=_browser_headers(),
            timeout=_REQUEST_TIMEOUT_SECONDS,
            allow_redirects=True,
        )
        final = urlparse(response.url)
        final_parts = [part for part in final.path.split("/") if part]
        if len(final_parts) >= 2 and final_parts[0] in {"U", "m"}:
            add(final_parts[1])
    except Exception:
        pass

    for code in list(candidates):
        decoded = _decode_urlsafe_base64(code)
        if decoded:
            add(decoded)

    return candidates


def _decode_urlsafe_base64(value: str) -> str | None:
    try:
        padding = "=" * ((4 - len(value) % 4) % 4)
        decoded = base64.urlsafe_b64decode((value + padding).encode("ascii")).decode(
            "utf-8"
        )
    except Exception:
        return None
    return decoded if "_$_" in decoded else None


def _resolve_talkingpoints_code(code: str) -> str | None:
    try:
        import requests
    except Exception:
        return None

    payload = {"code": code}
    for base in (
        "https://app.talkingpts.org/api/parents/",
        "https://helios.talkingpts.org/api/parents/",
        "https://icarus.talkingpts.org/api/parents/",
    ):
        try:
            response = requests.post(
                base + "auth/login_with_deeplink_code",
                data=json.dumps(payload),
                headers=_api_headers(),
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
        except Exception:
            continue
        content_type = response.headers.get("content-type", "")
        if response.status_code != 200 or "application/json" not in content_type:
            continue
        try:
            data = response.json()
        except Exception:
            continue
        extracted = _extract_talkingpoints_message(data)
        if extracted:
            return extracted
    return None


def _extract_talkingpoints_message(data: Any) -> str | None:
    if isinstance(data, dict):
        teacher = _clean_text(data.get("teacherName") or data.get("teacher_name"))
        message = _clean_text(data.get("message"))
        if teacher and message and not _looks_like_error_message(message):
            return f"{teacher}: {message}"

        contact = data.get("contact")
        if isinstance(contact, dict):
            extracted = _extract_talkingpoints_message(contact)
            if extracted:
                return extracted

        nested = data.get("data")
        if isinstance(nested, (dict, list)):
            extracted = _extract_talkingpoints_message(nested)
            if extracted:
                return extracted

        for value in data.values():
            if isinstance(value, (dict, list)):
                extracted = _extract_talkingpoints_message(value)
                if extracted:
                    return extracted
    elif isinstance(data, list):
        for item in data:
            extracted = _extract_talkingpoints_message(item)
            if extracted:
                return extracted
    return None


def _extract_static_page_text(url: str) -> str | None:
    try:
        import requests
        from bs4 import BeautifulSoup
    except Exception:
        return None

    response = requests.get(
        url,
        headers=_browser_headers(),
        timeout=_REQUEST_TIMEOUT_SECONDS,
        allow_redirects=True,
    )
    if response.status_code != 200:
        return None
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type:
        return None
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = _clean_text(soup.get_text(" ", strip=True))
    if not text or "TalkingPoints for Families" in text:
        return None
    if _looks_like_error_message(text):
        return None
    return text


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = re.sub(r"\s+", " ", value).strip()
    return text or None


def _looks_like_error_message(text: str) -> bool:
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


def _browser_headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "Chrome/125 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }


def _api_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Content-type": "application/json",
        "X-Mobile-Platform": "web",
        "X-Language": "en",
        "X-App-Version": "3",
        "Origin": "https://families.talkingpts.org",
        "Referer": "https://families.talkingpts.org/",
    }


def _cache_path() -> Path:
    data_home = Path(
        os.environ.get(
            "VESSENCE_DATA_HOME",
            str(Path.home() / "ambient" / "vessence-data"),
        )
    ).expanduser()
    return data_home / "cache" / "talkingpoints_readback_cache.json"


def _load_cache() -> dict[str, Any]:
    path = _cache_path()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache: Mapping[str, Any]) -> None:
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as e:
        logger.debug("Failed to save TalkingPoints cache: %s", e)


def _read_cache_entry(url: str) -> str | object | None:
    cache = _load_cache()
    entry = cache.get(url)
    if not isinstance(entry, dict):
        return _CACHE_MISS
    checked_at = float(entry.get("checked_at") or 0)
    resolved = entry.get("resolved")
    ttl = _CACHE_TTL_SECONDS if resolved else _FAILED_CACHE_TTL_SECONDS
    if time.time() - checked_at > ttl:
        return _CACHE_MISS
    return resolved or None


def _write_cache_entry(url: str, resolved: str | None) -> None:
    cache = _load_cache()
    cache[url] = {"checked_at": time.time(), "resolved": resolved or ""}
    _save_cache(cache)
