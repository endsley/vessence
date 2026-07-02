"""Shopping List Stage 2 handler — params-driven.

Stage 1 (qwen extraction) supplies `action` and `items` per the
PARAMS_SCHEMA in metadata.py. This handler dispatches directly on
`params["action"]` against the JSON store — no local LLM intent parse
needed. Escalates to Stage 3 only when params are missing or the
intent doesn't fit the simple add/remove/view/clear/check verbs.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)

_VALID_ACTIONS = {"view", "add", "remove", "clear", "check"}


def _split_items(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    if not isinstance(raw, str):
        return []
    return [piece.strip() for piece in str(raw).split(",") if piece.strip()]


async def handle(prompt: str, params: dict | None = None) -> dict | None:
    """Dispatch a shopping-list action from the classifier-extracted params."""
    if not params:
        logger.info("shopping_list handler: no params — escalating")
        return None

    raw_action = params.get("action")
    if not isinstance(raw_action, str):
        logger.info("shopping_list handler: malformed action %r — escalating", raw_action)
        return None

    action = raw_action.strip().lower()
    if action not in _VALID_ACTIONS:
        logger.info("shopping_list handler: unknown action %r — escalating", action)
        return None

    items = _split_items(params.get("items"))
    confidence = None
    if action in {"remove", "clear"}:
        confidence = params.get("confidence")
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not math.isfinite(confidence)
            or confidence < 0.80
        ):
            logger.info(
                "shopping_list handler: destructive action %r confidence %r "
                "below threshold — escalating",
                action,
                confidence,
            )
            return None

    try:
        from agent_skills.shopping_list import (
            add_item, remove_item, get_list, clear_list,
        )
    except Exception as e:
        logger.warning("shopping_list handler: import failed: %s", e)
        return None

    list_name = "default"

    if action == "view":
        current = get_list(list_name)
        if not current:
            return {"text": "Your shopping list is empty."}
        return {"text": f"Your shopping list has: {', '.join(current)}."}

    if action == "add":
        if not items:
            return None
        for item in items:
            add_item(item, list_name)
        current = get_list(list_name)
        return {
            "text": f"Added {', '.join(items)}. Your shopping list now has {len(current)} items."
        }

    if action == "remove":
        if not items:
            return None
        for item in items:
            remove_item(item, list_name, confidence=confidence)
        return {"text": f"Removed {', '.join(items)} from your shopping list."}

    if action == "clear":
        clear_list(list_name, confidence=confidence)
        return {"text": "Your shopping list has been cleared."}

    if action == "check":
        if not items:
            return None
        current_lower = [i.lower() for i in get_list(list_name)]
        present = [i for i in items if i.lower() in current_lower]
        missing = [i for i in items if i.lower() not in current_lower]
        if present and not missing:
            return {"text": f"Yes — {', '.join(present)} is on your shopping list."}
        if missing and not present:
            return {"text": f"No — {', '.join(missing)} is not on your shopping list."}
        return {
            "text": (
                f"Mixed: {', '.join(present)} is on the list; "
                f"{', '.join(missing)} is not."
            )
        }

    return None
