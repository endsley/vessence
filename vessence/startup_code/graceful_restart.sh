#!/bin/bash
# graceful_restart.sh — Zero-downtime restart for Jane Web Server
#
# Flow:
#   1. Determine which port the current server is on (8081 or 8083)
#   2. Start a NEW server on the alternate port
#   3. Wait for the new server's /health to return 200
#   4. Warm up the new CLI brain (POST /api/jane/warmup)
#   5. Tell the reverse proxy to switch upstream to the new port
#   6. Poll proxy active_requests until old requests drain (up to 60s)
#   7. Kill the old server
#
# Prerequisites:
#   - jane-proxy.service must be running (reverse_proxy.py on port 8080)
#   - jane-web.service must be running (uvicorn on port 8081 or 8083)
#
# Note: Port 8082 is reserved for the relay server. We use 8083 as the alternate.
#
# Usage:
#   bash startup_code/graceful_restart.sh

set -euo pipefail

PROXY_PORT=8080
PYTHON="/home/chieh/google-adk-env/adk-venv/bin/python"
VESSENCE_HOME="/home/chieh/ambient/vessence"
VESSENCE_DATA_HOME="/home/chieh/ambient/vessence-data"
VAULT_HOME="/home/chieh/ambient/vault"
ENV_FILE="$VESSENCE_DATA_HOME/.env"

HEALTH_TIMEOUT=30    # seconds to wait for new server health
DRAIN_TIMEOUT=60     # seconds to wait for old server to drain
WARMUP_TIMEOUT=60    # seconds to wait for CLI brain warmup

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# ── Step 1: Determine current and next port ──
log "Checking current upstream..."
CURRENT_PORT=$(curl -s http://localhost:$PROXY_PORT/proxy/status 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['upstream_port'])" 2>/dev/null || echo "8081")

if [ "$CURRENT_PORT" = "8081" ]; then
    NEXT_PORT=8083
else
    NEXT_PORT=8081
fi

log "Current server: port $CURRENT_PORT -> New server: port $NEXT_PORT"

# ── Step 2: Start the new server ──
log "Starting new server on port $NEXT_PORT..."

# Check if anything is already on the next port and kill it
OLD_PID=$(lsof -ti:$NEXT_PORT 2>/dev/null || true)
if [ -n "$OLD_PID" ]; then
    log "Killing stale process(es) on port $NEXT_PORT (PIDs: $OLD_PID)"
    kill $OLD_PID 2>/dev/null || true
    sleep 2
fi

# Source .env BEFORE starting the new server so it inherits all env vars
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
    log "Loaded environment from $ENV_FILE"
fi

# Start new server with same environment as the systemd service
AMBIENT_BASE="$HOME/ambient" \
VESSENCE_HOME="$VESSENCE_HOME" \
VESSENCE_DATA_HOME="$VESSENCE_DATA_HOME" \
VAULT_HOME="$VAULT_HOME" \
AMBIENT_HOME="$VESSENCE_DATA_HOME" \
PYTHONPATH="$VESSENCE_HOME" \
nohup "$PYTHON" -m uvicorn jane_web.main:app \
    --host 127.0.0.1 \
    --port "$NEXT_PORT" \
    --log-level info \
    > "$VESSENCE_DATA_HOME/logs/jane-web-$NEXT_PORT.log" 2>&1 &

NEW_PID=$!
log "New server PID: $NEW_PID"

# ── Step 3: Wait for health check ──
log "Waiting for new server health check..."
HEALTH_OK=false
for i in $(seq 1 $HEALTH_TIMEOUT); do
    if curl -sf "http://localhost:$NEXT_PORT/health" > /dev/null 2>&1; then
        HEALTH_OK=true
        break
    fi
    sleep 1
done

if [ "$HEALTH_OK" = false ]; then
    log "ERROR: New server failed to start within ${HEALTH_TIMEOUT}s. Aborting."
    kill "$NEW_PID" 2>/dev/null || true
    exit 1
fi

log "New server is healthy."

# ── Step 4: Warm up the CLI brain ──
log "Warming up CLI brain on new server..."

WARMUP_RESPONSE=$(curl -sf --max-time "$WARMUP_TIMEOUT" \
    -X POST "http://localhost:$NEXT_PORT/api/jane/warmup" \
    -H "Content-Type: application/json" \
    2>/dev/null || echo "warmup_endpoint_missing")

if [ "$WARMUP_RESPONSE" = "warmup_endpoint_missing" ]; then
    log "No warmup endpoint — waiting 10s for CLI brain startup..."
    sleep 10
else
    log "CLI brain warmup response: $WARMUP_RESPONSE"
fi

# ── Step 5: Switch the proxy upstream ──
log "Switching proxy upstream $CURRENT_PORT -> $NEXT_PORT..."

SWITCH_RESULT=$(curl -sf -X POST "http://localhost:$PROXY_PORT/proxy/switch" \
    -H "Content-Type: application/json" \
    -d "{\"port\": $NEXT_PORT}" 2>/dev/null)

if echo "$SWITCH_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['new_port']==$NEXT_PORT" 2>/dev/null; then
    log "Proxy switched to port $NEXT_PORT."
else
    log "ERROR: Proxy switch failed. Response: $SWITCH_RESULT"
    log "Keeping old server running. Kill new server manually (PID $NEW_PID)."
    exit 1
fi

# ── Step 6: Drain old server (poll active_requests) ──
log "Draining old server on port $CURRENT_PORT (up to ${DRAIN_TIMEOUT}s)..."
DRAIN_START=$(date +%s)
while true; do
    ELAPSED=$(( $(date +%s) - DRAIN_START ))
    if [ "$ELAPSED" -ge "$DRAIN_TIMEOUT" ]; then
        log "Drain timeout reached (${DRAIN_TIMEOUT}s). Proceeding with shutdown."
        break
    fi

    ACTIVE=$(curl -s "http://localhost:$PROXY_PORT/proxy/status" 2>/dev/null \
        | python3 -c "import sys,json; print(json.load(sys.stdin).get('active_requests',0))" 2>/dev/null || echo "0")

    if [ "$ACTIVE" = "0" ]; then
        log "All in-flight requests drained."
        break
    fi

    log "  $ACTIVE active request(s) remaining... waiting"
    sleep 2
done

# ── Step 7: Kill old server ──
OLD_SERVER_PID=$(lsof -ti:$CURRENT_PORT 2>/dev/null || true)
if [ -n "$OLD_SERVER_PID" ]; then
    log "Stopping old server (PIDs: $OLD_SERVER_PID)..."
    kill $OLD_SERVER_PID 2>/dev/null || true
    # Wait for graceful shutdown
    for i in $(seq 1 10); do
        REMAINING=$(lsof -ti:$CURRENT_PORT 2>/dev/null || true)
        if [ -z "$REMAINING" ]; then
            break
        fi
        sleep 1
    done
    # Force kill if still alive
    REMAINING=$(lsof -ti:$CURRENT_PORT 2>/dev/null || true)
    if [ -n "$REMAINING" ]; then
        log "Force-killing old server..."
        kill -9 $REMAINING 2>/dev/null || true
    fi
fi

log "=== Zero-downtime restart complete ==="
log "  Active server: port $NEXT_PORT (PID $NEW_PID)"
log "  Proxy: port $PROXY_PORT -> $NEXT_PORT"
log "  Old server: stopped"

# Verify final state
curl -sf "http://localhost:$PROXY_PORT/health" > /dev/null && log "Health check through proxy: OK" || log "WARNING: Health check through proxy failed"
