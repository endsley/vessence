#!/bin/bash
# graceful_restart.sh — Zero-downtime restart for Jane Web Server
#
# Design: Ping-pong between two ports (8081 and 8084).
#   1. Detect which port is currently active
#   2. Start a NEW server on the OTHER port
#   3. Wait for health + warm up the CLI brain
#   4. Switch the proxy (instant — zero user-facing downtime)
#   5. Kill the old server
#
# The user is NEVER offline. The proxy always points at a warm server.
# The switch itself is a single HTTP call — effectively instant.
#
# Port reservations:
#   8080 — reverse proxy (always running)
#   8081 — jane-web slot A
#   8082 — relay server (reserved)
#   8083 — memory daemon (reserved)
#   8084 — jane-web slot B
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

HEALTH_TIMEOUT=90    # seconds to wait for new server health
WARMUP_TIMEOUT=120   # seconds to wait for CLI brain warmup

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# ── Step 0: Create healthcheck lock to prevent interference ──
# The healthcheck runs every 2 minutes and checks port 8081 directly.
# During the ping-pong, 8081 may be vacant, causing the healthcheck to
# restart jane-web.service, killing our new nohup server. Lock it out.
LOCKFILE="/tmp/jane-web-restarting.lock"
touch "$LOCKFILE"
log "Created healthcheck lock (prevents restart collision during ping-pong)"

# ── Step 1: Detect current active port ──
log "Checking current upstream..."
CURRENT_PORT=$(curl -s http://localhost:$PROXY_PORT/proxy/status 2>/dev/null \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['upstream_port'])" 2>/dev/null \
    || echo "8081")

if [ "$CURRENT_PORT" = "8081" ]; then
    NEXT_PORT=8084
else
    NEXT_PORT=8081
fi

log "Active: port $CURRENT_PORT → Starting new server on port $NEXT_PORT"

# ── Step 2: Clear the target port ──
OLD_PID=$(lsof -ti:$NEXT_PORT 2>/dev/null || true)
if [ -n "$OLD_PID" ]; then
    log "Killing stale process on port $NEXT_PORT (PID: $OLD_PID)"
    kill -9 $OLD_PID 2>/dev/null || true
    sleep 1
fi

# ── Step 3: Load environment ──
if [ -f "$ENV_FILE" ]; then
    eval "$("$PYTHON" -c "
import sys
for line in open('$ENV_FILE'):
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    key, _, val = line.partition('=')
    key = key.strip()
    if key:
        val = val.replace(\"'\", \"'\\\"'\\\"'\")
        print(f\"export {key}='{val}'\")
")"
fi

# ── Step 3.5: Force fresh Python code ──
# Touch all .py files to update mtime (Claude Code edits preserve original
# timestamps, which tricks Python into using stale .pyc bytecache).
find "$VESSENCE_HOME" -name "*.py" -newer "$VESSENCE_HOME/startup_code/graceful_restart.sh" -exec touch {} + 2>/dev/null || true
find "$VESSENCE_HOME" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
log "Cleared Python bytecache and refreshed file timestamps."

# ── Step 4: Start new server ──
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

# ── Step 5: Wait for health ──
log "Waiting for new server to be healthy..."
HEALTH_OK=false
for i in $(seq 1 $HEALTH_TIMEOUT); do
    if curl -sf "http://localhost:$NEXT_PORT/health" > /dev/null 2>&1; then
        HEALTH_OK=true
        break
    fi
    sleep 1
done

if [ "$HEALTH_OK" = false ]; then
    log "ERROR: New server failed to start within ${HEALTH_TIMEOUT}s. Aborting — old server still active."
    kill "$NEW_PID" 2>/dev/null || true
    exit 1
fi

log "New server is healthy."

# ── Step 6: Warm up the CLI brain ──
log "Warming up CLI brain..."
WARMUP_RESPONSE=$(curl -sf --max-time "$WARMUP_TIMEOUT" \
    -X POST "http://localhost:$NEXT_PORT/api/jane/warmup" \
    -H "Content-Type: application/json" \
    2>/dev/null || echo "warmup_failed")

if [ "$WARMUP_RESPONSE" = "warmup_failed" ]; then
    log "WARNING: Brain warmup failed or timed out. Switching anyway."
else
    log "Brain warm: $WARMUP_RESPONSE"
fi

# ── Step 7: Switch proxy (instant — this is the zero-downtime moment) ──
log "Switching proxy: $CURRENT_PORT → $NEXT_PORT"
SWITCH_RESULT=$(curl -sf -X POST "http://localhost:$PROXY_PORT/proxy/switch" \
    -H "Content-Type: application/json" \
    -d "{\"port\": $NEXT_PORT}" 2>/dev/null)

if echo "$SWITCH_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['new_port']==$NEXT_PORT" 2>/dev/null; then
    log "Proxy switched to port $NEXT_PORT. New server is now live."
else
    log "ERROR: Proxy switch failed. Response: $SWITCH_RESULT"
    log "Old server on $CURRENT_PORT is still active. Kill new server manually (PID $NEW_PID)."
    exit 1
fi

# ── Step 8: Kill old server (grace period for in-flight requests) ──
log "Giving old server 5s grace period for in-flight requests..."
sleep 5

# Kill old server directly by PID — do NOT use `systemctl stop`.
# `systemctl stop` kills the entire service cgroup, which includes the NEW
# nohup server if it was spawned from a process in that cgroup (race condition
# observed: healthcheck restarted the service mid-ping-pong, killing new server).
# Killing by port PID is precise: only the old server dies.
OLD_SERVER_PID=$(lsof -ti:$CURRENT_PORT 2>/dev/null || true)
if [ -n "$OLD_SERVER_PID" ]; then
    log "Stopping old server on port $CURRENT_PORT (PID: $OLD_SERVER_PID)"
    # Exclude the NEW server PID in case lsof picks it up transiently
    for pid in $OLD_SERVER_PID; do
        if [ "$pid" != "$NEW_PID" ]; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    sleep 2
    # Force kill stragglers (again excluding new server)
    REMAINING=$(lsof -ti:$CURRENT_PORT 2>/dev/null || true)
    for pid in $REMAINING; do
        if [ "$pid" != "$NEW_PID" ]; then
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
fi

# Notify systemd that the service is no longer being managed (avoids surprise restarts).
# Use `kill --kill-who=main` (only main PID) instead of `stop` (whole cgroup).
if systemctl --user is-active jane-web.service >/dev/null 2>&1; then
    log "Disabling systemd jane-web.service restart supervision..."
    systemctl --user kill --kill-who=main --signal=SIGTERM jane-web.service 2>/dev/null || true
fi

# ── Done ──
log "=== Zero-downtime restart complete ==="
log "  Active server: port $NEXT_PORT (PID $NEW_PID)"
log "  Proxy: port $PROXY_PORT"
curl -sf "http://localhost:$PROXY_PORT/health" > /dev/null \
    && log "Health check: OK" \
    || log "WARNING: Health check failed"
