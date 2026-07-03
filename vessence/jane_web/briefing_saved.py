"""Pure helpers for saved briefing article routes."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


def saved_articles_index_path(saved_articles_dir: Path) -> Path:
    return saved_articles_dir / "saved.json"


def daily_briefing_article_path(tools_dir: str | Path, article_id: str) -> Path:
    return Path(tools_dir) / "daily_briefing" / "essence_data" / "articles" / f"{article_id}.json"


def saved_article_record(
    article_id: str,
    category: str,
    saved_at: str,
    article_data: Any,
) -> dict[str, Any]:
    return {
        "article_id": article_id,
        "category": category,
        "saved_at": saved_at,
        "article": article_data,
    }


def vault_saved_article_path(vault_saved_root: Path, category: str, article_id: str) -> Path:
    return vault_saved_root / category / f"{article_id}.json"


def saved_category_names(
    vault_categories: Iterable[str],
    saved_records: Mapping[str, Mapping[str, Any]],
) -> list[Any]:
    categories: set[Any] = set(vault_categories)
    categories.update(record.get("category", "Uncategorized") for record in saved_records.values())
    return sorted(categories)


def saved_article_list(
    saved_records: Mapping[str, dict[str, Any]],
    category: str | None = None,
) -> list[dict[str, Any]]:
    items = list(saved_records.values())
    if category:
        items = [item for item in items if item.get("category") == category]
    items.sort(key=lambda item: item.get("saved_at", ""), reverse=True)
    return items
