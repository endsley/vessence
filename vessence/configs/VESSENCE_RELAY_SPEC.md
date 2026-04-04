# Vessence Relay Server Specification

**Version:** 1.0
**Date:** 2026-03-21
**Purpose:** Enable phone/remote access to home-hosted Vessence without user networking setup

---

## 1. Overview

The Vessence Relay is a lightweight reverse proxy that connects users' mobile devices to their home-hosted Vessence Docker instance. Users do nothing — the Docker container auto-registers with the relay on startup, and the Android app connects through the relay transparently.

```
┌─────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  Android App │ ──────► │  relay.vessences  │ ──────► │  Home Docker    │
│  (anywhere)  │  HTTPS  │  .com             │  WSS    │  (user's PC)    │
│              │ ◄────── │  (VPS)            │ ◄────── │  Jane Web 8081  │
└─────────────┘         └──────────────────┘         └─────────────────┘
```

**Key principle:** The relay never processes AI requests or stores user data. It only forwards encrypted traffic between the phone and the home server.

---

## 2. Architecture

### 2.1 Components

| Component | Location | Purpose |
|---|---|---|
| **Relay Server** | `relay.vessences.com` (VPS) | Routes requests between phones and home servers |
| **Tunnel Client** | Inside Vessence Docker | Maintains persistent connection to relay |
| **Relay SDK** | Android app / web client | Connects to relay instead of direct server URL |

### 2.2 How It Works

**Registration (Docker startup):**
1. Docker container starts
2. Tunnel client reads `RELAY_TOKEN` from `.env` (assigned during account creation)
3. Client opens a persistent WebSocket to `wss://relay.vessences.com/tunnel`
4. Sends auth: `{"token": "...", "user_id": "..."}`
5. Relay maps `user_id → WebSocket connection`
6. Connection maintained with heartbeats every 30s

**Request routing (phone → home):**
1. Android app sends request to `https://relay.vessences.com/r/{user_id}/api/jane/chat`
2. Relay looks up `user_id` in connection map
3. Relay forwards the HTTP request over the WebSocket tunnel to the home Docker
4. Home Docker processes the request (Jane web handles it normally)
5. Response flows back: Home → WebSocket → Relay → HTTPS → Phone

**Streaming (SSE):**
1. For streaming endpoints (chat), relay maintains the SSE connection to the phone
2. Home Docker streams chunks over the WebSocket tunnel
3. Relay re-emits each chunk as SSE to the phone
4. Keepalive heartbeats prevent tunnel/proxy timeouts

---

## 3. Relay Server Implementation

### 3.1 Technology
- **Language:** Python (FastAPI + uvicorn)
- **WebSocket:** `websockets` library for tunnel connections
- **Proxy:** `httpx` for forwarding HTTP requests
- **Hosting:** Single VPS (Hetzner/DigitalOcean, 2 vCPU, 4 GB RAM)
- **SSL:** Let's Encrypt via Caddy or Nginx reverse proxy

### 3.2 API Endpoints

#### Tunnel Management

```
WSS /tunnel
  Auth: {"token": "relay_token", "user_id": "user_abc"}
  Purpose: Home Docker maintains this connection permanently
  Protocol: Bidirectional JSON messages over WebSocket
  Heartbeat: Every 30s, both sides send ping
```

```
GET /api/relay/status
  Returns: {"active_tunnels": 42, "uptime": "3d 14h"}
  Auth: Admin only
```

```
GET /api/relay/user/{user_id}/status
  Returns: {"online": true, "connected_since": "2026-03-21T10:00:00Z", "latency_ms": 45}
  Auth: User's auth token
```

#### Request Routing

```
ANY /r/{user_id}/{path:path}
  Purpose: Forwards any HTTP request to the user's home server via tunnel
  Auth: User's session token (cookie or header)
  Headers forwarded: All except Host (rewritten)
  Body forwarded: Raw bytes (supports file upload)
  Response: Proxied from home server (supports streaming/SSE)
```

### 3.3 Tunnel Protocol

Messages over the WebSocket tunnel are JSON-framed:

**Request (relay → home):**
```json
{
  "id": "req_abc123",
  "method": "POST",
  "path": "/api/jane/chat/stream",
  "headers": {"Content-Type": "application/json", "Cookie": "session_id=..."},
  "body": "{\"message\": \"hello\"}"
}
```

**Response (home → relay):**
```json
{
  "id": "req_abc123",
  "status": 200,
  "headers": {"Content-Type": "text/event-stream"},
  "body": "{\"type\": \"delta\", \"data\": \"Hi\"}",
  "streaming": true
}
```

**Stream chunk (home → relay):**
```json
{
  "id": "req_abc123",
  "chunk": "{\"type\": \"delta\", \"data\": \" there\"}\n",
  "done": false
}
```

**Stream end:**
```json
{
  "id": "req_abc123",
  "chunk": "",
  "done": true
}
```

### 3.4 Connection Management

| Scenario | Handling |
|---|---|
| Home server goes offline | Relay marks user as offline, phone gets "Vessence is offline" |
| Home server reconnects | Relay re-registers, phone auto-reconnects |
| Phone disconnects | No effect on tunnel — home stays connected |
| Relay restarts | Home Docker auto-reconnects (exponential backoff) |
| Multiple devices per user | All route through the same tunnel |

### 3.5 Security

- **Tunnel auth:** Each user gets a unique `RELAY_TOKEN` at account creation. Tokens are hashed server-side.
- **Request auth:** Phone's session cookies are forwarded to the home server — the home server validates auth, not the relay.
- **Encryption:** All traffic is TLS (HTTPS/WSS). Relay cannot read request bodies.
- **No data storage:** Relay stores only: user_id → connection mapping (in memory). No logs of request content.
- **Rate limiting:** Per-user rate limits to prevent abuse (100 req/min default).

---

## 4. Tunnel Client (Docker Side)

### 4.1 Implementation

A lightweight Python script that runs inside the Vessence Docker container:

```python
# vessence_tunnel.py — auto-connects to relay on Docker startup
import asyncio
import websockets
import httpx
import json
import os

RELAY_URL = os.getenv("RELAY_URL", "wss://relay.vessences.com/tunnel")
RELAY_TOKEN = os.getenv("RELAY_TOKEN", "")
LOCAL_URL = "http://127.0.0.1:8081"  # Jane web

async def tunnel():
    async with websockets.connect(RELAY_URL) as ws:
        # Authenticate
        await ws.send(json.dumps({"token": RELAY_TOKEN, "user_id": USER_ID}))

        # Process forwarded requests
        async for msg in ws:
            req = json.loads(msg)
            # Forward to local Jane web
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=req["method"],
                    url=f"{LOCAL_URL}{req['path']}",
                    headers=req.get("headers", {}),
                    content=req.get("body", ""),
                )
                await ws.send(json.dumps({
                    "id": req["id"],
                    "status": response.status_code,
                    "headers": dict(response.headers),
                    "body": response.text,
                }))
```

### 4.2 Docker Integration

Added to `docker-compose.yml` as a sidecar service:

```yaml
  tunnel:
    image: vessence/tunnel-client
    depends_on:
      - jane
    environment:
      - RELAY_URL=wss://relay.vessences.com/tunnel
      - RELAY_TOKEN=${RELAY_TOKEN}
      - LOCAL_URL=http://jane:8090
    restart: always
```

Or bundled into the Jane container as a background process.

### 4.3 Auto-Registration

On first Docker startup (during onboarding):
1. User creates account on vessences.com
2. Account creation generates a `RELAY_TOKEN`
3. Token is saved to `.env`
4. Docker container reads token and auto-connects to relay
5. User opens Android app, logs in with same account → relay routes to their Docker

---

## 5. Android App Integration

### 5.1 Connection Flow

1. User logs in on Android app
2. App checks: "Do I have a direct server URL?" (e.g., localhost, Tailscale IP)
3. If not → use relay: `https://relay.vessences.com/r/{user_id}/`
4. All API calls go through this base URL
5. Relay forwards to home server transparently

### 5.2 Settings

In Android app Settings:
- **Connection mode:**
  - "Auto (via Vessence relay)" — default, works everywhere
  - "Direct (local network)" — user enters IP:port for same-network use
  - "Custom URL" — user enters their own domain (Cloudflare, Tailscale, etc.)

### 5.3 Offline Detection

- App pings `relay.vessences.com/r/{user_id}/health` on startup
- If relay returns "offline" → show "Your Vessence is offline. Make sure your computer is running."
- If relay is unreachable → show "No internet connection"

---

## 6. Scaling

### 6.1 Resource Estimates

| Users | Connections | RAM | Bandwidth | CPU | Monthly Cost |
|---|---|---|---|---|---|
| 100 | 200 | 1 GB | 10 Mbps | 1 vCPU | ~$5 |
| 1,000 | 2,000 | 4 GB | 100 Mbps | 2 vCPU | ~$20 |
| 10,000 | 20,000 | 16 GB | 1 Gbps | 4 vCPU | ~$80 |
| 100,000 | 200,000 | 64 GB | 10 Gbps | 16 vCPU | ~$500 |

Bandwidth is the main cost driver (file sync). Chat-only is negligible.

### 6.2 Horizontal Scaling

When single-server limit is reached:
- Deploy multiple relay servers behind a load balancer
- Use Redis for cross-server user → connection mapping
- Route by user_id hash to consistent relay server

### 6.3 Regional Deployment

For low latency:
- US East, US West, EU, Asia relay servers
- User connects to nearest relay (GeoDNS)
- Home Docker connects to same relay as phone (coordinated via account region)

---

## 7. Account Integration

The relay ties into the Vessence account system:

1. **Sign up on vessences.com** → creates account, generates RELAY_TOKEN
2. **Download Docker package** → token pre-embedded or entered during onboarding
3. **Download Android app** → sign in with same account
4. **Relay auto-routes** → phone finds home server via relay

No networking knowledge required from the user at any point.

---

## 8. Implementation Plan

### Phase 1: MVP (2-3 days)
- [ ] Single-server relay with WebSocket tunneling
- [ ] Tunnel client script for Docker
- [ ] Request forwarding (HTTP, no streaming)
- [ ] Basic auth (token-based)
- [ ] Health check endpoint

### Phase 2: Streaming + Production (2-3 days)
- [ ] SSE/streaming support over tunnel
- [ ] File upload/download proxying
- [ ] Auto-reconnect with exponential backoff
- [ ] Rate limiting
- [ ] TLS via Caddy
- [ ] Deploy to VPS

### Phase 3: Android Integration (1-2 days)
- [ ] Connection mode selector in Settings
- [ ] Auto-detect relay vs direct
- [ ] Offline detection
- [ ] QR code for direct connection setup

### Phase 4: Scale (when needed)
- [ ] Redis-backed connection mapping
- [ ] Load balancer
- [ ] Regional deployment
- [ ] Monitoring/alerting
