"""Dynamic query marker payload helpers for the memory janitor."""

from __future__ import annotations

from typing import Iterable


PERSONAL_TOPIC_ALLOWLIST = frozenset({
    "identity",
    "identity evolution",
    "family",
    "personal",
    "preferences",
    "location",
    "office_location",
    "office_setup",
    "social",
    "neighbors",
    "interests",
    "music",
    "research",
    "activities",
    "feedback",
    "communication",
    "communication_style",
    "user",
})


def marker_labels_from_metadatas(metadatas: Iterable[dict | None]) -> set[str]:
    labels: set[str] = set()
    for meta in metadatas:
        for key in ("topic", "subtopic"):
            value = ((meta or {}).get(key) or "").strip()
            if value and value.lower() not in ("general", "unknown", ""):
                labels.add(value.lower())
    return labels


def dynamic_query_marker_payload(
    *,
    user_labels: Iterable[str],
    long_term_labels: Iterable[str],
    short_term_labels: Iterable[str],
    file_labels: Iterable[str],
    updated_at: str,
) -> dict[str, list[str] | str]:
    all_user_labels = set(user_labels)
    personal = all_user_labels & PERSONAL_TOPIC_ALLOWLIST
    project = all_user_labels - personal
    project |= set(long_term_labels)
    project |= set(short_term_labels)
    return {
        "personal_markers": sorted(personal),
        "project_markers": sorted(project),
        "file_markers": sorted(set(file_labels)),
        "updated_at": updated_at,
    }
