"""Payload and response helpers for Jane permission routes."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def permission_request_args(body: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "request_id": body["request_id"],
        "tool_name": body["tool_name"],
        "tool_input": body.get("tool_input", {}),
        "session_id": body.get("session_id", ""),
    }


def permission_response_args(body: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "request_id": body["request_id"],
        "approved": body.get("approved", False),
        "reason": body.get("reason", ""),
    }


def permission_wait_payload(approved: bool, request: Any) -> dict[str, Any]:
    return {"approved": approved, "reason": request.reason}


def permission_pending_entry(request: Any) -> dict[str, Any]:
    return {
        "request_id": request.request_id,
        "tool_name": request.tool_name,
        "tool_input": request.tool_input,
        "created_at": request.created_at,
    }
