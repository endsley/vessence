"""Pure data helpers for shopping list storage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CONFIDENCE_THRESHOLD = 0.80


@dataclass(frozen=True)
class ListMutation:
    items: list[str]
    should_save: bool


def coerce_lists_data(data: Any) -> dict[str, list[str]]:
    if not isinstance(data, dict):
        return {}
    if not all(
        isinstance(name, str)
        and isinstance(items, list)
        and all(isinstance(item, str) for item in items)
        for name, items in data.items()
    ):
        return {}
    return data


def list_key(list_name: str) -> str:
    key = list_name.lower()
    if not key.strip():
        raise ValueError("list_name is required")
    return key


def require_confidence(
    confidence: float,
    threshold: float = CONFIDENCE_THRESHOLD,
) -> None:
    if (
        confidence is None
        or isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
    ):
        raise TypeError("confidence must be numeric")
    if not confidence >= threshold:
        raise PermissionError("confidence is below the required threshold")


def add_item_to_lists(
    data: dict[str, list[str]],
    item: str,
    list_name: str = "default",
) -> ListMutation:
    key = list_key(list_name)
    if key not in data:
        data[key] = []
    item = item.strip()
    if item and item.lower() not in [i.lower() for i in data[key]]:
        data[key].append(item)
    return ListMutation(data[key], True)


def remove_item_from_lists(
    data: dict[str, list[str]],
    item: str,
    list_name: str = "default",
) -> ListMutation:
    key = list_key(list_name)
    item = item.strip()
    if not item:
        raise ValueError("item is required")
    if key in data:
        data[key] = [i for i in data[key] if i.lower() != item.lower()]
        return ListMutation(data[key], True)
    return ListMutation(data.get(key, []), False)


def clear_list_in_lists(
    data: dict[str, list[str]],
    list_name: str = "default",
) -> ListMutation:
    key = list_key(list_name)
    data[key] = []
    return ListMutation(data[key], True)


def format_lists_for_context(data: dict[str, list[str]]) -> str:
    if not data:
        return "No shopping lists exist yet. The user can ask you to create one."
    parts = []
    for name, items in data.items():
        if items:
            item_list = "\n".join(f"  - {i}" for i in items)
            parts.append(f"**{name.title()} list:**\n{item_list}")
        else:
            parts.append(f"**{name.title()} list:** (empty)")
    return "\n\n".join(parts)
