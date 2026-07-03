"""Pure helpers for reverse_proxy.py."""

from __future__ import annotations

from collections.abc import Mapping


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
