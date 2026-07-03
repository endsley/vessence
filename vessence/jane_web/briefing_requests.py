"""Request payload helpers for briefing submission and summarization routes."""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


_HTTP_URL_RE = re.compile(r"^https?://")


def is_http_url(url: str) -> bool:
    return bool(_HTTP_URL_RE.match(url))


def briefing_submit_values(body: Mapping[str, Any]) -> tuple[str, str, str, str]:
    url = body.get("url", "").strip()
    title = (body.get("title") or "").strip()
    text = (body.get("text") or "").strip()
    save_category = (body.get("save_category") or body.get("category") or "").strip()
    return (url, title, text, save_category)


def briefing_url_value(body: Mapping[str, Any]) -> str:
    return body.get("url", "").strip()


def briefing_text_summary_values(body: Mapping[str, Any]) -> tuple[str, str]:
    title = (body.get("title") or "").strip()
    text = (body.get("text") or "").strip()
    return (title, text)
