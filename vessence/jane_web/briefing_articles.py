"""Pure response helpers for briefing article list routes."""
from __future__ import annotations

from typing import Any


def _normalize_briefing_card(card: dict[str, Any]) -> None:
    if not card.get("categories"):
        card["categories"] = card.get("tags", []) or ([card["topic"]] if card.get("topic") else [])
    if card.get("image_path") and not card.get("image_url"):
        card["image_url"] = f"/api/briefing/image/{card['id']}"


def _filter_briefing_cards(
    cards: list[dict[str, Any]],
    *,
    topic: str | None,
    view: str | None,
) -> list[dict[str, Any]]:
    if view == "saved":
        return [card for card in cards if card.get("state") == "saved"]
    if topic:
        return [card for card in cards if card.get("topic", "").lower() == topic.lower()]
    return cards


def _briefing_categories(cards: list[dict[str, Any]]) -> list[str]:
    categories: set[str] = set()
    for card in cards:
        categories.update(card.get("categories", []))
    return sorted(categories)


def _briefing_page(
    cards: list[dict[str, Any]],
    *,
    limit: int | str | None,
    offset: int | str,
) -> tuple[list[dict[str, Any]], int, int, bool]:
    total = len(cards)
    if limit is None:
        return cards, 0, total, False
    try:
        limit_i = max(0, int(limit))
        offset_i = max(0, int(offset))
    except (TypeError, ValueError) as exc:
        raise ValueError("limit/offset must be integers") from exc
    page = cards[offset_i:offset_i + limit_i]
    has_more = offset_i + limit_i < total
    return page, offset_i, limit_i, has_more


def build_briefing_articles_response(
    cards: list[dict[str, Any]],
    *,
    topic: str | None = None,
    view: str | None = None,
    limit: int | str | None = None,
    offset: int | str = 0,
) -> dict[str, Any]:
    """Normalize, filter, paginate, and shape briefing article cards."""
    for card in cards:
        _normalize_briefing_card(card)

    cards = _filter_briefing_cards(cards, topic=topic, view=view)
    categories = _briefing_categories(cards)
    total = len(cards)
    page, offset_i, limit_i, has_more = _briefing_page(cards, limit=limit, offset=offset)

    for card in page:
        card.pop("full_summary", None)

    return {
        "status": "ok",
        "cards": page,
        "card_count": len(page),
        "total": total,
        "offset": offset_i,
        "limit": limit_i,
        "has_more": has_more,
        "categories": categories,
    }
