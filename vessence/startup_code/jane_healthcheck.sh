#!/bin/bash
# Comprehensive health check for Jane platform
# Called by systemd timer every 2 minutes.
# Checks all critical subsystems — not just "is the server alive."
# Alerts via Android notification when something is wrong.

PYTHON="/home/chieh/google-adk-env/adk-venv/bin/python"
VESSENCE_HOME="/home/chieh/ambient/vessence"
VESSENCE_DATA_HOME="/home/chieh/ambient/vessence-data"
LOG="$VESSENCE_DATA_HOME/logs/healthcheck.log"
LOCKFILE="/tmp/jane-web-restarting.lock"
COOLDOWN=180  # seconds between restart attempts

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }

# If a restart was recently triggered, skip restart (but still check)
RESTART_ALLOWED=true
if [ -f "$LOCKFILE" ]; then
    lock_age=$(( $(date +%s) - $(stat -c %Y "$LOCKFILE" 2>/dev/null || echo 0) ))
    if [ "$lock_age" -lt "$COOLDOWN" ]; then
        RESTART_ALLOWED=false
    else
        rm -f "$LOCKFILE"
    fi
fi

ISSUES=""

# ── Check 1: Jane web server responding ──
HTTP_CODE=$(curl -s --max-time 10 -o /dev/null -w "%{http_code}" "http://localhost:8081/health" 2>/dev/null)
if [ "$HTTP_CODE" != "200" ]; then
    ISSUES="${ISSUES}Jane web server is down (HTTP $HTTP_CODE). "
    if [ "$RESTART_ALLOWED" = true ]; then
        log "CRITICAL: Jane web server down — restarting"
        touch "$LOCKFILE"
        systemctl --user restart jane-web.service
    fi
fi

# ── Check 2: Reverse proxy ──
PROXY_CODE=$(curl -s --max-time 5 -o /dev/null -w "%{http_code}" "http://localhost:8080/health" 2>/dev/null)
if [ "$PROXY_CODE" != "200" ]; then
    ISSUES="${ISSUES}Reverse proxy is down. "
    log "WARNING: Reverse proxy not responding"
fi

# ── Check 3: Standing brain alive ──
BRAIN_ALIVE=$(curl -s --max-time 5 "http://localhost:8081/api/jane/current-provider" 2>/dev/null | "$PYTHON" -c "import sys,json; d=json.load(sys.stdin); print(d.get('alive',False))" 2>/dev/null || echo "False")
if [ "$BRAIN_ALIVE" != "True" ]; then
    ISSUES="${ISSUES}Standing brain is dead. "
    log "WARNING: Standing brain not alive"
fi

# ── Check 4: ChromaDB / memory ──
MEMORY_OK=$("$PYTHON" -c "
import sys; sys.path.insert(0, '$VESSENCE_HOME')
try:
    from jane.config import get_chroma_client, VECTOR_DB_USER_MEMORIES
    client = get_chroma_client(VECTOR_DB_USER_MEMORIES)
    cols = client.list_collections()
    print('ok' if len(cols) > 0 else 'empty')
except Exception as e:
    print(f'fail:{e}')
" 2>/dev/null)
if [ "$MEMORY_OK" = "ok" ]; then
    :  # good
elif [ "$MEMORY_OK" = "empty" ]; then
    ISSUES="${ISSUES}ChromaDB has no collections. "
    log "WARNING: ChromaDB empty"
else
    ISSUES="${ISSUES}ChromaDB unreachable: $MEMORY_OK. "
    log "WARNING: ChromaDB failed: $MEMORY_OK"
fi

# ── Check 5: Gemma router (Ollama) ──
OLLAMA_OK=$(curl -s --max-time 5 "http://localhost:11434/api/tags" 2>/dev/null | "$PYTHON" -c "import sys,json; d=json.load(sys.stdin); print('ok' if any('gemma' in m.get('name','') for m in d.get('models',[])) else 'no_gemma')" 2>/dev/null || echo "down")
if [ "$OLLAMA_OK" = "down" ]; then
    ISSUES="${ISSUES}Ollama is down (Gemma router unavailable). "
    log "WARNING: Ollama not responding"
elif [ "$OLLAMA_OK" = "no_gemma" ]; then
    ISSUES="${ISSUES}Gemma model not loaded in Ollama. "
    log "WARNING: Gemma model missing from Ollama"
fi

# ── Check 6: Gmail token valid ──
GMAIL_OK=$("$PYTHON" -c "
import os, json
token_path = os.path.join('$VESSENCE_DATA_HOME', 'credentials', 'gmail_token.json')
if not os.path.exists(token_path):
    print('missing')
else:
    d = json.load(open(token_path))
    print('ok' if d.get('access_token') else 'invalid')
" 2>/dev/null)
if [ "$GMAIL_OK" = "missing" ]; then
    ISSUES="${ISSUES}Gmail token missing (email won't work). "
    log "INFO: Gmail token not configured"
elif [ "$GMAIL_OK" = "invalid" ]; then
    ISSUES="${ISSUES}Gmail token invalid. "
    log "WARNING: Gmail token has no access_token"
fi

# ── Check 7: Memory daemon ──
MEM_DAEMON=$(curl -s --max-time 5 -o /dev/null -w "%{http_code}" "http://localhost:8083/health" 2>/dev/null)
if [ "$MEM_DAEMON" != "200" ]; then
    ISSUES="${ISSUES}Memory daemon is down. "
    log "WARNING: Memory daemon not responding"
fi

# ── Report ──
if [ -n "$ISSUES" ]; then
    log "ISSUES FOUND: $ISSUES"
    # Send alert to Android via announcements API
    "$PYTHON" -c "
import sys, json, urllib.request
data = json.dumps({
    'title': 'Health Check Alert',
    'message': '''$ISSUES''',
    'severity': 'warning'
}).encode()
try:
    req = urllib.request.Request('http://localhost:8081/api/jane/announce',
        data=data, headers={'Content-Type': 'application/json'}, method='POST')
    urllib.request.urlopen(req, timeout=5)
except: pass
" 2>/dev/null
else
    # All good — log periodically (every 10 runs ≈ 20 min)
    COUNTER_FILE="/tmp/jane-healthcheck-counter"
    COUNT=$(cat "$COUNTER_FILE" 2>/dev/null || echo 0)
    COUNT=$((COUNT + 1))
    echo "$COUNT" > "$COUNTER_FILE"
    if [ $((COUNT % 10)) -eq 0 ]; then
        log "ALL OK: server, proxy, brain, memory, gemma, gmail, memory-daemon"
    fi
fi

exit 0
