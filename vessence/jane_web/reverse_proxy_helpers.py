"""Pure helpers for reverse_proxy.py."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


HOP_BY_HOP = frozenset({
    "connection", "keep-alive", "proxy-authenticate",
    "proxy-authorization", "te", "trailers",
    "transfer-encoding", "upgrade",
})


def filtered_proxy_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {
        key: value for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP
    }


def forwarded_request_headers(
    headers: Mapping[str, str],
    *,
    client_ip: str,
    scheme: str,
) -> dict[str, str]:
    forwarded = filtered_proxy_headers(headers)
    forwarded["X-Forwarded-For"] = client_ip
    forwarded["X-Forwarded-Proto"] = scheme
    return forwarded


def is_websocket_upgrade(headers: Mapping[str, str]) -> bool:
    return (
        headers.get("Upgrade", "").lower() == "websocket"
        or headers.get("Connection", "").lower() == "upgrade"
    )


def is_streaming_response(headers: Mapping[str, str]) -> bool:
    return (
        headers.get("Transfer-Encoding", "").lower() == "chunked"
        or "text/event-stream" in headers.get("Content-Type", "")
    )


def proxy_status_payload(state: Any) -> dict[str, Any]:
    return {
        "upstream_port": state.upstream_port,
        "upstream_url": state.upstream_url,
        "switched_at": state.switched_at,
        "total_requests": state.total_requests,
        "active_requests": state.active_requests,
        "drain_active": state.drain_active(),
        "previous_port": state._previous_port,
    }


def restored_upstream_port(state_file: Any, default_port: int) -> tuple[int, bool]:
    try:
        if state_file.exists():
            saved = json.loads(state_file.read_text())
            return saved.get("upstream_port", default_port), True
    except Exception:
        pass
    return default_port, False
