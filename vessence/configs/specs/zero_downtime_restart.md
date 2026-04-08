# Zero-Downtime Restart — Spec

## Problem

When `systemctl --user restart jane-web.service` runs:
1. The server process is killed immediately (SIGTERM)
2. The CLI brain (standing brain) dies with it — loses all conversation context
3. Users see errors or empty responses during the 5-15 second cold start gap
4. The new CLI needs a full first-turn context build (slow)

## Solution: Blue-Green Deploy via Reverse Proxy

### Architecture

```
Cloudflare Tunnel → Reverse Proxy (port 8080) → Active Server (8081 or 8083)
                                                  └── Standing Brain (CLI process)
```

**Port allocation:**
- 8080 — reverse proxy (stable endpoint, Cloudflare tunnel target)
- 8081 — primary uvicorn server
- 8082 — relay server (RESERVED, do not use for blue-green)
- 8083 — alternate uvicorn server (blue-green counterpart to 8081)

The reverse proxy (`reverse_proxy.py`) is a thin aiohttp server that forwards all HTTP/WebSocket traffic to whichever upstream port is currently active. It has a control API to swap upstreams at runtime.

### Cloudflare Dashboard Change

After deploying the proxy for the first time, update the Cloudflare Tunnel configuration:

1. Go to **Cloudflare Dashboard → Zero Trust → Access → Tunnels**
2. Select the `jane` tunnel → **Configure**
3. Change the service URL from `http://localhost:8081` to `http://localhost:8080`
4. Save

This is a one-time change. After this, the proxy is the stable entry point and the tunnel never needs to change again during deploys.

### Restart Flow

```
Step 1: Determine current port (e.g., 8081)
Step 2: Start NEW server on alternate port (8083)
Step 3: Wait for /health on new server → 200 OK
Step 4: Warm up new CLI brain:
        POST /api/jane/warmup on new server
        → Triggers standing brain initialization
        → Waits up to 30s for brain to be alive
        → Read-only: no ChromaDB writes during warmup
Step 5: Switch proxy upstream: POST /proxy/switch {"port": 8083}
        → All new requests go to 8083
        → In-flight requests on 8081 continue until they complete
Step 6: Poll proxy /proxy/status for active_requests == 0 (up to 60s)
        → Adaptive drain: exits early when all in-flight requests finish
Step 7: Send SIGTERM to old server (port 8081)
        → Old CLI dies gracefully
Step 8: Verify health through proxy
```

### Components

1. **Reverse Proxy** — `jane_web/reverse_proxy.py`
   - Listens on port 8080
   - Forwards all traffic to upstream (8081 or 8083)
   - Control API: `POST /proxy/switch`, `GET /proxy/status`
   - Handles HTTP, SSE streaming, and WebSocket
   - **State persistence**: saves current upstream port to `$VESSENCE_DATA_HOME/proxy_state.json` on every switch. On startup, restores the last-known upstream port so the proxy survives restarts without losing track of which server is active.

2. **jane-proxy.service** — systemd user service
   - Runs reverse_proxy.py permanently
   - Never restarts during deploys (it IS the stable endpoint)
   - Cloudflare tunnel points to port 8080 (proxy), not 8081 (server)

3. **Warmup endpoint** — `POST /api/jane/warmup`
   - Triggers standing brain initialization
   - Waits up to 30s for the brain process to become alive
   - **Read-only**: does not write to ChromaDB or any persistent store
   - Returns `{"status": "warm", "model": "..."}` when ready
   - Returns 202 if still starting, 500 on error

4. **graceful_restart.sh** — orchestration script
   - Runs steps 1-8 above
   - Replaces `systemctl restart jane-web` for all non-emergency restarts
   - Sources `.env` BEFORE starting new server (so it inherits all API keys)
   - Handles `lsof` returning multiple PIDs (unquoted `$OLD_PID` for kill)
   - Polls `active_requests` from proxy status instead of fixed sleep for drain

### What Changes

| Component | Before | After |
|---|---|---|
| Cloudflare tunnel target | `:8081` (direct to server) | `:8080` (reverse proxy) |
| jane-web.service | Serves traffic directly | Upstream behind proxy |
| jane-proxy.service | Does not exist | Runs reverse_proxy.py on :8080 |
| Restart command | `systemctl restart jane-web` | `bash graceful_restart.sh` |
| Alternate port | 8082 | 8083 (8082 is relay server) |
| Downtime during restart | 5-15 seconds | Zero |
| Context loss | Complete | Mitigated (brain warmed up) |
| Drain strategy | Fixed 15s sleep | Poll active_requests (up to 60s) |

### Warmup Details

The warmup endpoint (`POST /api/jane/warmup`) does:
1. Gets (or creates) the standing brain manager
2. Starts the brain process if not already started
3. Polls `manager.brain.alive` every 1s for up to 30s
4. Returns the brain's model name when alive

This is intentionally **read-only** — it does not query ChromaDB, SQLite, or any other store. It only ensures the CLI subprocess is spawned and responsive. The first real user message will trigger context loading as normal.

### Proxy State Persistence

The reverse proxy persists its current upstream port to `$VESSENCE_DATA_HOME/proxy_state.json` whenever a switch occurs. On startup, `create_app()` checks for this file and restores the saved port. This means:

- If `jane-proxy.service` restarts (crash, system reboot), it remembers which server was active
- No manual intervention needed to re-point the proxy after an unexpected restart
- The state file is a single JSON object: `{"upstream_port": 8081}`

### Failure Handling

- If new server fails health check → abort, keep old server running
- If proxy switch fails → abort, keep old server running
- If warmup times out → proceed anyway (CLI will cold-start on first real request)
- If old server won't die → SIGKILL after 10s
- If drain timeout (60s) reached → proceed with kill anyway

### Limitations

- WebSocket connections (SSE chat streams) on the old server will be dropped when it dies. This is unavoidable — active streams complete or timeout, they can't be migrated.
- The new CLI starts fresh — it doesn't inherit the old CLI's full conversation memory. The warmup only ensures the process is alive, not that it has context loaded.
