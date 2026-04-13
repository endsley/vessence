#!/usr/bin/env python3
"""
Lightweight reverse proxy for zero-downtime deployment of Jane Web.

Sits in front of uvicorn and forwards all requests to the active upstream.
The upstream port can be swapped at runtime via a control endpoint, enabling
blue-green deployments without dropping requests.

Architecture:
    Cloudflare Tunnel -> reverse_proxy (port 8080) -> uvicorn (port 8081 or 8082)

Control API (localhost only):
    POST /proxy/switch   {"port": 8082}   — switch upstream
    GET  /proxy/status                     — show current upstream info

Usage:
    python reverse_proxy.py [--listen-port 8080] [--upstream-port 8081]
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

from collections import defaultdict
from time import monotonic as _monotonic

import aiohttp
from aiohttp import web

logger = logging.getLogger("jane.reverse_proxy")


# ── Proxy-level rate limiting ────────────────────────────────────────────────
# Catches all traffic before it reaches the application. This is the first
# line of defense against DDoS / credential-stuffing.

class _ProxyRateLimiter:
    """Simple in-memory sliding-window rate limiter for the reverse proxy."""

    def __init__(self):
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup: float = _monotonic()

    def check(self, key: str, max_requests: int, window_seconds: float) -> bool:
        now = _monotonic()
        if now - self._last_cleanup > 60:
            self._cleanup(now)
        cutoff = now - window_seconds
        timestamps = [t for t in self._hits[key] if t > cutoff]
        if len(timestamps) >= max_requests:
            self._hits[key] = timestamps
            return False
        timestamps.append(now)
        self._hits[key] = timestamps
        return True

    def _cleanup(self, now: float):
        stale = [k for k, v in self._hits.items() if not v or v[-1] < now - 120]
        for k in stale:
            del self._hits[k]
        self._last_cleanup = now


_proxy_rate_limiter = _ProxyRateLimiter()
_PROXY_MAX_REQUESTS_PER_MINUTE = 100


def _get_proxy_client_ip(request: web.Request) -> str:
    """Extract the real client IP from proxy headers or the transport."""
    return (
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.remote
        or "unknown"
    )

STATE_FILE = Path(os.environ.get("VESSENCE_DATA_HOME", Path.home() / "ambient" / "vessence-data")) / "proxy_state.json"

# ---------------------------------------------------------------------------
# Persistent upstream session (connection-pooled, not created per-request)
# ---------------------------------------------------------------------------
# One session is shared for all upstream requests. aiohttp's TCPConnector
# maintains a pool of keep-alive connections, eliminating the TCP handshake
# overhead that was previously paid on every request.
#
# Port switching (8081 ↔ 8084) still works: the session is not bound to a
# specific host/port — it routes each request to whatever URL is passed to
# session.request(). Old keep-alive connections to the previous port expire
# naturally after keepalive_timeout seconds.

_upstream_session: aiohttp.ClientSession | None = None


def _get_upstream_session() -> aiohttp.ClientSession:
    """Return the shared upstream session, creating it if needed."""
    global _upstream_session
    if _upstream_session is None or _upstream_session.closed:
        connector = aiohttp.TCPConnector(
            limit=200,              # max total connections in pool
            limit_per_host=100,     # max connections to any one upstream
            keepalive_timeout=30,   # idle keep-alive TTL (seconds)
            enable_cleanup_closed=True,
        )
        _upstream_session = aiohttp.ClientSession(
            timeout=CONNECT_TIMEOUT,
            connector=connector,
        )
    return _upstream_session

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class ProxyState:
    """Mutable state for the reverse proxy."""

    def __init__(self, upstream_port: int = 8081):
        self.upstream_port = upstream_port
        self.switched_at: float = time.time()
        self.total_requests: int = 0
        self.active_requests: int = 0
        # Per-port active request counters for drain monitoring
        self._port_active: dict[int, int] = defaultdict(int)
        self._previous_port: int | None = None
        self._lock = asyncio.Lock()

    @property
    def upstream_url(self) -> str:
        return f"http://127.0.0.1:{self.upstream_port}"

    async def switch(self, new_port: int) -> int:
        async with self._lock:
            old = self.upstream_port
            self._previous_port = old
            self.upstream_port = new_port
            self.switched_at = time.time()
            logger.info("Switched upstream %d -> %d", old, new_port)
            self._persist()
            return old

    def drain_active(self) -> int:
        """Return active requests on the PREVIOUS upstream (for drain monitoring)."""
        if self._previous_port is not None:
            return self._port_active.get(self._previous_port, 0)
        return 0

    def _persist(self):
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps({"upstream_port": self.upstream_port}))
        except Exception as e:
            logger.warning("Failed to persist proxy state: %s", e)


state = ProxyState()

# ---------------------------------------------------------------------------
# Control endpoints (only accessible from localhost)
# ---------------------------------------------------------------------------

def _is_localhost(request: web.Request) -> bool:
    peername = request.transport.get_extra_info("peername")
    if peername is None:
        return False
    host = peername[0]
    return host in ("127.0.0.1", "::1", "localhost")


async def handle_switch(request: web.Request) -> web.Response:
    """POST /proxy/switch  {"port": 8082}"""
    if not _is_localhost(request):
        return web.json_response({"error": "forbidden"}, status=403)
    try:
        body = await request.json()
        new_port = int(body["port"])
    except (json.JSONDecodeError, KeyError, ValueError):
        return web.json_response({"error": "need JSON body with 'port' integer"}, status=400)

    old_port = await state.switch(new_port)
    return web.json_response({
        "status": "switched",
        "old_port": old_port,
        "new_port": new_port,
    })


async def handle_status(request: web.Request) -> web.Response:
    """GET /proxy/status"""
    if not _is_localhost(request):
        return web.json_response({"error": "forbidden"}, status=403)
    return web.json_response({
        "upstream_port": state.upstream_port,
        "upstream_url": state.upstream_url,
        "switched_at": state.switched_at,
        "total_requests": state.total_requests,
        "active_requests": state.active_requests,
        "drain_active": state.drain_active(),
        "previous_port": state._previous_port,
    })


# ---------------------------------------------------------------------------
# Proxy handler
# ---------------------------------------------------------------------------

# Timeout for connecting to upstream — fail fast if upstream is down
CONNECT_TIMEOUT = aiohttp.ClientTimeout(total=None, connect=5)

# Headers that must not be forwarded
HOP_BY_HOP = frozenset({
    "connection", "keep-alive", "proxy-authenticate",
    "proxy-authorization", "te", "trailers",
    "transfer-encoding", "upgrade",
})


async def proxy_handler(request: web.Request) -> web.StreamResponse:
    """Forward every request to the active upstream."""
    # ── Global rate limiting (per IP) ─────────────────────────────────────
    client_ip = _get_proxy_client_ip(request)
    if client_ip not in ("127.0.0.1", "::1", "localhost"):
        if not _proxy_rate_limiter.check(f"proxy:{client_ip}", _PROXY_MAX_REQUESTS_PER_MINUTE, 60):
            logger.warning("Proxy rate limit hit for %s on %s", client_ip, request.path)
            return web.json_response(
                {"error": "Rate limit exceeded. Please slow down."},
                status=429,
            )

    state.total_requests += 1
    state.active_requests += 1
    upstream = state.upstream_url
    upstream_port = state.upstream_port
    state._port_active[upstream_port] += 1
    target_url = f"{upstream}{request.path_qs}"

    # Build forwarded headers
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in HOP_BY_HOP
    }
    headers["X-Forwarded-For"] = client_ip
    headers["X-Forwarded-Proto"] = request.scheme

    try:
        # Check for WebSocket upgrade
        if (
            request.headers.get("Upgrade", "").lower() == "websocket"
            or request.headers.get("Connection", "").lower() == "upgrade"
        ):
            return await _proxy_websocket(request, target_url, headers)

        # Check if this is a streaming response (SSE / chunked)
        # Use the shared persistent session (connection pool) — not a per-request session.
        session = _get_upstream_session()
        async with session.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=await request.read() if request.can_read_body else None,
            allow_redirects=False,
        ) as upstream_resp:
            # If upstream sends chunked / streaming, stream it through
            is_streaming = (
                upstream_resp.headers.get("Transfer-Encoding", "").lower() == "chunked"
                or "text/event-stream" in upstream_resp.headers.get("Content-Type", "")
            )

            if is_streaming:
                response = web.StreamResponse(
                    status=upstream_resp.status,
                    headers={
                        k: v for k, v in upstream_resp.headers.items()
                        if k.lower() not in HOP_BY_HOP
                    },
                )
                await response.prepare(request)
                async for chunk in upstream_resp.content.iter_any():
                    await response.write(chunk)
                await response.write_eof()
                return response
            else:
                body = await upstream_resp.read()
                return web.Response(
                    status=upstream_resp.status,
                    headers={
                        k: v for k, v in upstream_resp.headers.items()
                        if k.lower() not in HOP_BY_HOP
                    },
                    body=body,
                )
    except aiohttp.ClientConnectorError as exc:
        logger.error("Upstream connection failed (%s): %s", upstream, exc)
        return web.json_response(
            {"error": "upstream_unavailable", "detail": str(exc)},
            status=502,
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("Proxy error for %s %s", request.method, request.path)
        return web.json_response(
            {"error": "proxy_error", "detail": str(exc)},
            status=502,
        )
    finally:
        state.active_requests -= 1
        state._port_active[upstream_port] = max(0, state._port_active.get(upstream_port, 1) - 1)


async def _proxy_websocket(
    request: web.Request, target_url: str, headers: dict
) -> web.WebSocketResponse:
    """Proxy a WebSocket connection."""
    ws_client = web.WebSocketResponse()
    await ws_client.prepare(request)

    ws_url = target_url.replace("http://", "ws://").replace("https://", "wss://")

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(ws_url, headers=headers) as ws_upstream:

            async def _forward_client_to_upstream():
                async for msg in ws_client:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await ws_upstream.send_str(msg.data)
                    elif msg.type == aiohttp.WSMsgType.BINARY:
                        await ws_upstream.send_bytes(msg.data)
                    elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                        break

            async def _forward_upstream_to_client():
                async for msg in ws_upstream:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await ws_client.send_str(msg.data)
                    elif msg.type == aiohttp.WSMsgType.BINARY:
                        await ws_client.send_bytes(msg.data)
                    elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                        break

            await asyncio.gather(
                _forward_client_to_upstream(),
                _forward_upstream_to_client(),
                return_exceptions=True,
            )

    return ws_client


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

def create_app(upstream_port: int = 8081) -> web.Application:
    # Restore persisted state if available
    try:
        if STATE_FILE.exists():
            saved = json.loads(STATE_FILE.read_text())
            upstream_port = saved.get("upstream_port", upstream_port)
            logger.info("Restored persisted upstream port: %d", upstream_port)
    except Exception:
        pass
    state.upstream_port = upstream_port

    app = web.Application()
    # Control routes — must be registered before the catch-all
    app.router.add_post("/proxy/switch", handle_switch)
    app.router.add_get("/proxy/status", handle_status)
    # Catch-all proxy
    app.router.add_route("*", "/{path_info:.*}", proxy_handler)

    return app


def main():
    parser = argparse.ArgumentParser(description="Jane Web Reverse Proxy")
    parser.add_argument("--listen-port", type=int, default=8080,
                        help="Port this proxy listens on (default: 8080)")
    parser.add_argument("--upstream-port", type=int, default=8081,
                        help="Initial upstream uvicorn port (default: 8081)")
    parser.add_argument("--log-level", default="info",
                        choices=["debug", "info", "warning", "error"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    logger.info(
        "Starting reverse proxy on port %d -> upstream %d",
        args.listen_port, args.upstream_port,
    )

    app = create_app(upstream_port=args.upstream_port)
    web.run_app(app, host="127.0.0.1", port=args.listen_port)


if __name__ == "__main__":
    main()
