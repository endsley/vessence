"""Prepare synced SMS rows for Jane readback."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Iterable, Mapping

from jane_web.message_readback_helpers import (
    MAX_READBACK_CHARS as _MAX_READBACK_CHARS,
    MUSIC_PLAY_MARKER_RE as _MUSIC_PLAY_MARKER_RE,
    TALKINGPOINTS_URL_RE as _TALKINGPOINTS_URL_RE,
    WRAPPER_BODY_RE as _WRAPPER_BODY_RE,
    clean_text as _clean_text,
    cache_entry_readback_value as _cache_entry_readback_value,
    decode_urlsafe_base64 as _decode_urlsafe_base64,
    extract_talkingpoints_message as _extract_talkingpoints_message,
    find_talkingpoints_url as _find_talkingpoints_url,
    looks_like_error_message as _looks_like_error_message,
    looks_like_wrapper as _looks_like_wrapper,
    readback_cache_entry_is_fresh as _readback_cache_entry_is_fresh,
    readback_cache_ttl_seconds as _readback_cache_ttl_seconds,
    sanitize_untrusted_text as _sanitize_untrusted_text,
    talkingpoints_code_candidates_from_urls as _talkingpoints_code_candidates_from_urls,
    truncate_readback as _truncate_readback,
)

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
_FAILED_CACHE_TTL_SECONDS = 60 * 60
_REQUEST_TIMEOUT_SECONDS = 6
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


def _talkingpoints_code_candidates(url: str) -> list[str]:
    urls = [url]
    try:
        import requests

        response = requests.get(
            url,
            headers=_browser_headers(),
            timeout=_REQUEST_TIMEOUT_SECONDS,
            allow_redirects=True,
        )
        urls.append(response.url)
    except Exception:
        pass

    return _talkingpoints_code_candidates_from_urls(urls)


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
    return _cache_entry_readback_value(
        cache.get(url),
        now=time.time(),
        success_ttl_seconds=_CACHE_TTL_SECONDS,
        failed_ttl_seconds=_FAILED_CACHE_TTL_SECONDS,
        cache_miss=_CACHE_MISS,
    )


def _write_cache_entry(url: str, resolved: str | None) -> None:
    cache = _load_cache()
    cache[url] = {"checked_at": time.time(), "resolved": resolved or ""}
    _save_cache(cache)
