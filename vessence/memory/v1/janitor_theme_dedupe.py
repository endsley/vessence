"""Cross-session short-term theme dedupe helpers."""

from __future__ import annotations

from typing import Any


def short_term_theme_entries(items: dict[str, list[Any]]) -> list[dict[str, Any]]:
    themes: list[dict[str, Any]] = []
    for index, meta in enumerate(items.get("metadatas", [])):
        if (meta or {}).get("memory_type") == "short_term_theme":
            themes.append(
                {
                    "id": items["ids"][index],
                    "document": items["documents"][index],
                    "session_id": meta.get("session_id", ""),
                    "last_updated_at": meta.get("last_updated_at", ""),
                }
            )
    return themes


def cross_session_theme_deletion_id(
    theme: dict[str, Any],
    *,
    neighbor_id: str,
    neighbor_meta: dict[str, Any] | None,
    distance: float,
    similarity_threshold: float,
) -> str | None:
    neighbor_meta = neighbor_meta or {}
    if neighbor_id == theme["id"]:
        return None
    if neighbor_meta.get("session_id", "") == theme.get("session_id", ""):
        return None
    if distance > similarity_threshold:
        return None
    neighbor_updated = neighbor_meta.get("last_updated_at", "")
    if theme.get("last_updated_at", "") >= neighbor_updated:
        return neighbor_id
    return theme["id"]
