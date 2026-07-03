"""Contact search result helpers."""

from __future__ import annotations

from typing import Iterable


def aggregate_contact_rows(rows: Iterable) -> list[dict]:
    """Merge contact rows by contact_id, falling back to display_name."""
    people: dict[str, dict] = {}
    for row in rows:
        key = row["contact_id"] or row["display_name"]
        if key not in people:
            people[key] = {"display_name": row["display_name"], "phones": [], "emails": []}
        if row["phone_number"] and row["phone_number"] not in people[key]["phones"]:
            people[key]["phones"].append(row["phone_number"])
        if row["email"] and row["email"] not in people[key]["emails"]:
            people[key]["emails"].append(row["email"])
    return list(people.values())
