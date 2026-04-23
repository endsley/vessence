"""Saved-search bundle definitions.

A saved search is a named bundle of marketplace query strings sharing
filter parameters. Example::

    {
      "cars": {
        "label": "Cars",
        "queries": ["Toyota corolla", "Honda civic", "Honda fit"],
        "filters": {
          "max_price": 15000,
          "max_miles": 60000,
          "require_clean_title": true,
          "suspicion_filter": true
        },
        "location_id": "109352265750998",
        "created": "2026-04-22"
      }
    }

All saved searches live in one JSON file so add/list/delete are cheap.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any

_DATA = Path(os.environ.get(
    "VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data")))
CONFIG_PATH = _DATA / "config" / "marketplace_searches.json"
DATA_ROOT = _DATA / "data" / "facebook_marketplace_finds"

# Medford, MA. Discover other ids by opening marketplace and reading the URL.
DEFAULT_LOCATION_ID = "109352265750998"

_SAFE_NAME = re.compile(r"^[a-z0-9_-]{1,40}$")


def _load() -> dict[str, dict[str, Any]]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"marketplace_searches.json is corrupted ({e}). "
            f"Refusing to proceed — fix or restore before continuing.")


def _save(data: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_PATH)


def list_searches() -> list[dict[str, Any]]:
    out = []
    for name, body in _load().items():
        out.append({"name": name, **body})
    out.sort(key=lambda s: s.get("label", s["name"]).lower())
    return out


def get_search(name: str) -> dict[str, Any] | None:
    return _load().get(name)


def save_search(
    name: str,
    *,
    label: str,
    queries: list[str],
    filters: dict[str, Any] | None = None,
    location_id: str = DEFAULT_LOCATION_ID,
) -> dict[str, Any]:
    if not _SAFE_NAME.match(name):
        raise ValueError(f"search name must match {_SAFE_NAME.pattern!r}")
    if not isinstance(queries, list) or not queries:
        raise ValueError("queries must be a non-empty list of strings")
    data = _load()
    existing = data.get(name, {})
    body = {
        "label": label or name,
        "queries": queries,
        "filters": filters or {
            "max_price": 15000,
            "max_miles": 60000,
            "require_clean_title": True,
            "suspicion_filter": True,
        },
        "location_id": location_id,
        "created": existing.get("created", dt.date.today().isoformat()),
        "updated": dt.date.today().isoformat(),
    }
    data[name] = body
    _save(data)
    return body


def delete_search(name: str) -> bool:
    data = _load()
    if name in data:
        data.pop(name)
        _save(data)
        return True
    return False


def search_data_dir(name: str) -> Path:
    if not _SAFE_NAME.match(name):
        raise ValueError(f"unsafe search name: {name!r}")
    d = DATA_ROOT / name
    d.mkdir(parents=True, exist_ok=True)
    return d
