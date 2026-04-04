#!/usr/bin/env bash
# ===========================================================================
# deploy.sh — Zero-downtime deployment for Jane Web
#
# How it works:
#   1. Starts a NEW uvicorn instance on an alternate port (blue-green)
#   2. Waits for the new instance's /health endpoint to return 200
#   3. Tells the reverse proxy to switch upstream to the new port
#   4. Gracefully shuts down the OLD uvicorn instance
#   5. Rolls back if any step fails
#
# Prerequisites:
#   - jane-proxy.service must be running (reverse proxy on port 8080)
#   - jane-web.service should be running (uvicorn on current port)
#
# Usage:
#   ./deploy.sh                    # auto-detect ports, deploy
#   ./deploy.sh --new-port 8082    # explicitly set the new port
#   ./deploy.sh --dry-run          # show what would happen, don't execute
#
# ===========================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROXY_PORT="${PROXY_PORT:-8080}"
PROXY_CONTROL="http://127.0.0.1:${PROXY_PORT}/proxy"
PYTHON="${PYTHON:-/home/chieh/google-adk-env/adk-venv/bin/python}"
VESSENCE_HOME="${VESSENCE_HOME:-/home/chieh/ambient/vessence}"
VESSENCE_DATA_HOME="${VESSENCE_DATA_HOME:-/home/chieh/ambient/vessence-data}"
AMBIENT_BASE="${AMBIENT_BASE:-/home/chieh/ambient}"
VAULT_HOME="${VAULT_HOME:-/home/chieh/ambient/vault}"
LOG_DIR="${VESSENCE_DATA_HOME}/logs"
DEPLOY_LOG="${LOG_DIR}/deploy.log"
HEALTH_TIMEOUT=30       # seconds to wait for /health to return 200
SHUTDOWN_GRACE=10       # seconds to wait after SIGTERM before SIGKILL
ENV_FILE="${VESSENCE_DATA_HOME}/.env"

# Port pair for blue-green
PORT_A=8081
PORT_B=8082

# CLI args
NEW_PORT=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --new-port)  NEW_PORT="$2"; shift 2 ;;
        --dry-run)   DRY_RUN=true; shift ;;
        *)           echo "Unknown arg: $1"; exit 1 ;;
    esac
done

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
mkdir -p "$LOG_DIR"

log() {
    local msg
    msg="$(date '+%Y-%m-%d %H:%M:%S') [deploy] $*"
    echo "$msg" | tee -a "$DEPLOY_LOG"
}

die() {
    log "FATAL: $*"
    exit 1
}

# ---------------------------------------------------------------------------
# Detect current upstream from the proxy
# ---------------------------------------------------------------------------
get_current_port() {
    local resp
    resp=$(curl -sf "${PROXY_CONTROL}/status" 2>/dev/null) || {
        log "WARNING: Could not reach proxy at ${PROXY_CONTROL}/status"
        echo ""
        return
    }
    echo "$resp" | "$PYTHON" -c "import sys,json; print(json.load(sys.stdin)['upstream_port'])" 2>/dev/null
}

# ---------------------------------------------------------------------------
# Determine which port to deploy to
# ---------------------------------------------------------------------------
CURRENT_PORT=$(get_current_port)
if [[ -n "$NEW_PORT" ]]; then
    TARGET_PORT="$NEW_PORT"
elif [[ "$CURRENT_PORT" == "$PORT_A" ]]; then
    TARGET_PORT="$PORT_B"
elif [[ "$CURRENT_PORT" == "$PORT_B" ]]; then
    TARGET_PORT="$PORT_A"
else
    # No proxy running or unknown port — default to PORT_A
    TARGET_PORT="$PORT_A"
fi

log "Current upstream port: ${CURRENT_PORT:-unknown}"
log "Target port for new instance: $TARGET_PORT"

if [[ "$DRY_RUN" == "true" ]]; then
    log "[DRY RUN] Would start uvicorn on port $TARGET_PORT"
    log "[DRY RUN] Would health-check http://127.0.0.1:${TARGET_PORT}/health"
    log "[DRY RUN] Would switch proxy upstream to port $TARGET_PORT"
    log "[DRY RUN] Would stop old uvicorn on port ${CURRENT_PORT:-unknown}"
    exit 0
fi

# ---------------------------------------------------------------------------
# Step 1: Start new uvicorn instance
# ---------------------------------------------------------------------------
log "Step 1: Starting new uvicorn on port $TARGET_PORT"

# Check if something is already on TARGET_PORT
if curl -sf "http://127.0.0.1:${TARGET_PORT}/health" >/dev/null 2>&1; then
    log "WARNING: Port $TARGET_PORT already has a healthy server — reusing it"
else
    # Build environment for uvicorn
    ENV_ARGS=()
    ENV_ARGS+=("AMBIENT_BASE=$AMBIENT_BASE")
    ENV_ARGS+=("VESSENCE_HOME=$VESSENCE_HOME")
    ENV_ARGS+=("VESSENCE_DATA_HOME=$VESSENCE_DATA_HOME")
    ENV_ARGS+=("VAULT_HOME=$VAULT_HOME")
    ENV_ARGS+=("AMBIENT_HOME=$VESSENCE_DATA_HOME")
    ENV_ARGS+=("PYTHONPATH=$VESSENCE_HOME")

    # Source the .env file to pass all environment variables
    if [[ -f "$ENV_FILE" ]]; then
        set -a
        # shellcheck source=/dev/null
        source "$ENV_FILE"
        set +a
    fi

    cd "$VESSENCE_HOME/jane_web"
    env "${ENV_ARGS[@]}" "$PYTHON" -m uvicorn main:app \
        --host 127.0.0.1 \
        --port "$TARGET_PORT" \
        --log-level info \
        >> "${LOG_DIR}/jane_web_${TARGET_PORT}.log" 2>&1 &
    NEW_PID=$!
    log "Started uvicorn PID=$NEW_PID on port $TARGET_PORT"
fi

# ---------------------------------------------------------------------------
# Step 2: Wait for /health to return 200
# ---------------------------------------------------------------------------
log "Step 2: Waiting for health check on port $TARGET_PORT (timeout: ${HEALTH_TIMEOUT}s)"

elapsed=0
while [[ $elapsed -lt $HEALTH_TIMEOUT ]]; do
    if curl -sf "http://127.0.0.1:${TARGET_PORT}/health" >/dev/null 2>&1; then
        log "Health check passed after ${elapsed}s"
        break
    fi
    sleep 1
    elapsed=$((elapsed + 1))
done

if [[ $elapsed -ge $HEALTH_TIMEOUT ]]; then
    log "ROLLBACK: Health check failed after ${HEALTH_TIMEOUT}s"
    if [[ -n "${NEW_PID:-}" ]]; then
        log "Killing new instance PID=$NEW_PID"
        kill "$NEW_PID" 2>/dev/null || true
        wait "$NEW_PID" 2>/dev/null || true
    fi
    die "Deployment aborted — new server did not become healthy"
fi

# ---------------------------------------------------------------------------
# Step 3: Switch the proxy upstream
# ---------------------------------------------------------------------------
log "Step 3: Switching proxy upstream to port $TARGET_PORT"

SWITCH_RESP=$(curl -sf -X POST "${PROXY_CONTROL}/switch" \
    -H "Content-Type: application/json" \
    -d "{\"port\": $TARGET_PORT}" 2>&1) || {
    log "ROLLBACK: Failed to switch proxy upstream"
    if [[ -n "${NEW_PID:-}" ]]; then
        log "Killing new instance PID=$NEW_PID"
        kill "$NEW_PID" 2>/dev/null || true
    fi
    die "Proxy switch failed: $SWITCH_RESP"
}

log "Proxy switch response: $SWITCH_RESP"

# Verify the switch worked by checking proxy health
sleep 1
if ! curl -sf "http://127.0.0.1:${PROXY_PORT}/health" >/dev/null 2>&1; then
    log "WARNING: Proxy health check through new upstream returned non-200 (may be okay if /health is not at proxy root)"
fi

# ---------------------------------------------------------------------------
# Step 4: Gracefully stop the old server
# ---------------------------------------------------------------------------
if [[ -n "$CURRENT_PORT" && "$CURRENT_PORT" != "$TARGET_PORT" ]]; then
    log "Step 4: Stopping old uvicorn on port $CURRENT_PORT"

    OLD_PIDS=$(pgrep -f "uvicorn.*--port ${CURRENT_PORT}" 2>/dev/null || true)
    if [[ -n "$OLD_PIDS" ]]; then
        for pid in $OLD_PIDS; do
            log "Sending SIGTERM to PID=$pid"
            kill -TERM "$pid" 2>/dev/null || true
        done

        # Wait for graceful shutdown
        WAITED=0
        while [[ $WAITED -lt $SHUTDOWN_GRACE ]]; do
            REMAINING=$(pgrep -f "uvicorn.*--port ${CURRENT_PORT}" 2>/dev/null || true)
            if [[ -z "$REMAINING" ]]; then
                log "Old server shut down gracefully after ${WAITED}s"
                break
            fi
            sleep 1
            WAITED=$((WAITED + 1))
        done

        # Force kill if still running
        REMAINING=$(pgrep -f "uvicorn.*--port ${CURRENT_PORT}" 2>/dev/null || true)
        if [[ -n "$REMAINING" ]]; then
            log "Force-killing remaining old processes: $REMAINING"
            for pid in $REMAINING; do
                kill -9 "$pid" 2>/dev/null || true
            done
        fi
    else
        log "No old uvicorn process found on port $CURRENT_PORT"
    fi
else
    log "Step 4: Skipped — no old server to stop (first deploy or same port)"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
log "Deployment complete: traffic now routed to port $TARGET_PORT"
log "=========================================="
