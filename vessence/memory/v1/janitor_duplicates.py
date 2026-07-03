"""Exact-duplicate selection helpers for memory janitor cleanup."""

from __future__ import annotations

import datetime

from memory.v1.janitor_rules import meta_label


DUPLICATE_TIMESTAMP_KEYS = (
    "updated_at",
    "last_updated_at",
    "timestamp",
    "created_at",
    "archived_at",
    "code_verified_at",
)


def parse_stored_utc(value: str | None) -> datetime.datetime | None:
    """Parse legacy naive UTC strings and modern ISO timestamps."""
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(datetime.UTC).replace(tzinfo=None)
    return parsed


def normalise_duplicate_doc(doc: str) -> str:
    return " ".join((doc or "").split()).casefold()


def duplicate_row_timestamp(row: dict) -> datetime.datetime:
    metadata = row.get("meta") or {}
    for key in DUPLICATE_TIMESTAMP_KEYS:
        parsed = parse_stored_utc(metadata.get(key))
        if parsed is not None:
            return parsed
    return datetime.datetime.min


def duplicate_deletion_groups(rows: list[dict], *, min_doc_chars: int = 20) -> list[list[dict]]:
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for row in rows:
        norm_doc = normalise_duplicate_doc(row.get("doc", ""))
        if len(norm_doc) < min_doc_chars:
            continue
        metadata = row.get("meta") or {}
        key = (
            meta_label(metadata, "topic"),
            meta_label(metadata, "subtopic"),
            norm_doc,
        )
        groups.setdefault(key, []).append(row)

    stale_groups: list[list[dict]] = []
    for duplicate_rows in groups.values():
        if len(duplicate_rows) < 2:
            continue
        keep = max(duplicate_rows, key=lambda row: (duplicate_row_timestamp(row), row["id"]))
        stale_rows = [row for row in duplicate_rows if row["id"] != keep["id"]]
        if stale_rows:
            stale_groups.append(stale_rows)
    return stale_groups
