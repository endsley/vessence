#!/bin/bash
set -e

# ═══════════════════════════════════════════════════════════════════════════════
# Vessence Setup Script — Complete Installer
# ═══════════════════════════════════════════════════════════════════════════════
#
# One-command installer for Jane AI. Handles everything:
#   - Prerequisite checks (Python, Git)
#   - Python venv + dependency install
#   - Data directory creation + memory seeding
#   - .env configuration (name, brain, API keys)
#   - Agent config linking
#   - Test server run
#   - Auto-start service registration
#   - Remote access setup (optional)
#   - Get-to-know-you questions (optional)
#
# Run from the repo root (~/ambient):
#   bash vessence/setup.sh
#
# Safe to re-run — idempotent by design.
# ═══════════════════════════════════════════════════════════════════════════════

# ── Colors ───────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

ok()   { echo -e "  ${GREEN}[OK]${NC} $1"; }
fail() { echo -e "  ${RED}[FAIL]${NC} $1"; }
warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; }
info() { echo -e "  ${CYAN}-->${NC} $1"; }
header() { echo -e "\n${BOLD}=== $1 ===${NC}"; }

# ── Repo root check ─────────────────────────────────────────────────────────

if [ ! -d "vessence" ] || [ ! -f "vessence/requirements.txt" ]; then
    fail "This script must be run from the Vessence repo root (e.g. ~/ambient)."
    echo ""
    echo "  Expected layout:"
    echo "    ~/ambient/"
    echo "      vessence/          <-- the code repo"
    echo "      vessence-data/     <-- created by this script"
    echo ""
    echo "  Run:  cd ~/ambient && bash vessence/setup.sh"
    exit 1
fi

REPO_ROOT="$(pwd)"
echo -e "${BOLD}Vessence Setup${NC} - running from ${REPO_ROOT}"

# ═════════════════════════════════════════════════════════════════════════════
# Phase 1 — Check Prerequisites
# ═════════════════════════════════════════════════════════════════════════════

header "Phase 1: Checking prerequisites"

# -- Python --
PYTHON_CMD=""
for cmd in python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON_CMD="$cmd"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    fail "Python 3 not found."
    echo ""
    echo "  Install Python 3.11 or 3.12:"
    echo "    Ubuntu/Debian:  sudo apt update && sudo apt install -y python3.12 python3.12-venv python3.12-dev"
    echo "    Fedora/RHEL:    sudo dnf install -y python3.12"
    echo "    macOS:          brew install python@3.12"
    echo "    Windows:        Use WSL2 (wsl --install), then install inside WSL."
    exit 1
fi

PY_VERSION=$($PYTHON_CMD --version 2>&1 | grep -oP '\d+\.\d+')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    fail "Python $PY_VERSION found, but 3.11+ is required."
    echo ""
    echo "  Install Python 3.11 or 3.12:"
    echo "    Ubuntu/Debian:  sudo apt update && sudo apt install -y python3.12 python3.12-venv python3.12-dev"
    echo "    Fedora/RHEL:    sudo dnf install -y python3.12"
    echo "    macOS:          brew install python@3.12"
    exit 1
fi

ok "Python: $($PYTHON_CMD --version 2>&1)"

if [ "$PY_MINOR" -ge 13 ]; then
    warn "Python 3.13+ detected. This usually works, but 3.11/3.12 is the sweet spot."
fi

# -- Git --
if command -v git &>/dev/null; then
    ok "Git: $(git --version)"
else
    fail "Git not found."
    echo ""
    echo "  Install git:"
    echo "    Ubuntu/Debian:  sudo apt install -y git"
    echo "    Fedora/RHEL:    sudo dnf install -y git"
    echo "    macOS:          brew install git"
    exit 1
fi

# ═════════════════════════════════════════════════════════════════════════════
# Phase 2 — Python Virtual Environment + Dependencies
# ═════════════════════════════════════════════════════════════════════════════

header "Phase 2: Python environment + dependencies"

if [ -d "./venv" ] && [ -f "./venv/bin/python" ]; then
    info "Virtual environment already exists at ./venv"
else
    info "Creating virtual environment..."
    $PYTHON_CMD -m venv ./venv
    ok "Virtual environment created"
fi

info "Upgrading pip..."
./venv/bin/pip install --upgrade pip --quiet

info "Installing dependencies from vessence/requirements.txt..."
info "(This may take 1-3 minutes on first run)"
./venv/bin/pip install -r vessence/requirements.txt --quiet

# Verify key imports
if ./venv/bin/python -c "import chromadb, fastapi, uvicorn; print('OK')" 2>/dev/null | grep -q "OK"; then
    ok "Core packages verified (chromadb, fastapi, uvicorn)"
else
    fail "Package verification failed. Check the pip install output above for errors."
    exit 1
fi

# ═════════════════════════════════════════════════════════════════════════════
# Phase 3 — Create Data Directories
# ═════════════════════════════════════════════════════════════════════════════

header "Phase 3: Creating data directories"

mkdir -p vessence-data/memory/v1/vector_db
mkdir -p vessence-data/logs
mkdir -p vessence-data/credentials
mkdir -p vault/documents
mkdir -p essences
mkdir -p skills
touch essences/.gitkeep skills/.gitkeep

ok "Data directories created:"
info "  vessence-data/memory/v1/vector_db/"
info "  vessence-data/logs/"
info "  vessence-data/credentials/"
info "  vault/documents/"
info "  essences/"
info "  skills/"

# ═════════════════════════════════════════════════════════════════════════════
# Phase 4 — Seed Jane's Memory
# ═════════════════════════════════════════════════════════════════════════════

header "Phase 4: Seeding Jane's memory"

if [ -f "vessence-data/memory/v1/vector_db/long_term_memory/chroma.sqlite3" ]; then
    warn "Memory database already exists -- skipping seed (won't overwrite your data)"
else
    if [ -d "vessence/seed_db" ]; then
        cp -r vessence/seed_db/* vessence-data/memory/v1/vector_db/
        if [ -f "vessence-data/memory/v1/vector_db/long_term_memory/chroma.sqlite3" ]; then
            ok "Memory seeded successfully"
        else
            # The seed_db might have a different structure; copy what we have
            warn "Seed copied, but chroma.sqlite3 not found at expected path. Check vessence/seed_db layout."
        fi
    else
        fail "vessence/seed_db/ not found. Cannot seed memory."
        exit 1
    fi
fi

# ═════════════════════════════════════════════════════════════════════════════
# Phase 5 — Copy .env Template + Generate Session Secret
# ═════════════════════════════════════════════════════════════════════════════

header "Phase 5: Environment configuration file"

if [ -f "vessence-data/.env" ]; then
    warn ".env already exists at vessence-data/.env -- not overwriting"
    info "To reset, delete it and re-run this script."
else
    if [ -f "vessence/.env.example" ]; then
        cp vessence/.env.example vessence-data/.env
        ok "Copied .env.example -> vessence-data/.env"
    else
        fail "vessence/.env.example not found. Cannot create config."
        exit 1
    fi
fi

# Auto-generate SESSION_SECRET_KEY if it's still the placeholder
if grep -q "SESSION_SECRET_KEY=changeme-generate-a-real-secret" "vessence-data/.env" 2>/dev/null; then
    ./venv/bin/python -c "
import secrets, re, pathlib
env = pathlib.Path('vessence-data/.env')
text = env.read_text()
secret = secrets.token_hex(32)
text = re.sub(r'^SESSION_SECRET_KEY=.*', f'SESSION_SECRET_KEY={secret}', text, flags=re.M)
env.write_text(text)
print('done')
" >/dev/null
    ok "Session secret key generated"
elif grep -q "SESSION_SECRET_KEY=" "vessence-data/.env" 2>/dev/null; then
    info "Session secret key already set"
fi

# ═════════════════════════════════════════════════════════════════════════════
# Phase 6 — Configure Jane (Interactive)
# ═════════════════════════════════════════════════════════════════════════════

header "Phase 6: Configure Jane"

# Helper to set a value in the .env file
set_env() {
    local key="$1" value="$2"
    if grep -q "^${key}=" "vessence-data/.env" 2>/dev/null; then
        sed -i "s|^${key}=.*|${key}=${value}|" "vessence-data/.env"
    else
        echo "${key}=${value}" >> "vessence-data/.env"
    fi
}

# -- Your name --
EXISTING_NAME=$(grep -oP '^USER_NAME=\K.+' "vessence-data/.env" 2>/dev/null || true)
if [ -n "$EXISTING_NAME" ]; then
    info "Name already set: $EXISTING_NAME"
    echo -n "  Keep this name? (y/n) [y]: "
    read -r KEEP_NAME
    if [ "$KEEP_NAME" = "n" ] || [ "$KEEP_NAME" = "N" ]; then
        echo -n "  What's your name? "
        read -r USER_NAME
        set_env "USER_NAME" "$USER_NAME"
        ok "Name set to: $USER_NAME"
    else
        USER_NAME="$EXISTING_NAME"
        ok "Keeping name: $USER_NAME"
    fi
else
    echo -n "  What's your name? Jane will use this to address you: "
    read -r USER_NAME
    if [ -z "$USER_NAME" ]; then
        USER_NAME="Friend"
        warn "No name entered -- using 'Friend'"
    fi
    set_env "USER_NAME" "$USER_NAME"
    ok "Name set to: $USER_NAME"
fi

# -- Detect AI brain --
echo ""
info "Checking which AI CLIs are installed..."

BRAINS_FOUND=()
if command -v claude &>/dev/null; then
    ok "Claude Code found: $(which claude)"
    BRAINS_FOUND+=("claude")
fi
if command -v gemini &>/dev/null; then
    ok "Gemini CLI found: $(which gemini)"
    BRAINS_FOUND+=("gemini")
fi
if command -v codex &>/dev/null; then
    ok "Codex found: $(which codex)"
    BRAINS_FOUND+=("codex")
fi

JANE_BRAIN=""
if [ ${#BRAINS_FOUND[@]} -eq 0 ]; then
    warn "No AI CLI detected. Jane needs one to think."
    echo ""
    echo -e "  Install one of these (requires Node.js from ${CYAN}https://nodejs.org${NC}):"
    echo -e "    ${CYAN}npm install -g @anthropic-ai/claude-code${NC}   — Claude Code (best, needs subscription)"
    echo -e "    ${CYAN}npm install -g @google/gemini-cli${NC}          — Gemini CLI (free tier available)"
    echo -e "    ${CYAN}npm install -g @openai/codex${NC}               — Codex (needs OpenAI API key)"
    echo ""
    echo -n "  Which will you use? (claude/gemini/codex): "
    read -r JANE_BRAIN
    if [[ ! "$JANE_BRAIN" =~ ^(claude|gemini|codex)$ ]]; then
        JANE_BRAIN="gemini"
        warn "Defaulting to gemini"
    fi
    warn "Install it now, then re-run this script to verify."
elif [ ${#BRAINS_FOUND[@]} -eq 1 ]; then
    JANE_BRAIN="${BRAINS_FOUND[0]}"
    ok "Using $JANE_BRAIN as Jane's brain (only one found)"
else
    echo ""
    echo -n "  Multiple CLIs found. Which should Jane use? (${BRAINS_FOUND[*]}): "
    read -r JANE_BRAIN
    # Validate
    VALID=false
    for b in "${BRAINS_FOUND[@]}"; do
        if [ "$b" = "$JANE_BRAIN" ]; then VALID=true; break; fi
    done
    if [ "$VALID" = false ]; then
        JANE_BRAIN="${BRAINS_FOUND[0]}"
        warn "Invalid choice -- using $JANE_BRAIN"
    fi
    ok "Using $JANE_BRAIN as Jane's brain"
fi
set_env "JANE_BRAIN" "$JANE_BRAIN"

# -- API key --
echo ""
case "$JANE_BRAIN" in
    claude)
        info "Claude Code authenticates via its own login -- no API key needed here."
        info "Make sure you've run 'claude' at least once to log in."
        echo ""
        info "A Google API key is optional but useful for weather and background services."
        EXISTING_GKEY=$(grep -oP '^GOOGLE_API_KEY=\K.+' "vessence-data/.env" 2>/dev/null || true)
        if [ -n "$EXISTING_GKEY" ]; then
            info "Google API key already set"
        else
            echo -e "  Get a free one at: ${CYAN}https://aistudio.google.com${NC} → Get API key"
            echo -n "  Google API key (or press Enter to skip): "
            read -r GOOGLE_KEY
            if [ -n "$GOOGLE_KEY" ]; then
                set_env "GOOGLE_API_KEY" "$GOOGLE_KEY"
                ok "Google API key saved"
            else
                info "Skipped -- you can add it later in vessence-data/.env"
            fi
        fi
        ;;
    gemini)
        EXISTING_GKEY=$(grep -oP '^GOOGLE_API_KEY=\K.+' "vessence-data/.env" 2>/dev/null || true)
        if [ -n "$EXISTING_GKEY" ]; then
            info "Google API key already set"
        else
            echo -e "  Jane needs a Google Gemini API key. It's free."
            echo -e "  Get one at: ${CYAN}https://aistudio.google.com${NC} → Get API key"
            echo -e "  It looks like: AIzaSy..."
            echo -n "  Google API key: "
            read -r GOOGLE_KEY
            if [ -n "$GOOGLE_KEY" ]; then
                set_env "GOOGLE_API_KEY" "$GOOGLE_KEY"
                ok "Google API key saved"
            else
                warn "No key entered -- Jane won't work without it. Add it to vessence-data/.env later."
            fi
        fi
        ;;
    codex)
        EXISTING_OKEY=$(grep -oP '^OPENAI_API_KEY=\K.+' "vessence-data/.env" 2>/dev/null || true)
        if [ -n "$EXISTING_OKEY" ]; then
            info "OpenAI API key already set"
        else
            echo -e "  Jane needs an OpenAI API key."
            echo -e "  Get one at: ${CYAN}https://platform.openai.com/api-keys${NC}"
            echo -e "  It looks like: sk-proj-..."
            echo -n "  OpenAI API key: "
            read -r OPENAI_KEY
            if [ -n "$OPENAI_KEY" ]; then
                set_env "OPENAI_API_KEY" "$OPENAI_KEY"
                ok "OpenAI API key saved"
            else
                warn "No key entered -- Jane won't work without it. Add it to vessence-data/.env later."
            fi
        fi
        ;;
esac

# ═════════════════════════════════════════════════════════════════════════════
# Phase 7 — Link Agent Configuration
# ═════════════════════════════════════════════════════════════════════════════

header "Phase 7: Linking agent configuration"

info "Connecting your AI CLI to Jane's identity and protocols..."

case "$JANE_BRAIN" in
    claude)
        ln -sf vessence/CLAUDE.md ./CLAUDE.md
        ok "Linked CLAUDE.md"
        mkdir -p .claude/hooks
        ln -sf ../../vessence/startup_code/claude_smart_context.py .claude/hooks/context_build.py 2>/dev/null || true
        ok "Claude hooks directory set up"
        ;;
    gemini)
        ln -sf vessence/GEMINI.md ./GEMINI.md
        ok "Linked GEMINI.md"
        ;;
    codex)
        ln -sf vessence/AGENTS.md ./AGENTS.md
        ok "Linked AGENTS.md"
        ;;
esac

# ═════════════════════════════════════════════════════════════════════════════
# Phase 8 — Test Run
# ═════════════════════════════════════════════════════════════════════════════

header "Phase 8: Test run"

info "Starting Jane briefly to verify the server works..."

export VESSENCE_HOME="${REPO_ROOT}/vessence"
export VESSENCE_DATA_HOME="${REPO_ROOT}/vessence-data"
export VAULT_HOME="${REPO_ROOT}/vault"
export ESSENCES_DIR="${REPO_ROOT}/essences"

# Start server in background
cd vessence
../venv/bin/python -m uvicorn jane_web.main:app \
    --host 127.0.0.1 --port 8081 --log-level warning &
SERVER_PID=$!
cd "$REPO_ROOT"

# Wait for it to come up
sleep 4

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/ 2>/dev/null || echo "000")

# Clean up
kill $SERVER_PID 2>/dev/null || true
wait $SERVER_PID 2>/dev/null || true

if [ "$HTTP_STATUS" = "200" ] || [ "$HTTP_STATUS" = "302" ]; then
    ok "Server responded with HTTP $HTTP_STATUS -- it works!"
else
    warn "Server returned HTTP $HTTP_STATUS (expected 200 or 302)."
    warn "Common issues: port 8081 already in use, missing .env values, import errors."
fi

# ═════════════════════════════════════════════════════════════════════════════
# Phase 9 — Auto-Start on Boot
# ═════════════════════════════════════════════════════════════════════════════

header "Phase 9: Setting up auto-start"

OS_TYPE="$(uname -s)"

if [ "$OS_TYPE" = "Linux" ]; then
    info "Detected Linux -- using systemd user service"

    mkdir -p ~/.config/systemd/user

    SERVICE_FILE=~/.config/systemd/user/jane-web.service

    cat > "$SERVICE_FILE" << SVCEOF
[Unit]
Description=Jane Web Server
After=network.target

[Service]
Type=simple
WorkingDirectory=${REPO_ROOT}/vessence
ExecStart=${REPO_ROOT}/venv/bin/python -m uvicorn jane_web.main:app --host 127.0.0.1 --port 8081 --log-level info
Restart=always
RestartSec=5
Environment=VESSENCE_HOME=${REPO_ROOT}/vessence
Environment=VESSENCE_DATA_HOME=${REPO_ROOT}/vessence-data
Environment=VAULT_HOME=${REPO_ROOT}/vault
Environment=ESSENCES_DIR=${REPO_ROOT}/essences
EnvironmentFile=${REPO_ROOT}/vessence-data/.env

[Install]
WantedBy=default.target
SVCEOF

    ok "Service file written to $SERVICE_FILE"

    systemctl --user daemon-reload
    systemctl --user enable jane-web.service 2>/dev/null
    ok "Service enabled (will start on boot)"

    # Start the service
    systemctl --user start jane-web.service 2>/dev/null || true

    # Enable lingering so user services run without an active login
    loginctl enable-linger "$(whoami)" 2>/dev/null || true

    # Verify
    sleep 2
    if systemctl --user is-active jane-web.service &>/dev/null; then
        ok "jane-web.service is running"
    else
        warn "Service installed but may not be active yet. Check with:"
        info "  systemctl --user status jane-web.service"
    fi

elif [ "$OS_TYPE" = "Darwin" ]; then
    info "Detected macOS -- using launchd"

    mkdir -p ~/Library/LaunchAgents

    PLIST_FILE=~/Library/LaunchAgents/com.vessence.jane-web.plist

    cat > "$PLIST_FILE" << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.vessence.jane-web</string>
  <key>ProgramArguments</key>
  <array>
    <string>${REPO_ROOT}/venv/bin/python</string>
    <string>-m</string><string>uvicorn</string>
    <string>jane_web.main:app</string>
    <string>--host</string><string>127.0.0.1</string>
    <string>--port</string><string>8081</string>
  </array>
  <key>WorkingDirectory</key><string>${REPO_ROOT}/vessence</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>VESSENCE_HOME</key><string>${REPO_ROOT}/vessence</string>
    <key>VESSENCE_DATA_HOME</key><string>${REPO_ROOT}/vessence-data</string>
    <key>VAULT_HOME</key><string>${REPO_ROOT}/vault</string>
    <key>ESSENCES_DIR</key><string>${REPO_ROOT}/essences</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>${REPO_ROOT}/vessence-data/logs/jane-web.log</string>
  <key>StandardErrorPath</key><string>${REPO_ROOT}/vessence-data/logs/jane-web.log</string>
</dict></plist>
PLISTEOF

    ok "Plist written to $PLIST_FILE"

    # Unload first if already loaded (idempotent)
    launchctl unload "$PLIST_FILE" 2>/dev/null || true
    launchctl load "$PLIST_FILE"
    ok "Service loaded and running"

    # Verify
    if launchctl list | grep -q vessence; then
        ok "com.vessence.jane-web is registered with launchd"
    else
        warn "Service may not be active. Check with: launchctl list | grep vessence"
    fi

else
    warn "Unsupported OS ($OS_TYPE). Cannot set up auto-start."
    info "You'll need to start the server manually:"
    info "  cd ${REPO_ROOT}/vessence && ../venv/bin/python -m uvicorn jane_web.main:app --host 127.0.0.1 --port 8081"
fi

# ═════════════════════════════════════════════════════════════════════════════
# Phase 10 — Remote Access (Optional)
# ═════════════════════════════════════════════════════════════════════════════

header "Phase 10: Remote access (optional)"

echo ""
echo -e "  Jane is running locally at ${CYAN}http://localhost:8081${NC}."
echo "  To access her from your phone or anywhere outside your home,"
echo "  you can set up a permanent public URL through the Vessences relay."
echo "  The relay forwards encrypted traffic — it never stores your data."
echo ""
echo -n "  Set up remote access now? (y/n) [n]: "
read -r SETUP_RELAY

RELAY_URL=""
if [ "$SETUP_RELAY" = "y" ] || [ "$SETUP_RELAY" = "Y" ]; then
    info "Starting relay setup..."
    cd vessence
    if ../venv/bin/python relay_client.py --setup; then
        # Try to extract the URL from the relay config
        RELAY_JSON="$HOME/.vessence-relay.json"
        if [ -f "$RELAY_JSON" ]; then
            RELAY_URL=$(./venv/bin/python -c "import json; d=json.load(open('$RELAY_JSON')); print(f'https://{d.get(\"subdomain\",\"?\")}.vessences.com')" 2>/dev/null || echo "")
        fi
        ok "Relay connected"
        if [ -n "$RELAY_URL" ]; then
            ok "Your URL: $RELAY_URL"
        fi
    else
        warn "Relay setup failed or was cancelled. You can try later:"
        info "  cd vessence && ../venv/bin/python relay_client.py --setup"
    fi
    cd "$REPO_ROOT"
else
    info "Skipped. Set up later:  cd vessence && ../venv/bin/python relay_client.py --setup"
fi

# ═════════════════════════════════════════════════════════════════════════════
# Phase 11 — Get to Know You (Optional)
# ═════════════════════════════════════════════════════════════════════════════

header "Phase 11: Quick intro (optional)"

echo ""
echo "  A few quick questions so Jane already knows you when you first meet."
echo "  Press Enter to skip any question."
echo ""

add_fact() {
    local fact="$1" topic="$2" subtopic="${3:-}"
    local cmd=(./venv/bin/python vessence/memory/v1/add_fact.py "$fact" --topic "$topic")
    if [ -n "$subtopic" ]; then
        cmd+=(--subtopic "$subtopic")
    fi
    "${cmd[@]}" >/dev/null 2>&1 || true
}

# Name/nickname
echo -n "  What should Jane call you? [$USER_NAME]: "
read -r NICKNAME
if [ -n "$NICKNAME" ] && [ "$NICKNAME" != "$USER_NAME" ]; then
    add_fact "User's name is $NICKNAME" "identity" "name"
    set_env "USER_NAME" "$NICKNAME"
    USER_NAME="$NICKNAME"
    ok "Got it, $NICKNAME"
elif [ -n "$USER_NAME" ]; then
    add_fact "User's name is $USER_NAME" "identity" "name"
    ok "Using $USER_NAME"
fi

# Profession
echo -n "  What do you do for work (or are you a student)? "
read -r PROFESSION
if [ -n "$PROFESSION" ]; then
    add_fact "User works as: $PROFESSION" "identity" "profession"
    ok "Noted"
fi

# Interests
echo -n "  What are your hobbies or interests? "
read -r INTERESTS
if [ -n "$INTERESTS" ]; then
    add_fact "User's interests: $INTERESTS" "interests"
    ok "Noted"
fi

# Communication style
echo -n "  How do you like to be talked to? (quick/detailed/casual): "
read -r STYLE
if [ -n "$STYLE" ]; then
    add_fact "User prefers $STYLE communication style" "preferences" "communication_style"
    ok "Noted"
fi

# Location
echo -n "  What city or timezone are you in? "
read -r LOCATION
if [ -n "$LOCATION" ]; then
    add_fact "User is located in $LOCATION" "identity" "location"
    ok "Noted"
fi

# Goals
echo -n "  Anything specific you want Jane to help with? "
read -r GOALS
if [ -n "$GOALS" ]; then
    add_fact "User wants help with: $GOALS" "projects"
    ok "Noted"
fi

# ═════════════════════════════════════════════════════════════════════════════
# Done
# ═════════════════════════════════════════════════════════════════════════════

header "Setup complete!"

echo ""
echo -e "${GREEN}Jane is ready. Here's what's running:${NC}"
echo "  - Web UI: http://localhost:8081"
echo "  - Brain: $JANE_BRAIN"
echo "  - Auto-starts on boot: yes"
if [ -n "$RELAY_URL" ]; then
    echo "  - Remote access: $RELAY_URL"
else
    echo "  - Remote access: local only (set up later with relay_client.py)"
fi
echo ""
echo -e "${BOLD}Useful commands:${NC}"
echo "  Update Jane:  git pull && ./venv/bin/pip install -r vessence/requirements.txt"
if [ "$OS_TYPE" = "Linux" ]; then
    echo "  View logs:    journalctl --user -u jane-web.service -f"
elif [ "$OS_TYPE" = "Darwin" ]; then
    echo "  View logs:    tail -f vessence-data/logs/jane-web.log"
fi
echo "  Android app:  https://vessences.com/downloads"
echo ""
echo -e "  ${BOLD}Open ${CYAN}http://localhost:8081${NC}${BOLD} in your browser to start talking to Jane.${NC}"
echo -e "  She already knows your name, ${GREEN}${USER_NAME}${NC}."
echo ""
