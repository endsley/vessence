"""Pure decision helpers for check_continuation.py."""

from __future__ import annotations

from typing import Any


CONTINUE_PROMPT_TEXT = "[new]\nrun job queue:"


def queue_payload_is_empty(payload: dict[str, Any]) -> bool:
    return len(payload.get("items", [])) == 0


def idle_state_is_idle(
    state: dict[str, Any],
    *,
    now: float,
    threshold_seconds: int,
) -> bool:
    last_ts = state.get("last_active_ts", 0)
    elapsed = now - last_ts if last_ts else 999999
    return elapsed >= threshold_seconds


def active_queue_not_empty_result() -> dict[str, Any]:
    return {
        "should_continue": False,
        "prompt_index": None,
        "prompt_text": None,
        "reason": "Active queue not empty",
    }


def no_pending_jobs_result() -> dict[str, Any]:
    return {
        "should_continue": False,
        "prompt_index": None,
        "prompt_text": None,
        "reason": "No pending jobs",
    }


def user_active_result() -> dict[str, Any]:
    return {
        "should_continue": False,
        "prompt_index": None,
        "prompt_text": None,
        "reason": "user is active",
    }


def continue_job_result(job_num: int) -> dict[str, Any]:
    return {
        "should_continue": True,
        "prompt_index": job_num,
        "prompt_text": CONTINUE_PROMPT_TEXT,
        "reason": "All conditions met",
    }
