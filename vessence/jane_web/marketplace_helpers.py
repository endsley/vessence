"""Pure helpers for Facebook Marketplace web routes."""
from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any


_SAFE_SEARCH_NAME_RE = re.compile(r"^[a-z0-9_-]{1,40}$")
_SAFE_LISTING_SLUG_RE = re.compile(r"^[a-z0-9_-]{1,60}$")
_SAFE_LISTING_ID_RE = re.compile(r"^[0-9]{4,25}$")
_SAFE_PHOTO_NAME_RE = re.compile(r"^photo_\d{2,3}\.(jpg|jpeg|png|webp)$")


def is_safe_marketplace_name(name: str) -> bool:
    return bool(_SAFE_SEARCH_NAME_RE.match(name))


def is_safe_listing_key(slug: str, listing_id: str) -> bool:
    return bool(_SAFE_LISTING_SLUG_RE.match(slug) and _SAFE_LISTING_ID_RE.match(listing_id))


def is_safe_photo_name(photo_name: str) -> bool:
    return bool(_SAFE_PHOTO_NAME_RE.match(photo_name))


def marketplace_create_search_payload(
    body: Mapping[str, Any],
    default_location_id: Any,
) -> dict[str, Any]:
    queries = body.get("queries") or []
    name = (body.get("name") or "").strip()
    return {
        "name": name,
        "label": body.get("label") or name,
        "queries": [str(query).strip() for query in queries if str(query).strip()]
        if isinstance(queries, list)
        else [],
        "raw_queries_valid": isinstance(queries, list) and bool(queries),
        "filters": body.get("filters"),
        "location_id": body.get("location_id") or default_location_id,
    }


def marketplace_refresh_command(python_bin: str, name: str) -> list[str]:
    return [python_bin, "-m", "agent_skills.marketplace.refresh", name]


def marketplace_refresh_env(environ: Mapping[str, str]) -> dict[str, str]:
    env = dict(environ)
    env.pop("DISPLAY", None)
    env.pop("WAYLAND_DISPLAY", None)
    return env


def marketplace_refresh_log_path(data_home: str | Path, name: str) -> Path:
    return Path(data_home) / "logs" / f"marketplace_refresh_{name}.log"


def marketplace_refresh_log_header(name: str, now: datetime) -> str:
    return f"\n=== manual refresh {name} at {now.isoformat(timespec='seconds')} ===\n"
