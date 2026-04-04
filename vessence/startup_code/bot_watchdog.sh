#!/bin/bash
# bot_watchdog.sh - Checks if bots are alive and restarts services only after repeated failures.

set -u

# Ensure systemctl --user can connect when invoked from cron.
export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus"

HOME_DIR="${HOME:-$(getent passwd "$(id -u)" | cut -d: -f6)}"
AMBIENT_BASE="${AMBIENT_BASE:-$HOME_DIR/ambient}"

VESSENCE_HOME="${VESSENCE_HOME:-$AMBIENT_BASE/vessence}"
VESSENCE_DATA_HOME="${VESSENCE_DATA_HOME:-$AMBIENT_BASE/vessence-data}"
VAULT_HOME="${VAULT_HOME:-$AMBIENT_BASE/vault}"

export VESSENCE_HOME VESSENCE_DATA_HOME VAULT_HOME
export AMBIENT_HOME="${AMBIENT_HOME:-$VESSENCE_DATA_HOME}"

VENV_BIN="${VENV_BIN:-$HOME_DIR/google-adk-env/adk-venv/bin}"

LOG_DIR="$VESSENCE_DATA_HOME/logs/System_log"
STATE_DIR="$VESSENCE_DATA_HOME/state/watchdog"
LOG_PATH="$LOG_DIR/watchdog.log"
mkdir -p "$LOG_DIR" "$STATE_DIR"

BRAIN_URL="${WATCHDOG_BRAIN_URL:-http://localhost:8000/list-apps}"
PROBE_RETRIES="${WATCHDOG_PROBE_RETRIES:-3}"
PROBE_DELAY_SECS="${WATCHDOG_PROBE_DELAY_SECS:-2}"
BRAIN_FAILURE_THRESHOLD="${WATCHDOG_BRAIN_FAILURE_THRESHOLD:-2}"
BRIDGE_FAILURE_THRESHOLD="${WATCHDOG_BRIDGE_FAILURE_THRESHOLD:-2}"
RESTART_COOLDOWN_SECS="${WATCHDOG_RESTART_COOLDOWN_SECS:-900}"

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "$LOG_PATH"
}

state_path() {
    printf '%s/%s.%s' "$STATE_DIR" "$1" "$2"
}

read_state() {
    local key="$1"
    local suffix="$2"
    local path
    path="$(state_path "$key" "$suffix")"
    if [ -f "$path" ]; then
        cat "$path"
    else
        printf '0'
    fi
}

write_state() {
    local key="$1"
    local suffix="$2"
    local value="$3"
    printf '%s' "$value" > "$(state_path "$key" "$suffix")"
}

reset_failure_state() {
    local key="$1"
    write_state "$key" failures 0
}

record_failure() {
    local key="$1"
    local current
    current="$(read_state "$key" failures)"
    current=$((current + 1))
    write_state "$key" failures "$current"
    printf '%s' "$current"
}

restart_with_cooldown() {
    local key="$1"
    local service="$2"
    local reason="$3"
    local threshold="$4"
    local failures
    failures="$(record_failure "$key")"

    if [ "$failures" -lt "$threshold" ]; then
        log "$reason Failure ${failures}/${threshold}; holding restart until threshold is met."
        return
    fi

    local now
    now="$(date +%s)"
    local last_restart
    last_restart="$(read_state "$key" last_restart)"
    local elapsed=$((now - last_restart))
    if [ "$last_restart" -gt 0 ] && [ "$elapsed" -lt "$RESTART_COOLDOWN_SECS" ]; then
        log "$reason Restart suppressed for ${service}; cooldown ${RESTART_COOLDOWN_SECS}s, ${elapsed}s elapsed."
        return
    fi

    log "$reason Restarting ${service} after ${failures} consecutive failures."
    if systemctl --user restart "$service"; then
        write_state "$key" last_restart "$now"
        reset_failure_state "$key"
    else
        log "Restart failed for ${service}."
    fi
}

check_brain() {
    local attempt=1
    while [ "$attempt" -le "$PROBE_RETRIES" ]; do
        if "$VENV_BIN/python" -c "import urllib.request; urllib.request.urlopen('$BRAIN_URL', timeout=5)" > /dev/null 2>&1; then
            reset_failure_state brain
            return 0
        fi

        if [ "$attempt" -lt "$PROBE_RETRIES" ]; then
            sleep "$PROBE_DELAY_SECS"
        fi
        attempt=$((attempt + 1))
    done

    restart_with_cooldown brain amber-brain.service "Amber Brain probe failed after ${PROBE_RETRIES} attempts." "$BRAIN_FAILURE_THRESHOLD"
    return 1
}

check_bridge_service() {
    local key="$1"
    local service="$2"
    local threshold="$3"

    if systemctl --user is-active --quiet "$service"; then
        reset_failure_state "$key"
        return 0
    fi

    restart_with_cooldown "$key" "$service" "${service} is not active." "$threshold"
    return 1
}

check_jane_web() {
    local port=8081
    local pids
    pids=$(pgrep -f "uvicorn.*${port}" 2>/dev/null)
    local count
    count=$(echo "$pids" | grep -c '[0-9]' 2>/dev/null || echo 0)

    # Kill duplicates — keep only the oldest process
    if [ "$count" -gt 1 ]; then
        local oldest
        oldest=$(echo "$pids" | head -1)
        for pid in $pids; do
            if [ "$pid" != "$oldest" ]; then
                log "Jane Web: killing duplicate process $pid (keeping $oldest)"
                kill "$pid" 2>/dev/null
            fi
        done
        reset_failure_state jane_web
        return 0
    fi

    # Check if running and healthy
    if [ "$count" -eq 1 ]; then
        if "$VENV_BIN/python" -c "import urllib.request; urllib.request.urlopen('http://localhost:${port}/health', timeout=5)" > /dev/null 2>&1; then
            reset_failure_state jane_web
            return 0
        fi
    fi

    # Not running or unhealthy — start it
    local now
    now="$(date +%s)"
    local last_restart
    last_restart="$(read_state jane_web last_restart)"
    local elapsed=$((now - last_restart))
    if [ "$last_restart" -gt 0 ] && [ "$elapsed" -lt "$RESTART_COOLDOWN_SECS" ]; then
        log "Jane Web: restart suppressed; cooldown ${RESTART_COOLDOWN_SECS}s, ${elapsed}s elapsed."
        return 1
    fi

    log "Jane Web: starting on port ${port}"
    cd "$VESSENCE_HOME/jane_web" && \
        PYTHONPATH="$VESSENCE_HOME" nohup "$VENV_BIN/python" -m uvicorn main:app \
        --host 127.0.0.1 --port "$port" --log-level info \
        >> "$VESSENCE_DATA_HOME/logs/jane_web.log" 2>&1 &
    write_state jane_web last_restart "$now"
    reset_failure_state jane_web
}

check_relay() {
    local port=8082
    local pids
    pids=$(pgrep -f "uvicorn.*${port}" 2>/dev/null)
    local count
    count=$(echo "$pids" | grep -c '[0-9]' 2>/dev/null || echo 0)

    # Kill duplicates — keep only the oldest process
    if [ "$count" -gt 1 ]; then
        local oldest
        oldest=$(echo "$pids" | head -1)
        for pid in $pids; do
            if [ "$pid" != "$oldest" ]; then
                log "Relay: killing duplicate process $pid (keeping $oldest)"
                kill "$pid" 2>/dev/null
            fi
        done
        reset_failure_state relay
        return 0
    fi

    # Check if running and healthy
    if [ "$count" -eq 1 ]; then
        if "$VENV_BIN/python" -c "import urllib.request; urllib.request.urlopen('http://localhost:${port}/health', timeout=5)" > /dev/null 2>&1; then
            reset_failure_state relay
            return 0
        fi
    fi

    # Not running or unhealthy — restart via systemd
    restart_with_cooldown relay vessence-relay.service "Relay server probe failed." 2
    return 1
}

check_memory_daemon() {
    local port=8083
    if "$VENV_BIN/python" -c "import urllib.request; urllib.request.urlopen('http://localhost:${port}/health', timeout=5)" > /dev/null 2>&1; then
        reset_failure_state memory_daemon
        return 0
    fi

    restart_with_cooldown memory_daemon memory-daemon.service "Memory daemon probe failed on port ${port}." 2
    return 1
}

check_brain
check_bridge_service amber_bridge amber-bridge.service "$BRIDGE_FAILURE_THRESHOLD"
check_bridge_service jane_bridge jane-bridge.service "$BRIDGE_FAILURE_THRESHOLD"
check_jane_web
check_relay
check_memory_daemon
