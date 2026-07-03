"""Response builders for the shopping-list Stage 2 handler."""

from __future__ import annotations

from .actions import format_check_response


def build_view_response(current: list[str]) -> dict:
    if not current:
        return {"text": "Your shopping list is empty."}
    return {"text": f"Your shopping list has: {', '.join(current)}."}


def build_add_response(items: list[str], current: list[str]) -> dict:
    return {"text": f"Added {', '.join(items)}. Your shopping list now has {len(current)} items."}


def build_remove_response(items: list[str]) -> dict:
    return {"text": f"Removed {', '.join(items)} from your shopping list."}


def build_clear_response() -> dict:
    return {"text": "Your shopping list has been cleared."}


def build_check_response(present: list[str], missing: list[str]) -> dict:
    return {"text": format_check_response(present, missing)}
