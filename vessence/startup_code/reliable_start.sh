#!/bin/bash
# reliable_start.sh - Enhanced background launcher
HOME_DIR="${HOME:-$(getent passwd "$(id -u)" | cut -d: -f6)}"
AMBIENT_BASE="${AMBIENT_BASE:-$HOME_DIR/ambient}"

DEFAULT_VESSENCE_HOME="$AMBIENT_BASE/vessence"
if [ ! -d "$DEFAULT_VESSENCE_HOME" ] && [ -d "/home/chieh/vessence" ]; then
    DEFAULT_VESSENCE_HOME="/home/chieh/vessence"
fi
VESSENCE_HOME="${VESSENCE_HOME:-$DEFAULT_VESSENCE_HOME}"

DEFAULT_VESSENCE_DATA_HOME="$AMBIENT_BASE/vessence-data"
if [ ! -d "$DEFAULT_VESSENCE_DATA_HOME" ] && [ -d "/home/chieh/vessence-data" ]; then
    DEFAULT_VESSENCE_DATA_HOME="/home/chieh/vessence-data"
fi
VESSENCE_DATA_HOME="${VESSENCE_DATA_HOME:-$DEFAULT_VESSENCE_DATA_HOME}"

DEFAULT_VAULT_HOME="$AMBIENT_BASE/vault"
if [ ! -d "$DEFAULT_VAULT_HOME" ] && [ -d "/home/chieh/vault" ]; then
    DEFAULT_VAULT_HOME="/home/chieh/vault"
fi
VAULT_HOME="${VAULT_HOME:-$DEFAULT_VAULT_HOME}"

export VESSENCE_HOME VESSENCE_DATA_HOME VAULT_HOME
export AMBIENT_HOME="${AMBIENT_HOME:-$VESSENCE_DATA_HOME}"
DEFAULT_VENV_BIN="$HOME_DIR/google-adk-env/adk-venv/bin"
if [ ! -x "$DEFAULT_VENV_BIN/python" ] && [ -x "/home/chieh/google-adk-env/adk-venv/bin/python" ]; then
    DEFAULT_VENV_BIN="/home/chieh/google-adk-env/adk-venv/bin"
fi
VENV_BIN="${VENV_BIN:-$DEFAULT_VENV_BIN}"
mkdir -p "$VESSENCE_DATA_HOME/logs/Amber_log" "$VESSENCE_DATA_HOME/logs/Jane_log"

echo "Cleaning up existing processes..."
pkill -9 -f "adk web|discord_bridge.py|bridge.py" || true
rm -f /tmp/amber_bridge.lock /tmp/jane_bridge.lock
sleep 2

# 1. Start Amber Brain
echo "Starting Amber Brain..."
cd "$VESSENCE_HOME"
nohup $VENV_BIN/adk web --port 8000 "$VESSENCE_HOME" > "$VESSENCE_DATA_HOME/logs/Amber_log/server.log" 2>&1 &

# Wait for Brain HTTP
for i in {1..30}; do
    if $VENV_BIN/python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/list-apps')" > /dev/null 2>&1; then
        echo "Brain HTTP is UP."
        break
    fi
    sleep 1
done

# Deep health check: verify amber agent actually loads (catches syntax errors, import failures)
echo "Verifying Amber agent loads cleanly..."
TEST_SESSION="healthcheck_$$"
$VENV_BIN/python -c "
import urllib.request, json
# Create session
req = urllib.request.Request('http://localhost:8000/apps/amber/users/healthcheck/sessions/$TEST_SESSION',
    data=b'{}', headers={'Content-Type': 'application/json'}, method='POST')
try:
    urllib.request.urlopen(req, timeout=10)
except Exception as e:
    print(f'Session create failed: {e}'); exit(1)
# Send test message
payload = json.dumps({'app_name':'amber','user_id':'healthcheck','session_id':'$TEST_SESSION',
    'new_message':{'parts':[{'text':'ping'}],'role':'user'}}).encode()
req2 = urllib.request.Request('http://localhost:8000/run',
    data=payload, headers={'Content-Type': 'application/json'}, method='POST')
try:
    resp = urllib.request.urlopen(req2, timeout=30)
    print('Agent health check PASSED.')
except Exception as e:
    print(f'Agent health check FAILED: {e}'); exit(1)
" 2>&1
if [ $? -ne 0 ]; then
    echo "ERROR: Amber agent failed health check. Check server.log. Bridges NOT started."
    exit 1
fi

# 2. Start Amber Bridge
echo "Starting Amber Bridge..."
cd "$VESSENCE_HOME"
nohup $VENV_BIN/python jane/discord_bridge.py > "$VESSENCE_DATA_HOME/logs/Amber_log/bridge.log" 2>&1 &

# 3. Start Jane Bridge
echo "Starting Jane Bridge..."
cd "$HOME_DIR/gemini_cli_bridge"
nohup $VENV_BIN/python bridge.py > "$VESSENCE_DATA_HOME/logs/Jane_log/bridge.log" 2>&1 &

echo "All bots initiated. Check logs for status."
