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
POST_SWITCH_WATCH_SECONDS=45

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# Return only real Jane uvicorn server PIDs.
#
# Do not use `pgrep -f "uvicorn jane_web.main:app"` here. That pattern also
# matches shell commands, monitors, editors, and traced invocations that merely
# contain the text. With `set -euo pipefail`, those false positives can abort
# the script when they do not own a listening socket.
jane_web_pids() {
    "$PYTHON" - <<'PY'
from pathlib import Path

for proc in Path("/proc").iterdir():
    if not proc.name.isdigit():
        continue
    try:
        raw = (proc / "cmdline").read_bytes()
    except OSError:
        continue
    if not raw:
        continue
    argv = [part.decode("utf-8", "ignore") for part in raw.split(b"\0") if part]
    for i in range(len(argv) - 2):
        if argv[i] == "-m" and argv[i + 1] == "uvicorn" and argv[i + 2] == "jane_web.main:app":
            print(proc.name)
            break
PY
}

port_for_pid() {
    local pid="$1"
    ss -Hltnp 2>/dev/null \
        | awk -v needle="pid=${pid}," '
            index($0, needle) {
                split($4, parts, ":")
                print parts[length(parts)]
                exit
            }
        '
}

# Return PID(s) that are LISTENING on the given TCP port, one per line.
# Fixes the subtle bug where `lsof -ti:$PORT` returned ALL processes with a
# socket involving the port — including the reverse proxy's OUTGOING
# connection to an upstream jane-web. That caused a previous graceful restart
# to accidentally kill the proxy along with the old jane-web. Using `ss -ltn`
# plus an exact-port grep restricts matches to listeners only.
listeners_on_port() {
    local port="$1"
    [ -z "$port" ] && return 0
    # -H: no header, -l: listen, -t: tcp, -n: numeric, -p: show pid=...
    # `|| true` prevents pipefail abort when grep finds no matches (empty
    # port is the common case on ping-pong startup).
    ss -Hltnp "sport = :$port" 2>/dev/null | { grep -oP 'pid=\K[0-9]+' || true; } | sort -u
}

rollback_to_systemd_8081() {
    log "Rolling back to systemd-managed port 8081..."
    systemctl --user start jane-web.service 2>/dev/null || systemctl --user restart jane-web.service
    for _ in $(seq 1 60); do
        if curl -sf "http://localhost:8081/health" > /dev/null 2>&1; then
            curl -sf -X POST "http://localhost:$PROXY_PORT/proxy/switch" \
                -H "Content-Type: application/json" \
                -d '{"port": 8081}' >/dev/null 2>&1 || true
            systemctl --user stop jane-web-pingpong-8084.service >/dev/null 2>&1 || true
            log "Rollback complete: proxy points at port 8081."
            return 0
        fi
        sleep 1
    done
    log "ERROR: Rollback failed; port 8081 did not become healthy."
    return 1
}

stop_systemd_8081_as_old_slot() {
    log "Stopping systemd jane-web.service cleanly..."
    systemctl --user stop jane-web.service 2>/dev/null || true

    # During ping-pong, port 8081 is the retired slot. Long-lived requests
    # can make systemd hit TimeoutStopSec and mark the stopped unit as
    # failed(Result=timeout), even though the proxy has already moved to the
    # new healthy upstream. Normalize that expected inactive state so later
    # diagnostics do not report a false service failure.
    systemctl --user reset-failed jane-web.service 2>/dev/null || true
    sleep 1
}

# ── Step 0: Create healthcheck lock to prevent interference ──
# The healthcheck runs every 2 minutes. During ping-pong, the proxy can briefly
# point at a port that is still settling; lock out auto-recovery until this
# script either finishes or exits through the cleanup trap.
LOCKFILE="/tmp/jane-web-restarting.lock"
touch "$LOCKFILE"
log "Created healthcheck lock (prevents restart collision during ping-pong)"
cleanup_lock() {
    rm -f "$LOCKFILE" 2>/dev/null || true
}
trap cleanup_lock EXIT

# ── Step 0.5: Sanity check — detect orphan uvicorn processes ──
# If any uvicorn jane_web process is running on a port other than
# 8081/8084, it's an orphan (e.g. someone manually nohup'd one). Kill
# it before proceeding so we don't end up with three concurrent servers.
ORPHAN_PIDS=$(jane_web_pids | while read -r pid; do
    port=$(port_for_pid "$pid")
    if [ -n "$port" ] && [ "$port" != "8081" ] && [ "$port" != "8084" ]; then
        echo "$pid"
    fi
done)
if [ -n "$ORPHAN_PIDS" ]; then
    log "WARN: Killing orphan uvicorn processes (not on 8081/8084): $ORPHAN_PIDS"
    for pid in $ORPHAN_PIDS; do kill -9 "$pid" 2>/dev/null || true; done
fi

# ── Step 0.6: Hard invariant — never proceed with >1 live jane-web process ──
# After a regression, it's possible to end up with TWO valid jane-web uvicorns
# (one on 8081, one on 8084) both claiming to be alive. If the proxy is only
# routing to one of them, the other is pure thread-leak. Reconcile before
# starting a third: keep whichever one the proxy currently points at; kill
# everything else that's holding 8081 or 8084.
CURRENT_UPSTREAM=$(curl -s http://localhost:$PROXY_PORT/proxy/status 2>/dev/null \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('upstream_port',''))" 2>/dev/null \
    || echo "")
ALL_PIDS=$(jane_web_pids | sort -u)
ALL_COUNT=$(echo "$ALL_PIDS" | grep -c . || true)
if [ "$ALL_COUNT" -gt 1 ]; then
    log "WARN: $ALL_COUNT jane-web uvicorns detected before restart (upstream=${CURRENT_UPSTREAM:-unknown}). Reconciling."
    for pid in $ALL_PIDS; do
        port=$(port_for_pid "$pid")
        if [ -z "$port" ]; then continue; fi
        if [ -n "$CURRENT_UPSTREAM" ] && [ "$port" = "$CURRENT_UPSTREAM" ]; then
            log "  keep PID $pid on port $port (current proxy upstream)"
        else
            log "  kill PID $pid on port $port (not the live upstream)"
            kill "$pid" 2>/dev/null || true
        fi
    done
    sleep 2
    # Force-kill anything still lingering that isn't the live upstream.
    for pid in $(jane_web_pids); do
        port=$(port_for_pid "$pid")
        if [ -n "$CURRENT_UPSTREAM" ] && [ "$port" = "$CURRENT_UPSTREAM" ]; then
            continue
        fi
        kill -9 "$pid" 2>/dev/null || true
    done
fi

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
# Listener-only — avoids killing the reverse proxy or any other process
# that merely has an established connection involving this port number.
OLD_PID=$(listeners_on_port "$NEXT_PORT")
if [ -n "$OLD_PID" ]; then
    log "Killing stale LISTENER on port $NEXT_PORT (PID: $OLD_PID)"
    for pid in $OLD_PID; do kill -9 "$pid" 2>/dev/null || true; done
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
if [ "$NEXT_PORT" = "8081" ]; then
    log "Starting systemd-managed jane-web.service on port 8081..."
    systemctl --user restart jane-web.service
    NEW_PID=""
    for i in $(seq 1 30); do
        NEW_PID=$(listeners_on_port "$NEXT_PORT" | head -1)
        [ -n "$NEW_PID" ] && break
        sleep 1
    done
    if [ -z "$NEW_PID" ]; then
        log "ERROR: systemd did not create a listener on port 8081."
        systemctl --user status jane-web.service --no-pager || true
        exit 1
    fi
else
    PINGPONG_UNIT="jane-web-pingpong-${NEXT_PORT}.service"
    log "Starting transient systemd unit $PINGPONG_UNIT on port $NEXT_PORT..."
    systemctl --user stop "$PINGPONG_UNIT" >/dev/null 2>&1 || true
    systemd-run --user \
        --unit="${PINGPONG_UNIT%.service}" \
        --collect \
        --property="WorkingDirectory=$VESSENCE_HOME" \
        /bin/bash -lc "exec env AMBIENT_BASE='$HOME/ambient' VESSENCE_HOME='$VESSENCE_HOME' VESSENCE_DATA_HOME='$VESSENCE_DATA_HOME' VAULT_HOME='$VAULT_HOME' AMBIENT_HOME='$VESSENCE_DATA_HOME' PYTHONPATH='$VESSENCE_HOME' '$PYTHON' -m uvicorn jane_web.main:app --host 127.0.0.1 --port '$NEXT_PORT' --log-level info >> '$VESSENCE_DATA_HOME/logs/jane-web-$NEXT_PORT.log' 2>&1" \
        >/dev/null

    NEW_PID=""
    for i in $(seq 1 30); do
        NEW_PID=$(listeners_on_port "$NEXT_PORT" | head -1)
        [ -n "$NEW_PID" ] && break
        sleep 1
    done
    if [ -z "$NEW_PID" ]; then
        log "ERROR: transient unit did not create a listener on port $NEXT_PORT."
        systemctl --user status "$PINGPONG_UNIT" --no-pager || true
        exit 1
    fi
fi
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
    if [ "$NEXT_PORT" = "8081" ]; then
        systemctl --user stop jane-web.service 2>/dev/null || true
    else
        systemctl --user stop "jane-web-pingpong-${NEXT_PORT}.service" 2>/dev/null || true
        kill "$NEW_PID" 2>/dev/null || true
    fi
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

# Stop the OLD server cleanly.
# Only stop systemd if the old server was on port 8081 (systemd's port).
# If the old server was on 8084 (previous nohup), kill by PID directly.
if [ "$CURRENT_PORT" = "8081" ] && systemctl --user is-active jane-web.service >/dev/null 2>&1; then
    stop_systemd_8081_as_old_slot
fi
if [ "$CURRENT_PORT" != "8081" ]; then
    systemctl --user stop "jane-web-pingpong-${CURRENT_PORT}.service" 2>/dev/null || true
fi

# Backup: kill anything still LISTENING on the old port (e.g. nohup orphan
# from a previous graceful_restart). MUST be listener-only — the reverse
# proxy on port 8080 has an active OUTGOING connection to whichever upstream
# was live, so `lsof -ti:$CURRENT_PORT` (used here historically) would have
# returned the proxy's PID too and killed it. `listeners_on_port` matches
# LISTEN sockets only.
OLD_SERVER_PID=$(listeners_on_port "$CURRENT_PORT")
if [ -n "$OLD_SERVER_PID" ]; then
    log "Cleaning up stragglers LISTENING on port $CURRENT_PORT (PID: $OLD_SERVER_PID)"
    for pid in $OLD_SERVER_PID; do
        if [ "$pid" != "$NEW_PID" ]; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    sleep 2
    REMAINING=$(listeners_on_port "$CURRENT_PORT")
    for pid in $REMAINING; do
        if [ "$pid" != "$NEW_PID" ]; then
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
fi

# (Old server was already stopped above via systemctl stop or listener cleanup.)

# ── Step 9: Verify the switched upstream survived cleanup ──
log "Verifying active upstream survived cleanup for ${POST_SWITCH_WATCH_SECONDS}s..."
for i in $(seq 1 "$POST_SWITCH_WATCH_SECONDS"); do
    if ! kill -0 "$NEW_PID" 2>/dev/null; then
        log "ERROR: New server PID $NEW_PID exited after proxy switch."
        if [ "$NEXT_PORT" = "8081" ]; then
            systemctl --user status jane-web.service --no-pager || true
        else
            tail -n 80 "$VESSENCE_DATA_HOME/logs/jane-web-$NEXT_PORT.log" || true
            rollback_to_systemd_8081 || true
        fi
        exit 1
    fi

    if ! curl -sf "http://localhost:$NEXT_PORT/health" > /dev/null 2>&1; then
        log "ERROR: Direct health check failed on active upstream port $NEXT_PORT during post-switch watch."
        if [ "$NEXT_PORT" != "8081" ]; then
            rollback_to_systemd_8081 || true
        fi
        exit 1
    fi

    if ! curl -sf "http://localhost:$PROXY_PORT/health" > /dev/null 2>&1; then
        log "ERROR: Proxy health check failed after switching to $NEXT_PORT during post-switch watch."
        if [ "$NEXT_PORT" != "8081" ]; then
            rollback_to_systemd_8081 || true
        fi
        exit 1
    fi

    sleep 1
done

# ── Done ──
log "=== Zero-downtime restart complete ==="
log "  Active server: port $NEXT_PORT (PID $NEW_PID)"
log "  Proxy: port $PROXY_PORT"
log "Health check: OK"
