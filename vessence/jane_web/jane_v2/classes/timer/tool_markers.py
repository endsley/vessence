"""Client-tool marker helpers for the timer Stage 2 handler."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from jane_web.client_tool_markers import build_client_tool_marker


TIMER_SET_TOOL = "timer.set"
TIMER_LIST_TOOL = "timer.list"
TIMER_CANCEL_TOOL = "timer.cancel"
TIMER_DELETE_TOOL = "timer.delete"


def timer_tool_marker(tool: str, args: Mapping[str, Any]) -> str:
    return build_client_tool_marker(tool, dict(args), compact_json=True)


def timer_set_marker(duration_ms: int, label: str) -> str:
    return timer_tool_marker(TIMER_SET_TOOL, {"duration_ms": duration_ms, "label": label})


def timer_list_marker() -> str:
    return timer_tool_marker(TIMER_LIST_TOOL, {})


def timer_cancel_marker() -> str:
    return timer_tool_marker(TIMER_CANCEL_TOOL, {})


def timer_delete_marker(target: Mapping[str, Any]) -> str:
    return timer_tool_marker(TIMER_DELETE_TOOL, target)
