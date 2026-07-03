"""Shopping List Stage 2 handler — params-driven.

Stage 1 (qwen extraction) supplies `action` and `items` per the
PARAMS_SCHEMA in metadata.py. This handler dispatches directly on
`params["action"]` against the JSON store — no local LLM intent parse
needed. Escalates to Stage 3 only when params are missing or the
intent doesn't fit the simple add/remove/view/clear/check verbs.
"""

from __future__ import annotations

import logging
from .actions import (
    VALID_ACTIONS as _VALID_ACTIONS,
    destructive_confidence_ok as _destructive_confidence_ok,
    parse_action_params as _parse_action_params,
    split_items as _split_items,
    split_present_missing as _split_present_missing,
)
from .responses import (
    build_add_response as _build_add_response,
    build_check_response as _build_check_response,
    build_clear_response as _build_clear_response,
    build_remove_response as _build_remove_response,
    build_view_response as _build_view_response,
)

logger = logging.getLogger(__name__)


async def handle(prompt: str, params: dict | None = None) -> dict | None:
    """Dispatch a shopping-list action from the classifier-extracted params."""
    status, parsed = _parse_action_params(params)
    if status == "missing_params":
        logger.info("shopping_list handler: no params — escalating")
        return None
    if status == "malformed_action":
        logger.info(
            "shopping_list handler: malformed action %r — escalating",
            (parsed or {}).get("raw_action"),
        )
        return None
    if status == "unknown_action":
        logger.info("shopping_list handler: unknown action %r — escalating", (parsed or {}).get("action"))
        return None
    if status == "low_confidence":
        logger.info(
            "shopping_list handler: destructive action %r confidence %r "
            "below threshold — escalating",
            (parsed or {}).get("action"),
            (parsed or {}).get("confidence"),
        )
        return None

    parsed = parsed or {}
    action = parsed["action"]
    items = parsed["items"]
    confidence = parsed["confidence"]

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
        return _build_view_response(current)

    if action == "add":
        if not items:
            return None
        for item in items:
            add_item(item, list_name)
        current = get_list(list_name)
        return _build_add_response(items, current)

    if action == "remove":
        if not items:
            return None
        for item in items:
            remove_item(item, list_name, confidence=confidence)
        return _build_remove_response(items)

    if action == "clear":
        clear_list(list_name, confidence=confidence)
        return _build_clear_response()

    if action == "check":
        if not items:
            return None
        present, missing = _split_present_missing(items, get_list(list_name))
        return _build_check_response(present, missing)

    return None
