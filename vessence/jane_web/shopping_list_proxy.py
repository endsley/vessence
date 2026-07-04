"""Helpers for legacy proxy shopping-list actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ShoppingActionKind = Literal["add", "remove", "clear"]


@dataclass(frozen=True)
class ShoppingListProxyAction:
    kind: ShoppingActionKind
    item: str
    store: str


_ADD_STORE_MARKERS = (
    (" to the costco", "costco"),
    (" to costco", "costco"),
    (" to the walmart", "walmart"),
    (" to walmart", "walmart"),
    (" to the grocery", "grocery"),
    (" to grocery", "grocery"),
    (" to the target", "target"),
    (" to target", "target"),
)
_REMOVE_STORE_MARKERS = (
    (" from the costco", "costco"),
    (" from costco", "costco"),
    (" from walmart", "walmart"),
    (" from grocery", "grocery"),
)


def _extract_item_and_store(text: str, markers: tuple[tuple[str, str], ...]) -> tuple[str, str]:
    text_lower = text.lower()
    for marker, store in markers:
        if marker in text_lower:
            return text[:text_lower.index(marker)].strip(), store
    return text.strip(), "default"


def parse_shopping_list_proxy_action(action: str | None) -> ShoppingListProxyAction | None:
    action = (action or "").lower().strip()
    if action.startswith("add "):
        item, store = _extract_item_and_store(action[4:].strip(), _ADD_STORE_MARKERS)
        return ShoppingListProxyAction(kind="add", item=item, store=store)
    if action.startswith("remove "):
        item, store = _extract_item_and_store(action[7:].strip(), _REMOVE_STORE_MARKERS)
        return ShoppingListProxyAction(kind="remove", item=item, store=store)
    if action.startswith("clear"):
        store = action.replace("clear", "").strip() or "default"
        return ShoppingListProxyAction(kind="clear", item="", store=store)
    return None


def shopping_list_v2_task_context(
    action: ShoppingListProxyAction,
    updated_items: list[str] | None = None,
) -> str:
    if action.kind == "add":
        return (
            f"Added {action.item!r} to the {action.store} list. "
            f"Current list: {', '.join(updated_items or []) or '(empty)'}"
        )
    if action.kind == "remove":
        return (
            f"Removed {action.item!r} from the {action.store} list. "
            f"Current list: {', '.join(updated_items or []) or '(empty)'}"
        )
    return f"Cleared the {action.store} shopping list."


def shopping_list_legacy_response(
    action: ShoppingListProxyAction,
    updated_items: list[str] | None = None,
) -> str:
    if action.kind == "add":
        return (
            f"Added **{action.item}** to the {action.store} list. "
            f"Current list: {', '.join(updated_items or []) or '(empty)'}"
        )
    if action.kind == "remove":
        return (
            f"Removed **{action.item}** from the {action.store} list. "
            f"Current list: {', '.join(updated_items or []) or '(empty)'}"
        )
    return f"Cleared the {action.store} shopping list."
