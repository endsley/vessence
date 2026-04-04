"""
Vessence Relay Server
Routes requests between phones and home-hosted Vessence Docker instances
via persistent WebSocket tunnels. Includes account management.
"""

import asyncio
import base64
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import jwt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Header
from fastapi.responses import JSONResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles

import database as db

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("relay")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HEARTBEAT_INTERVAL = 30  # seconds
HEARTBEAT_TIMEOUT = 90  # seconds — disconnect if no pong
REQUEST_TIMEOUT = 120  # seconds — max wait for home server response
MAX_BODY_SIZE = 100 * 1024 * 1024  # 100 MB

SECRET_KEY = os.getenv("VESSENCE_SECRET_KEY", "vessence-dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 30

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

# ---------------------------------------------------------------------------
# JWT session tokens
# ---------------------------------------------------------------------------

def create_session_token(user_id: str) -> str:
    """Create a JWT session token for the given user."""
    payload = {
        "sub": user_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_session_token(token: str) -> Optional[str]:
    """Verify a JWT session token. Returns user_id or None."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


async def get_authenticated_user(request: Request) -> Optional[db.User]:
    """Extract and verify session token from request headers."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = request.headers.get("x-session-token", "")

    if not token:
        return None

    user_id = verify_session_token(token)
    if not user_id:
        return None

    return db.get_user_by_id(user_id)


# ---------------------------------------------------------------------------
# Tunnel token validation (database-backed)
# ---------------------------------------------------------------------------

def validate_token(user_id: str, token: str) -> bool:
    """Validate a tunnel auth token against the database."""
    if not token:
        return False
    user = db.get_user_by_relay_token(token)
    if user is None:
        log.warning("Tunnel auth: no user found for provided relay token")
        return False
    if user.id != user_id:
        log.warning("Tunnel auth: token belongs to user %s but claimed user_id %s", user.id, user_id)
        return False
    return True


# ---------------------------------------------------------------------------
# Tunnel registry
# ---------------------------------------------------------------------------

@dataclass
class TunnelConnection:
    user_id: str
    ws: WebSocket
    connected_at: float = field(default_factory=time.time)
    last_pong: float = field(default_factory=time.time)
    pending: dict[str, asyncio.Future] = field(default_factory=dict)
    streams: dict[str, asyncio.Queue] = field(default_factory=dict)
    _heartbeat_task: Optional[asyncio.Task] = field(default=None, repr=False)


class TunnelRegistry:
    def __init__(self):
        self._connections: dict[str, TunnelConnection] = {}
        self._lock = asyncio.Lock()

    async def register(self, user_id: str, conn: TunnelConnection):
        async with self._lock:
            old = self._connections.get(user_id)
            if old:
                log.info("Replacing existing tunnel for %s", user_id)
                await self._cleanup(old)
            self._connections[user_id] = conn
            log.info("Tunnel registered: %s (total: %d)", user_id, len(self._connections))

    async def unregister(self, user_id: str):
        async with self._lock:
            conn = self._connections.pop(user_id, None)
            if conn:
                await self._cleanup(conn)
                log.info("Tunnel unregistered: %s (total: %d)", user_id, len(self._connections))

    def get(self, user_id: str) -> Optional[TunnelConnection]:
        return self._connections.get(user_id)

    @property
    def active_count(self) -> int:
        return len(self._connections)

    @property
    def all_users(self) -> list[str]:
        return list(self._connections.keys())

    async def _cleanup(self, conn: TunnelConnection):
        """Cancel heartbeat and fail all pending requests."""
        if conn._heartbeat_task and not conn._heartbeat_task.done():
            conn._heartbeat_task.cancel()
        for req_id, fut in conn.pending.items():
            if not fut.done():
                fut.set_exception(ConnectionError("Tunnel disconnected"))
        conn.pending.clear()
        for req_id, queue in conn.streams.items():
            await queue.put(None)
        conn.streams.clear()
        try:
            await conn.ws.close()
        except Exception:
            pass


registry = TunnelRegistry()
START_TIME = time.time()

# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Vessence Relay Server starting")
    yield
    log.info("Vessence Relay Server shutting down")
    for user_id in list(registry.all_users):
        await registry.unregister(user_id)


app = FastAPI(title="Vessence Relay", lifespan=lifespan)

# ---------------------------------------------------------------------------
# Health & status endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "uptime_seconds": int(time.time() - START_TIME)}


@app.get("/api/relay/status")
async def relay_status():
    uptime = int(time.time() - START_TIME)
    days, rem = divmod(uptime, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return {
        "active_tunnels": registry.active_count,
        "uptime": " ".join(parts),
        "uptime_seconds": uptime,
    }


@app.get("/api/relay/user/{user_id}/status")
async def user_status(user_id: str):
    conn = registry.get(user_id)
    if not conn:
        return {"online": False}
    latency_ms = int((time.time() - conn.last_pong) * 1000)
    connected_since = datetime.fromtimestamp(conn.connected_at, tz=timezone.utc).isoformat()
    return {
        "online": True,
        "connected_since": connected_since,
        "latency_ms": min(latency_ms, HEARTBEAT_INTERVAL * 1000),
    }

# ---------------------------------------------------------------------------
# Account API endpoints
# ---------------------------------------------------------------------------

@app.post("/api/accounts/register")
async def register(request: Request):
    """Register a new Vessence account."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    email = body.get("email", "").strip()
    display_name = body.get("display_name", "").strip()
    password = body.get("password", "")

    if not email or not display_name or not password:
        return JSONResponse(
            status_code=400,
            content={"error": "email, display_name, and password are required"},
        )

    if len(password) < 8:
        return JSONResponse(
            status_code=400,
            content={"error": "Password must be at least 8 characters"},
        )

    try:
        user = db.create_user(email, display_name, password)
    except ValueError:
        return JSONResponse(
            status_code=409,
            content={"error": "An account with this email already exists"},
        )

    log.info("New account registered: %s (%s)", user.email, user.id)
    return JSONResponse(
        status_code=201,
        content={
            "user_id": user.id,
            "relay_token": user.relay_token,
            "message": "Account created",
        },
    )


@app.post("/api/accounts/login")
async def login(request: Request):
    """Log in with email and password."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    email = body.get("email", "").strip()
    password = body.get("password", "")

    if not email or not password:
        return JSONResponse(
            status_code=400,
            content={"error": "email and password are required"},
        )

    user = db.get_user_by_email(email)
    if not user or not db.verify_password(password, user.password_hash):
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid email or password"},
        )

    db.update_last_login(user.id)
    session_token = create_session_token(user.id)

    log.info("User logged in: %s (%s)", user.email, user.id)
    return {
        "user_id": user.id,
        "relay_token": user.relay_token,
        "display_name": user.display_name,
        "session_token": session_token,
    }


@app.post("/api/accounts/google-login")
async def google_login(request: Request):
    """Log in or register via Google OAuth ID token."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    id_token = body.get("id_token", "")
    if not id_token:
        return JSONResponse(
            status_code=400,
            content={"error": "id_token is required"},
        )

    # Verify the Google ID token
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests

        idinfo = google_id_token.verify_oauth2_token(
            id_token, google_requests.Request(), GOOGLE_CLIENT_ID
        )
        google_id = idinfo["sub"]
        email = idinfo.get("email", "")
        name = idinfo.get("name", email.split("@")[0])
    except ImportError:
        log.warning("google-auth library not installed — Google login unavailable")
        return JSONResponse(
            status_code=501,
            content={"error": "Google login not configured on this server"},
        )
    except Exception as e:
        log.warning("Google token verification failed: %s", e)
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid Google token"},
        )

    # Look up existing user by google_id
    user = db.get_user_by_google_id(google_id)
    if not user:
        # Check if email already exists (link accounts)
        user = db.get_user_by_email(email)
        if user:
            # Link google_id to existing account
            conn = db._get_conn()
            try:
                conn.execute("UPDATE users SET google_id = ? WHERE id = ?", (google_id, user.id))
                conn.commit()
            finally:
                conn.close()
        else:
            # Create new account
            user = db.create_user_from_google(email, name, google_id)
            log.info("New Google account registered: %s (%s)", user.email, user.id)

    db.update_last_login(user.id)
    session_token = create_session_token(user.id)

    return {
        "user_id": user.id,
        "relay_token": user.relay_token,
        "display_name": user.display_name,
        "session_token": session_token,
    }


@app.get("/api/accounts/me")
async def get_me(request: Request):
    """Get the current user's profile."""
    user = await get_authenticated_user(request)
    if not user:
        return JSONResponse(
            status_code=401,
            content={"error": "Not authenticated"},
        )
    return user.to_public_dict()


@app.post("/api/accounts/relay-token/regenerate")
async def regenerate_token(request: Request):
    """Generate a new relay token (invalidates the old one)."""
    user = await get_authenticated_user(request)
    if not user:
        return JSONResponse(
            status_code=401,
            content={"error": "Not authenticated"},
        )

    new_token = db.regenerate_relay_token(user.id)
    log.info("Relay token regenerated for user %s", user.id)
    return {"relay_token": new_token}


# ---------------------------------------------------------------------------
# Tunnel WebSocket endpoint
# ---------------------------------------------------------------------------

async def _heartbeat(conn: TunnelConnection):
    """Send pings and monitor pongs."""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            try:
                await conn.ws.send_json({"type": "ping", "ts": time.time()})
            except Exception:
                log.warning("Failed to send heartbeat to %s", conn.user_id)
                break
            if time.time() - conn.last_pong > HEARTBEAT_TIMEOUT:
                log.warning("Heartbeat timeout for %s", conn.user_id)
                break
    except asyncio.CancelledError:
        return
    await registry.unregister(conn.user_id)


@app.websocket("/tunnel")
async def tunnel_endpoint(ws: WebSocket):
    await ws.accept()

    # --- Auth: first message must be {"token": "...", "user_id": "..."} ---
    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=10)
        auth = json.loads(raw)
        token = auth.get("token", "")
        user_id = auth.get("user_id", "")
    except (asyncio.TimeoutError, json.JSONDecodeError, KeyError) as exc:
        log.warning("Tunnel auth failed: %s", exc)
        await ws.send_json({"type": "auth", "status": "error", "message": "Invalid auth"})
        await ws.close(code=4001, reason="Auth failed")
        return

    if not user_id or not validate_token(user_id, token):
        log.warning("Tunnel auth rejected for user_id=%s", user_id)
        await ws.send_json({"type": "auth", "status": "error", "message": "Invalid token"})
        await ws.close(code=4003, reason="Invalid token")
        return

    await ws.send_json({"type": "auth", "status": "ok"})
    log.info("Tunnel authenticated: %s", user_id)

    conn = TunnelConnection(user_id=user_id, ws=ws)
    conn._heartbeat_task = asyncio.create_task(_heartbeat(conn))
    await registry.register(user_id, conn)

    # --- Main receive loop ---
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "pong":
                conn.last_pong = time.time()
                continue

            req_id = msg.get("id")
            if not req_id:
                continue

            streaming = msg.get("streaming", False)
            is_chunk = "chunk" in msg

            if is_chunk:
                queue = conn.streams.get(req_id)
                if queue:
                    done = msg.get("done", False)
                    chunk_data = msg.get("chunk", "")
                    await queue.put(chunk_data if not done else None)
                    if done:
                        conn.streams.pop(req_id, None)
            elif streaming:
                queue = asyncio.Queue()
                conn.streams[req_id] = queue
                fut = conn.pending.get(req_id)
                if fut and not fut.done():
                    fut.set_result(msg)
            else:
                fut = conn.pending.pop(req_id, None)
                if fut and not fut.done():
                    fut.set_result(msg)

    except WebSocketDisconnect:
        log.info("Tunnel disconnected: %s", user_id)
    except Exception as exc:
        log.exception("Tunnel error for %s: %s", user_id, exc)
    finally:
        await registry.unregister(user_id)

# ---------------------------------------------------------------------------
# Proxy endpoint: ANY /r/{user_id}/{path:path}
# ---------------------------------------------------------------------------

@app.api_route("/r/{user_id}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy(user_id: str, path: str, request: Request):
    conn = registry.get(user_id)
    if not conn:
        return JSONResponse(
            status_code=503,
            content={"error": "Vessence is offline", "user_id": user_id},
        )

    req_id = f"req_{uuid.uuid4().hex[:12]}"

    skip_headers = {"host", "connection", "upgrade", "transfer-encoding"}
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in skip_headers
    }

    body = await request.body()

    # Binary bodies (multipart uploads) must be base64-encoded to survive
    # JSON serialization over the WebSocket tunnel.
    content_type = headers.get("content-type", headers.get("Content-Type", ""))
    is_binary = body and (
        "multipart/form-data" in content_type
        or "application/octet-stream" in content_type
    )

    if is_binary:
        body_payload = base64.b64encode(body).decode("ascii")
        body_encoding = "base64"
    else:
        body_payload = body.decode("utf-8", errors="replace") if body else ""
        body_encoding = "utf-8"

    tunnel_req = {
        "id": req_id,
        "method": request.method,
        "path": f"/{path}",
        "headers": headers,
        "body": body_payload,
        "body_encoding": body_encoding,
        "query": str(request.url.query) if request.url.query else "",
    }

    fut: asyncio.Future = asyncio.get_event_loop().create_future()
    conn.pending[req_id] = fut

    try:
        await conn.ws.send_json(tunnel_req)
    except Exception as exc:
        conn.pending.pop(req_id, None)
        log.error("Failed to send request to tunnel %s: %s", user_id, exc)
        return JSONResponse(
            status_code=502,
            content={"error": "Tunnel send failed"},
        )

    try:
        resp_msg = await asyncio.wait_for(fut, timeout=REQUEST_TIMEOUT)
    except asyncio.TimeoutError:
        conn.pending.pop(req_id, None)
        conn.streams.pop(req_id, None)
        return JSONResponse(
            status_code=504,
            content={"error": "Home server timeout"},
        )
    except ConnectionError:
        return JSONResponse(
            status_code=503,
            content={"error": "Vessence went offline during request"},
        )

    status = resp_msg.get("status", 200)
    resp_headers = resp_msg.get("headers", {})

    skip_resp = {"transfer-encoding", "connection", "keep-alive", "content-length"}
    clean_headers = {
        k: v for k, v in resp_headers.items()
        if k.lower() not in skip_resp
    }

    streaming = resp_msg.get("streaming", False)

    if streaming:
        queue = conn.streams.get(req_id)
        if not queue:
            return Response(
                content=resp_msg.get("body", ""),
                status_code=status,
                headers=clean_headers,
            )

        async def stream_generator():
            try:
                while True:
                    try:
                        chunk = await asyncio.wait_for(queue.get(), timeout=REQUEST_TIMEOUT)
                    except asyncio.TimeoutError:
                        log.warning("Stream timeout for %s/%s", user_id, req_id)
                        break
                    if chunk is None:
                        break
                    yield chunk.encode("utf-8") if isinstance(chunk, str) else chunk
            finally:
                conn.streams.pop(req_id, None)

        content_type = clean_headers.pop("content-type", "text/event-stream")
        return StreamingResponse(
            stream_generator(),
            status_code=status,
            headers=clean_headers,
            media_type=content_type,
        )
    else:
        body_content = resp_msg.get("body", "")
        content_bytes = body_content.encode("utf-8") if isinstance(body_content, str) else body_content
        return Response(
            content=content_bytes,
            status_code=status,
            headers=clean_headers,
        )


# ---------------------------------------------------------------------------
# Stripe / Relay subscription endpoints
# ---------------------------------------------------------------------------

@app.post("/api/relay/subscribe")
async def subscribe_relay(request: Request):
    """Create a Stripe Checkout session for relay subscription."""
    user = await get_authenticated_user(request)
    if not user:
        return JSONResponse(
            status_code=401,
            content={"error": "Not authenticated"},
        )

    try:
        from stripe_integration import create_checkout_session
        checkout_url = create_checkout_session(user.id, user.email)
    except RuntimeError as e:
        return JSONResponse(
            status_code=503,
            content={"error": str(e)},
        )
    except Exception as e:
        log.exception("Stripe checkout error: %s", e)
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to create checkout session"},
        )

    return {"checkout_url": checkout_url}


@app.get("/api/relay/subscription-status")
async def subscription_status(request: Request):
    """Check if the current user has an active relay subscription."""
    user = await get_authenticated_user(request)
    if not user:
        return JSONResponse(
            status_code=401,
            content={"error": "Not authenticated"},
        )

    from stripe_integration import verify_subscription
    active = verify_subscription(user.id)
    return {"subscribed": active, "user_id": user.id}


@app.post("/api/relay/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events for subscription lifecycle."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        from stripe_integration import handle_webhook_event
        result = handle_webhook_event(payload, sig_header)
    except RuntimeError as e:
        return JSONResponse(
            status_code=503,
            content={"error": str(e)},
        )
    except Exception as e:
        log.warning("Stripe webhook error: %s", e)
        return JSONResponse(
            status_code=400,
            content={"error": "Webhook verification failed"},
        )

    log.info("Stripe webhook processed: %s", result.get("event"))
    return {"received": True, "result": result}


# ---------------------------------------------------------------------------
# Static files (registration/login pages) — mounted last so API routes win
# ---------------------------------------------------------------------------

_static_dir = Path(__file__).parent / "static"
if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static_dir), html=True), name="static")

# Convenience redirects
@app.get("/register")
async def register_page():
    return Response(
        content=(_static_dir / "register.html").read_bytes(),
        media_type="text/html",
    )

@app.get("/login")
async def login_page():
    return Response(
        content=(_static_dir / "login.html").read_bytes(),
        media_type="text/html",
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("RELAY_PORT", "8080"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
