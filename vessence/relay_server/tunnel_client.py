"""
Vessence Tunnel Client — runs inside Docker to maintain a persistent
WebSocket connection to the Vessence Relay Server.

Usage:
    python tunnel_client.py

Environment variables:
    RELAY_URL   - WebSocket URL of relay (default: wss://relay.vessences.com/tunnel)
    RELAY_TOKEN - Authentication token
    USER_ID     - User identifier
    LOCAL_URL   - Local Vessence server URL (default: http://127.0.0.1:8081)
"""

import asyncio
import base64
import json
import logging
import os
import signal
import sys
import time
from typing import Optional

import httpx
import websockets
from websockets.exceptions import ConnectionClosed, ConnectionClosedError

try:
    from websockets.exceptions import InvalidStatusCode
except ImportError:
    InvalidStatusCode = Exception  # fallback for newer websockets versions

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("tunnel-client")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RELAY_URL = os.getenv("RELAY_URL", "wss://relay.vessences.com/tunnel")
RELAY_TOKEN = os.getenv("RELAY_TOKEN", "")
USER_ID = os.getenv("USER_ID", "")
LOCAL_URL = os.getenv("LOCAL_URL", "http://127.0.0.1:8081")

HEARTBEAT_INTERVAL = 30  # seconds
REQUEST_TIMEOUT = 120  # seconds
BACKOFF_INITIAL = 1.0  # seconds
BACKOFF_MAX = 60.0  # seconds
BACKOFF_FACTOR = 2.0

# ---------------------------------------------------------------------------
# Tunnel client
# ---------------------------------------------------------------------------

class TunnelClient:
    def __init__(self):
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running = True
        self._http: Optional[httpx.AsyncClient] = None

    async def run(self):
        """Main loop with auto-reconnect and exponential backoff."""
        if not RELAY_TOKEN:
            log.error("RELAY_TOKEN not set — cannot connect to relay")
            sys.exit(1)
        if not USER_ID:
            log.error("USER_ID not set — cannot connect to relay")
            sys.exit(1)

        backoff = BACKOFF_INITIAL
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=10))

        try:
            while self._running:
                try:
                    await self._connect_and_serve()
                    # Clean disconnect — reset backoff
                    backoff = BACKOFF_INITIAL
                except (ConnectionClosed, ConnectionClosedError, OSError) as exc:
                    log.warning("Connection lost: %s", exc)
                except InvalidStatusCode as exc:
                    log.error("Relay rejected connection (HTTP %s)", exc.status_code)
                except Exception as exc:
                    log.exception("Unexpected error: %s", exc)

                if not self._running:
                    break

                log.info("Reconnecting in %.1fs...", backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * BACKOFF_FACTOR, BACKOFF_MAX)
        finally:
            if self._http:
                await self._http.aclose()

    async def _connect_and_serve(self):
        """Connect to relay, authenticate, then process requests."""
        log.info("Connecting to %s", RELAY_URL)
        async with websockets.connect(
            RELAY_URL,
            ping_interval=None,  # we handle heartbeats ourselves
            max_size=100 * 1024 * 1024,  # 100 MB
            close_timeout=5,
        ) as ws:
            self._ws = ws

            # Authenticate
            await ws.send(json.dumps({
                "token": RELAY_TOKEN,
                "user_id": USER_ID,
            }))

            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            auth_resp = json.loads(raw)
            if auth_resp.get("status") != "ok":
                log.error("Auth failed: %s", auth_resp.get("message", "unknown"))
                return

            log.info("Connected and authenticated as %s", USER_ID)

            # Start heartbeat and request handler concurrently
            heartbeat_task = asyncio.create_task(self._heartbeat(ws))
            try:
                await self._handle_messages(ws)
            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
                self._ws = None

    async def _heartbeat(self, ws):
        """Send pong responses to relay pings, and our own keepalive."""
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                try:
                    await ws.send(json.dumps({"type": "pong", "ts": time.time()}))
                except Exception:
                    break
        except asyncio.CancelledError:
            return

    async def _handle_messages(self, ws):
        """Receive messages from relay and dispatch requests."""
        async for raw in ws:
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "ping":
                # Respond with pong
                await ws.send(json.dumps({"type": "pong", "ts": time.time()}))
                continue

            req_id = msg.get("id")
            if not req_id:
                continue

            # It's a forwarded HTTP request — handle in a task
            asyncio.create_task(self._handle_request(ws, msg))

    async def _handle_request(self, ws, req: dict):
        """Forward a request to the local server and send the response back."""
        req_id = req["id"]
        method = req.get("method", "GET")
        path = req.get("path", "/")
        headers = req.get("headers", {})
        body_raw = req.get("body", "")
        body_encoding = req.get("body_encoding", "utf-8")
        query = req.get("query", "")

        # Decode base64 bodies (binary/multipart uploads)
        if body_encoding == "base64" and body_raw:
            body = base64.b64decode(body_raw)
        else:
            body = body_raw

        url = f"{LOCAL_URL}{path}"
        if query:
            url = f"{url}?{query}"

        # Remove headers that could cause issues with the local request
        skip = {"host", "transfer-encoding", "connection"}
        clean_headers = {k: v for k, v in headers.items() if k.lower() not in skip}

        log.info("→ %s %s (id=%s)", method, path, req_id)

        try:
            # Check if the request might return SSE/streaming
            accept = headers.get("accept", headers.get("Accept", ""))
            wants_stream = "text/event-stream" in accept or "/stream" in path

            if wants_stream:
                await self._handle_streaming_request(ws, req_id, method, url, clean_headers, body)
            else:
                await self._handle_regular_request(ws, req_id, method, url, clean_headers, body)

        except httpx.ConnectError as exc:
            log.error("Local server unreachable: %s", exc)
            await self._send_error(ws, req_id, 502, "Local Vessence server is not running")
        except httpx.TimeoutException:
            log.error("Local server timeout for %s", req_id)
            await self._send_error(ws, req_id, 504, "Local server timeout")
        except Exception as exc:
            log.exception("Error handling request %s: %s", req_id, exc)
            await self._send_error(ws, req_id, 500, f"Tunnel error: {exc}")

    async def _handle_regular_request(self, ws, req_id, method, url, headers, body):
        """Forward a non-streaming request."""
        if isinstance(body, bytes):
            content = body if body else None
        else:
            content = body.encode("utf-8") if body else None
        response = await self._http.request(
            method=method,
            url=url,
            headers=headers,
            content=content,
        )

        resp_headers = dict(response.headers)
        resp_body = response.text

        await ws.send(json.dumps({
            "id": req_id,
            "status": response.status_code,
            "headers": resp_headers,
            "body": resp_body,
            "streaming": False,
        }))

        log.info("← %d %s (id=%s, %d bytes)", response.status_code, url, req_id, len(resp_body))

    async def _handle_streaming_request(self, ws, req_id, method, url, headers, body):
        """Forward a streaming/SSE request, sending chunks as they arrive."""
        if isinstance(body, bytes):
            content = body if body else None
        else:
            content = body.encode("utf-8") if body else None
        async with self._http.stream(
            method=method,
            url=url,
            headers=headers,
            content=content,
        ) as response:
            resp_headers = dict(response.headers)

            # Send initial response with status and headers
            await ws.send(json.dumps({
                "id": req_id,
                "status": response.status_code,
                "headers": resp_headers,
                "body": "",
                "streaming": True,
            }))

            log.info("← %d STREAM %s (id=%s)", response.status_code, url, req_id)

            # Stream chunks
            async for chunk in response.aiter_text():
                if chunk:
                    await ws.send(json.dumps({
                        "id": req_id,
                        "chunk": chunk,
                        "done": False,
                    }))

            # End of stream
            await ws.send(json.dumps({
                "id": req_id,
                "chunk": "",
                "done": True,
            }))

            log.info("← STREAM END (id=%s)", req_id)

    async def _send_error(self, ws, req_id, status, message):
        """Send an error response back through the tunnel."""
        try:
            await ws.send(json.dumps({
                "id": req_id,
                "status": status,
                "headers": {"content-type": "application/json"},
                "body": json.dumps({"error": message}),
                "streaming": False,
            }))
        except Exception:
            log.error("Failed to send error response for %s", req_id)

    def stop(self):
        self._running = False


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():
    client = TunnelClient()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Handle graceful shutdown
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, client.stop)

    try:
        loop.run_until_complete(client.run())
    except KeyboardInterrupt:
        log.info("Interrupted — shutting down")
    finally:
        loop.close()
        log.info("Tunnel client stopped")


if __name__ == "__main__":
    main()
