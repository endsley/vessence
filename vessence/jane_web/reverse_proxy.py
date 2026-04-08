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

import aiohttp
from aiohttp import web

logger = logging.getLogger("jane.reverse_proxy")

STATE_FILE = Path(os.environ.get("VESSENCE_DATA_HOME", Path.home() / "ambient" / "vessence-data")) / "proxy_state.json"

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
        self._lock = asyncio.Lock()

    @property
    def upstream_url(self) -> str:
        return f"http://127.0.0.1:{self.upstream_port}"

    async def switch(self, new_port: int) -> int:
        async with self._lock:
            old = self.upstream_port
            self.upstream_port = new_port
            self.switched_at = time.time()
            logger.info("Switched upstream %d -> %d", old, new_port)
            self._persist()
            return old

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
    state.total_requests += 1
    state.active_requests += 1
    upstream = state.upstream_url
    target_url = f"{upstream}{request.path_qs}"

    # Build forwarded headers
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in HOP_BY_HOP
    }
    headers["X-Forwarded-For"] = request.remote or "unknown"
    headers["X-Forwarded-Proto"] = request.scheme

    try:
        # Check for WebSocket upgrade
        if (
            request.headers.get("Upgrade", "").lower() == "websocket"
            or request.headers.get("Connection", "").lower() == "upgrade"
        ):
            return await _proxy_websocket(request, target_url, headers)

        # Check if this is a streaming response (SSE / chunked)
        async with aiohttp.ClientSession(timeout=CONNECT_TIMEOUT) as session:
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
