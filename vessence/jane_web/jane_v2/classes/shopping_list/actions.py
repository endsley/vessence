"""Pure action helpers for the shopping-list handler."""
from __future__ import annotations

import math
from typing import Optional


VALID_ACTIONS = {"view", "add", "remove", "clear", "check"}
DESTRUCTIVE_CONFIDENCE_THRESHOLD = 0.80
DESTRUCTIVE_ACTIONS = {"remove", "clear"}


def split_items(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    if not isinstance(raw, str):
        return []
    return [piece.strip() for piece in str(raw).split(",") if piece.strip()]


def destructive_confidence_ok(confidence: object) -> bool:
    return (
        not isinstance(confidence, bool)
        and isinstance(confidence, (int, float))
        and math.isfinite(confidence)
        and confidence >= DESTRUCTIVE_CONFIDENCE_THRESHOLD
    )


def parse_action_params(params: dict | None) -> tuple[str, dict | None]:
    """Validate classifier params before any shopping-list mutation occurs."""
    if not params:
        return "missing_params", None

    raw_action = params.get("action")
    if not isinstance(raw_action, str):
        return "malformed_action", {"raw_action": raw_action}

    action = raw_action.strip().lower()
    if action not in VALID_ACTIONS:
        return "unknown_action", {"action": action}

    items = split_items(params.get("items"))
    confidence = None
    if action in DESTRUCTIVE_ACTIONS:
        confidence = params.get("confidence")
        if not destructive_confidence_ok(confidence):
            return "low_confidence", {"action": action, "confidence": confidence}

    return "ok", {"action": action, "items": items, "confidence": confidence}


def split_present_missing(items: list[str], current: list[str]) -> tuple[list[str], list[str]]:
    current_lower = [item.lower() for item in current]
    present = [item for item in items if item.lower() in current_lower]
    missing = [item for item in items if item.lower() not in current_lower]
    return present, missing


def format_check_response(present: list[str], missing: list[str]) -> str:
    if present and not missing:
        return f"Yes — {', '.join(present)} is on your shopping list."
    if missing and not present:
        return f"No — {', '.join(missing)} is not on your shopping list."
    return (
        f"Mixed: {', '.join(present)} is on the list; "
        f"{', '.join(missing)} is not."
    )
