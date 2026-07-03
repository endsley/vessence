"""Self-healing report authorization and payload normalization helpers."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from typing import Any


def self_healing_report_authorized(
    request: Any,
    *,
    expected_token: str,
    is_local_request_fn: Callable[[Any], bool],
) -> bool:
    if is_local_request_fn(request):
        return True
    expected = (expected_token or "").strip()
    provided = request.headers.get("x-jane-self-heal-token", "").strip()
    return bool(expected and provided and secrets.compare_digest(expected, provided))


def normalize_self_healing_report(body: dict[str, Any], *, default_project_root: str) -> dict[str, Any]:
    tags = body.get("tags") if isinstance(body.get("tags"), list) else ["external"]
    payload = body.get("payload") if isinstance(body.get("payload"), dict) else body
    return {
        "source": str(body.get("source") or "external_app"),
        "category": str(body.get("category") or "error"),
        "message": str(body.get("message") or "")[:2000],
        "project_root": str(body.get("project_root") or default_project_root),
        "tags": tags,
        "payload": payload,
    }
