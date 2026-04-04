#!/bin/bash
# Health check for jane-web.service
# Called by systemd timer every 2 minutes.
# If the server doesn't respond within 10s, restart it.
# Uses a lock file to prevent cascading restarts.

ENDPOINT="http://localhost:8081/api/app/latest-version"
TIMEOUT=10
LOG="/home/chieh/ambient/vessence-data/logs/healthcheck.log"
LOCKFILE="/tmp/jane-web-restarting.lock"
COOLDOWN=180  # seconds to wait after a restart before allowing another

# If a restart was recently triggered, skip this check
if [ -f "$LOCKFILE" ]; then
    lock_age=$(( $(date +%s) - $(stat -c %Y "$LOCKFILE" 2>/dev/null || echo 0) ))
    if [ "$lock_age" -lt "$COOLDOWN" ]; then
        exit 0
    fi
    rm -f "$LOCKFILE"
fi

response=$(curl -s --max-time "$TIMEOUT" -o /dev/null -w "%{http_code}" "$ENDPOINT" 2>/dev/null)

if [ "$response" = "200" ]; then
    exit 0
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') UNHEALTHY: endpoint returned '$response' — restarting jane-web.service" >> "$LOG"
    touch "$LOCKFILE"
    systemctl --user restart jane-web.service
    echo "$(date '+%Y-%m-%d %H:%M:%S') Restart triggered" >> "$LOG"
    exit 1
fi
