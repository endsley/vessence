"""Cache-Control header selection for Jane web responses."""

from __future__ import annotations


def cache_control_header(path: str) -> str:
    if path.startswith("/static/"):
        return "public, max-age=86400"
    if path.startswith("/api/briefing/image/"):
        return "public, max-age=3600"
    if path.startswith("/api/"):
        return "no-store"
    return "no-cache"
