"""Response builders for the timer Stage 2 handler."""
from __future__ import annotations

from agent_skills.private_handler_utils import pending_continuation

from .parsing import pretty_duration
from .tool_markers import (
    timer_cancel_marker as _timer_cancel_marker,
    timer_delete_marker as _timer_delete_marker,
    timer_list_marker as _timer_list_marker,
    timer_set_marker as _timer_set_marker,
)


INTENT = "timer"


def build_timer_pending(awaiting: str, data: dict, question: str) -> dict:
    return pending_continuation(
        handler_class=INTENT,
        awaiting=awaiting,
        question=question,
        data=data,
    )


def build_ask_duration_response(data: dict) -> dict:
    ask = "Sure — how long should the timer run?"
    return {
        "text": ask,
        "structured": {
            "intent": INTENT,
            "entities": {"action": "set", "stage": "await_duration"},
            "pending_action": build_timer_pending("duration", data, question=ask),
        },
    }


def build_duration_retry_response(data: dict) -> dict:
    ask = "I didn't catch that. How long should the timer run? Like '5 minutes'."
    return {
        "text": ask,
        "structured": {
            "intent": INTENT,
            "pending_action": build_timer_pending("duration", data, question=ask),
        },
    }


def build_ask_label_response(data: dict) -> dict:
    pretty = pretty_duration(data.get("duration_ms", 0))
    ask = f"Got it, {pretty}. What should I call this timer? Or say 'no label'."
    return {
        "text": ask,
        "structured": {
            "intent": INTENT,
            "entities": {
                "action": "set",
                "stage": "await_label",
                "duration_ms": data.get("duration_ms"),
            },
            "pending_action": build_timer_pending("label", data, question=ask),
        },
    }


def build_set_marker(duration_ms: int, label: str) -> str:
    return _timer_set_marker(duration_ms, label)


def spoken_set_confirmation(duration_ms: int, label: str) -> str:
    pretty = pretty_duration(duration_ms)
    if label:
        ll = label.lower()
        already_terminal = any(ll.endswith(w) for w in ("ready", "done", "up", "finished", "out"))
        if already_terminal:
            return f"Timer set — I'll tell you in {pretty} when {label}."
        return f"Timer set — I'll let you know when the {label} is ready in {pretty}."
    return f"Timer set for {pretty}."


def build_set_response(duration_ms: int, label: str, *, from_followup: bool = False) -> dict:
    structured: dict = {
        "intent": INTENT,
        "entities": {
            "action": "set",
            "duration_ms": duration_ms,
            "label": label or "",
        },
    }
    if from_followup:
        structured["pending_action"] = {
            "type": "STAGE2_FOLLOWUP",
            "handler_class": INTENT,
            "status": "resolved",
        }
    return {
        "text": f"{spoken_set_confirmation(duration_ms, label)} {build_set_marker(duration_ms, label)}",
        "conversation_end": True,
        "structured": structured,
    }


def build_count_response() -> dict:
    return {
        "text": f"Let me check. {_timer_list_marker()}",
        "structured": {"intent": INTENT, "entities": {"action": "count"}},
    }


def build_list_response() -> dict:
    return {
        "text": f"Checking your timers. {_timer_list_marker()}",
        "structured": {"intent": INTENT, "entities": {"action": "list"}},
    }


def build_cancel_response() -> dict:
    return {
        "text": f"Cancelling your timer. {_timer_cancel_marker()}",
        "structured": {"intent": INTENT, "entities": {"action": "cancel"}},
    }


def delete_target_description(target: dict) -> str:
    if "id" in target:
        return f"timer #{target['id']}"
    if "label" in target:
        return f"the {target['label']} timer"
    return f"the #{target['index']} timer"


def build_delete_response(target: dict) -> dict:
    marker = _timer_delete_marker(target)
    return {
        "text": f"Deleting {delete_target_description(target)}. {marker}",
        "structured": {"intent": INTENT, "entities": {"action": "delete", **target}},
    }
