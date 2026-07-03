"""Pure SMS recipient and draft policy helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


STOP_PREFIXES = ("my ", "the ", "to ", "for ")


@dataclass(frozen=True)
class ContactLookupResult:
    match: dict[str, str] | None
    ambiguous_count: int = 0


def normalize_name(name: str) -> str:
    n = (name or "").strip().lower()
    for prefix in STOP_PREFIXES:
        if n.startswith(prefix):
            n = n[len(prefix):].strip()
            break
    return re.sub(r"\s+", " ", n)


def escape_sql_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def alias_match_from_row(row: Any, normalized_alias: str) -> dict[str, str] | None:
    if row and row["phone_number"]:
        return {
            "phone_number": row["phone_number"],
            "display_name": row["display_name"] or normalized_alias,
            "source": "alias",
        }
    return None


def contact_lookup_from_rows(rows: list[Any]) -> ContactLookupResult:
    seen: dict[str, str] = {}
    for row in rows:
        display_name = row["display_name"]
        if display_name not in seen:
            seen[display_name] = row["phone_number"]
    if len(seen) == 1:
        display_name, phone = next(iter(seen.items()))
        return ContactLookupResult(
            {
                "phone_number": phone,
                "display_name": display_name,
                "source": "contacts",
            }
        )
    if len(seen) > 1:
        return ContactLookupResult(None, len(seen))
    return ContactLookupResult(None, 0)


def draft_is_expired(
    created_epoch: int,
    *,
    now: float,
    ttl_seconds: int,
) -> bool:
    return now - created_epoch > ttl_seconds


def draft_payload_from_row(row: Any) -> dict[str, str | None]:
    return {
        "draft_id": row["draft_id"],
        "phone_number": row["phone_number"],
        "display_name": row["display_name"],
        "body": row["body"],
    }


def expired_draft_cutoff_text(now: float, ttl_seconds: int) -> str:
    return str(int(now - ttl_seconds))
