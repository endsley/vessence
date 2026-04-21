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
    if $PYTHON_CMD -m venv ./venv 2>/dev/null; then
        ok "Virtual environment created"
    else
        # Happens on Debian/Ubuntu when python3-venv isn't installed.
        # Fall back to pip-installing virtualenv into the user site so we
        # don't force the user through sudo/apt mid-install.
        warn "python3 -m venv failed (likely python3-venv not installed)."
        info "Falling back to virtualenv via --user pip install..."
        $PYTHON_CMD -m pip install --user --break-system-packages virtualenv --quiet
        VIRTUALENV_BIN="$HOME/.local/bin/virtualenv"
        if [ ! -x "$VIRTUALENV_BIN" ]; then
            VIRTUALENV_BIN="$($PYTHON_CMD -m site --user-base)/bin/virtualenv"
        fi
        "$VIRTUALENV_BIN" ./venv
        ok "Virtual environment created (via virtualenv)"
    fi
fi

info "Upgrading pip..."
./venv/bin/pip install --upgrade pip --quiet

info "Installing dependencies from vessence/requirements.txt..."
info "(This may take 1-3 minutes on first run)"
./venv/bin/pip install -r vessence/requirements.txt --quiet

# Verify the app actually imports — catches missing transitive deps that a
# simple `import chromadb, fastapi` check would let slip through (e.g. the
# itsdangerous / python-multipart deps that bit us once).
if ./venv/bin/python -c "
import sys
sys.path.insert(0, 'vessence')
from jane_web.main import app  # noqa: F401
print('OK')
" 2>/dev/null | grep -q "OK"; then
    ok "jane_web.main imports cleanly (all deps resolved)"
else
    fail "jane_web.main failed to import. Re-run with:"
    fail "  ./venv/bin/python -c \"import sys; sys.path.insert(0,'vessence'); from jane_web.main import app\""
    fail "to see the underlying error."
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
# Phase 5 — Configure Jane (delegates to first_run_setup.py)
# ═════════════════════════════════════════════════════════════════════════════

header "Phase 5: Configure Jane"

info "Launching interactive configuration (first_run_setup.py)..."
echo ""

# first_run_setup.py owns everything .env-related: copying .env.example,
# generating the session secret, detecting the AI CLI, prompting for name /
# API keys / OAuth / weather.
./venv/bin/python vessence/startup_code/first_run_setup.py

# Helper used by Phase 10 (get-to-know-you) to update USER_NAME if the user
# picks a different name during intro questions.
set_env() {
    local key="$1" value="$2"
    if grep -q "^${key}=" "vessence-data/.env" 2>/dev/null; then
        sed -i "s|^${key}=.*|${key}=${value}|" "vessence-data/.env"
    else
        echo "${key}=${value}" >> "vessence-data/.env"
    fi
}

# Read JANE_BRAIN + USER_NAME back from .env for the phases that follow.
JANE_BRAIN=$(grep -oP '^JANE_BRAIN=\K.+' "vessence-data/.env" 2>/dev/null || echo "")
USER_NAME=$(grep -oP '^USER_NAME=\K.+' "vessence-data/.env" 2>/dev/null || echo "")

if [ -z "$JANE_BRAIN" ]; then
    fail "JANE_BRAIN was not set by first_run_setup.py. Aborting."
    exit 1
fi
ok "Brain: $JANE_BRAIN, name: ${USER_NAME:-<unset>}"

# ═════════════════════════════════════════════════════════════════════════════
# Phase 6 — Link Agent Configuration
# ═════════════════════════════════════════════════════════════════════════════

header "Phase 6: Linking agent configuration"

info "Connecting your AI CLI to Jane's identity and protocols..."

case "$JANE_BRAIN" in
    claude)
        ln -sf vessence/CLAUDE.md ./CLAUDE.md
        ok "Linked CLAUDE.md"

        # Also symlink CLAUDE.md into $HOME so Jane's identity loads from any directory
        if [ "$(realpath "${REPO_ROOT}")" != "$(realpath "${HOME}")" ]; then
            ln -sf "${REPO_ROOT}/CLAUDE.md" "${HOME}/CLAUDE.md" 2>/dev/null || true
            ok "Linked CLAUDE.md to \$HOME"
        fi

        # Hook: context_build.py — pipes each user prompt through ChromaDB and returns
        # relevant memory as additionalContext. Must be registered in settings.json;
        # simply placing the file in .claude/hooks/ has no effect.
        mkdir -p .claude/hooks
        ln -sf ../../vessence/startup_code/claude_smart_context.py .claude/hooks/context_build.py 2>/dev/null || true
        ln -sf ../../vessence/startup_code/stop_hook_memory.py .claude/hooks/stop_memory.py 2>/dev/null || true
        ok "Claude hooks directory set up"

        CONTEXT_HOOK="${REPO_ROOT}/venv/bin/python ${REPO_ROOT}/.claude/hooks/context_build.py"
        STOP_HOOK="${REPO_ROOT}/venv/bin/python ${REPO_ROOT}/.claude/hooks/stop_memory.py"

        # Write project-level settings.json (fires when running from ~/ambient)
        cat > .claude/settings.json << CLSETTINGS
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CONTEXT_HOOK}"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${STOP_HOOK}"
          }
        ]
      }
    ]
  }
}
CLSETTINGS
        ok "Wrote .claude/settings.json (context + memory hooks)"

        # Merge both hooks into global ~/.claude/settings.json so they fire from any directory
        GLOBAL_SETTINGS="${HOME}/.claude/settings.json"
        if [ -f "$GLOBAL_SETTINGS" ]; then
            "${REPO_ROOT}/venv/bin/python" - "$GLOBAL_SETTINGS" "$CONTEXT_HOOK" "$STOP_HOOK" << 'PYMERGE'
import json, sys
path, context_cmd, stop_cmd = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path) as f:
    cfg = json.load(f)
hooks = cfg.setdefault("hooks", {})

# UserPromptSubmit — replace any existing Jane entry
ups = hooks.setdefault("UserPromptSubmit", [])
hooks["UserPromptSubmit"] = [e for e in ups if "context_build" not in str(e)]
hooks["UserPromptSubmit"].append({"hooks": [{"type": "command", "command": context_cmd}]})

# Stop — replace any existing Jane entry
stops = hooks.setdefault("Stop", [])
hooks["Stop"] = [e for e in stops if "stop_memory" not in str(e)]
hooks["Stop"].append({"hooks": [{"type": "command", "command": stop_cmd}]})

with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
PYMERGE
            ok "Merged context + memory hooks into global ~/.claude/settings.json"
        else
            cat > "$GLOBAL_SETTINGS" << GLSETTINGS
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CONTEXT_HOOK}"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${STOP_HOOK}"
          }
        ]
      }
    ]
  }
}
GLSETTINGS
            ok "Wrote global ~/.claude/settings.json (context + memory hooks)"
        fi
        ;;
    gemini)
        ln -sf vessence/GEMINI.md ./GEMINI.md
        ok "Linked GEMINI.md"
        ;;
    openai|codex)
        ln -sf vessence/AGENTS.md ./AGENTS.md
        ok "Linked AGENTS.md"
        ;;
esac

# ═════════════════════════════════════════════════════════════════════════════
# Phase 7 — Test Run
# ═════════════════════════════════════════════════════════════════════════════

header "Phase 7: Test run"

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
# Phase 8 — Auto-Start on Boot
# ═════════════════════════════════════════════════════════════════════════════

header "Phase 8: Setting up auto-start"

OS_TYPE="$(uname -s)"

if [ "$OS_TYPE" = "Linux" ]; then
    info "Detected Linux -- using systemd user service"

    mkdir -p ~/.config/systemd/user
    mkdir -p vessence-data/logs

    SERVICE_FILE=~/.config/systemd/user/jane-web.service
    TEMPLATE_FILE=vessence/configs/systemd/jane-web.service

    if [ ! -f "$TEMPLATE_FILE" ]; then
        fail "Missing systemd template at $TEMPLATE_FILE"
        exit 1
    fi

    # Single source of truth: the committed template. It uses %h for the
    # user's home directory, so no path substitution is needed.
    cp "$TEMPLATE_FILE" "$SERVICE_FILE"
    ok "Service file installed from $TEMPLATE_FILE → $SERVICE_FILE"

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
# Phase 9 — Remote Access (Optional)
# ═════════════════════════════════════════════════════════════════════════════

header "Phase 9: Remote access (optional)"

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
# Phase 10 — Get to Know You (Optional)
# ═════════════════════════════════════════════════════════════════════════════

header "Phase 10: Quick intro (optional)"

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
# Phase 11 — Cron Jobs
# ═════════════════════════════════════════════════════════════════════════════

header "Phase 11: Installing cron jobs"

# Build the full crontab from scratch so it's idempotent.
# Env header fixes the "$VESSENCE_HOME expands to empty in cron" bug —
# cron does not inherit the login shell's environment.
CRONTAB_CONTENT="# Jane cron jobs — managed by setup.sh, do not edit manually
AMBIENT_BASE=${REPO_ROOT}
VESSENCE_HOME=${REPO_ROOT}/vessence
VESSENCE_DATA_HOME=${REPO_ROOT}/vessence-data
VAULT_HOME=${REPO_ROOT}/vault
ESSENCES_DIR=${REPO_ROOT}/essences
PYTHONPATH=${REPO_ROOT}/vessence
PYTHON=${REPO_ROOT}/venv/bin/python
SHELL=/bin/bash

# Auto-pull: fetch + fast-forward every 2 hours; reinstall deps / restart if needed
0 */2 * * * /bin/bash ${REPO_ROOT}/vessence/startup_code/auto_pull.sh

# Memory janitor: expire short-term, merge duplicates, verify code memories vs codebase
15 2 * * * \${PYTHON} ${REPO_ROOT}/vessence/memory/v1/janitor_memory.py

# Nightly self-improvement: doc drift audit, code audit, pipeline audit, dead code scan
0 1 * * * \${PYTHON} ${REPO_ROOT}/vessence/agent_skills/nightly_self_improve.py

# Identity essay regeneration (self-reflection from memories)
0 3 * * * \${PYTHON} ${REPO_ROOT}/vessence/agent_skills/generate_identity_essay.py

# Jane context regeneration (rebuild boot context from configs)
15 3 * * * \${PYTHON} ${REPO_ROOT}/vessence/startup_code/regenerate_jane_context.py

# Code map regeneration (file/function/route index)
15 4 * * * \${PYTHON} ${REPO_ROOT}/vessence/agent_skills/generate_code_map.py

# System janitor: temp files, log rotation, old session transcript pruning
0 3 * * * \${PYTHON} ${REPO_ROOT}/vessence/agent_skills/janitor_system.py

# Essence scheduler: dispatch scheduled essence tasks every minute
* * * * * \${PYTHON} ${REPO_ROOT}/vessence/agent_skills/essence_scheduler.py

# Job queue runner: process pending jobs every 5 minutes
*/5 * * * * \${PYTHON} ${REPO_ROOT}/vessence/agent_skills/job_queue_runner.py

# Process watchdog: kill zombie Docker containers, idle daemons, memory hogs
*/5 * * * * \${PYTHON} ${REPO_ROOT}/vessence/agent_skills/process_watchdog.py

# USB incremental sync backup (daily at 2:00 AM)
0 2 * * * \${PYTHON} ${REPO_ROOT}/vessence/startup_code/usb_sync.py

# Evolve code map keywords from today's user messages
10 2 * * * \${PYTHON} ${REPO_ROOT}/vessence/agent_skills/evolve_code_map_keywords.py

# Daily briefing fetch (news, TTS audio)
10 2 * * * /bin/bash -c 'timeout 30m \${PYTHON} ${REPO_ROOT}/tools/daily_briefing/functions/run_briefing.py'

# Screen dimmer: dim monitor after sunset every 30 minutes
*/30 * * * * \${PYTHON} ${REPO_ROOT}/vessence/agent_skills/screen_dimmer.py
"

if command -v crontab &>/dev/null; then
    echo "$CRONTAB_CONTENT" | crontab -
    ok "Crontab installed ($(echo "$CRONTAB_CONTENT" | grep -c '^\*\|^[0-9]') jobs)"
    info "Memory janitor + code-memory verifier runs nightly at 2:15 AM"
    info "Self-improvement orchestrator runs nightly at 1:00 AM"
else
    warn "crontab command not found — skipping cron setup"
    info "Install cron: sudo apt install -y cron"
fi

# Run the memory janitor immediately so the first session doesn't have to
# wait until 2:15 AM for themes to be archived and code memories verified.
info "Running memory janitor for the first time..."
if "${REPO_ROOT}/venv/bin/python" "${REPO_ROOT}/vessence/memory/v1/janitor_memory.py" 2>/dev/null; then
    ok "Memory janitor completed"
else
    warn "Memory janitor exited with an error (non-fatal — will retry tonight at 2:15 AM)"
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
