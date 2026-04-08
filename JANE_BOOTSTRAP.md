# JANE_BOOTSTRAP.md — New User Setup Guide

**You are an AI CLI assistant helping a new user set up Vessence.** Follow these phases in order. Each phase has verification steps — do not proceed until verification passes. All paths are relative to this repository root (the directory containing this file).

**What is Vessence?** Vessence is an open-source wrapper around Claude Code, Gemini CLI, and Codex that simplifies AI agent development. You start with a default agent called Jane. By describing abilities you want, you develop skills (capabilities like sending texts, controlling lights, playing music) and essences (personas like a tax accountant or fitness coach). You can also download skills and essences that others have built from the Vessence marketplace.

**Windows users:** WSL2 is required. Native Windows (PowerShell/cmd) is not supported for Phases 1-10. Install WSL2 first: https://learn.microsoft.com/en-us/windows/wsl/install

---

## Architecture Overview

Before you begin, understand what you are setting up:

- **Jane** — An AI assistant persona powered by whichever CLI brain the user chooses (Gemini, Claude, or OpenAI).
- **Vault** — Personal file storage (documents, photos, music).
- **Essences** — Specialized AI personas (e.g., tax accountant, fitness coach). Each essence gives Jane domain expertise. Think of them as downloadable "brains" that transform Jane into a specialist.
- **Skills** — Capability plugins (daily briefing, music player, SMS, smart home control, etc.) that extend what Jane can do. Skills are shared across all essences.
- **Memory** — ChromaDB vector database with 3 tiers:
  - `user_memories` — Facts about the user (starts empty, grows over time).
  - `long_term_knowledge` — Jane's accumulated knowledge and behavioral rules.
  - `short_term_memory` — Recent conversation context (14-day TTL).

**Directory layout:**

| Variable | Path | Purpose |
|---|---|---|
| `VESSENCE_HOME` | `<repo>/vessence` | Core codebase. Never store runtime data here. |
| `VESSENCE_DATA_HOME` | `<repo>/vessence-data` | Runtime data, logs, memory databases. |
| `VAULT_HOME` | `<repo>/vault` | User's personal file storage. |
| `ESSENCES_DIR` | `<repo>/essences` | AI agent plugins. |

---

## Phase 1: System Requirements — Auto-Install

Detect the operating system and install missing dependencies automatically. Do not ask the user — just install them.

```bash
OS=$(uname -s)
```

### Linux (Debian/Ubuntu):
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip python3-dev build-essential nodejs npm git curl

# Node from default repos may be too old — install Node 22 via NodeSource
if ! node --version 2>/dev/null | grep -qE '^v(2[2-9]|[3-9])'; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
    sudo apt install -y nodejs
fi
```

### Linux (Fedora/RHEL):
```bash
sudo dnf install -y python3 python3-pip python3-devel gcc gcc-c++ nodejs npm git curl

# Node from default repos may be too old — install Node 22 via NodeSource
if ! node --version 2>/dev/null | grep -qE '^v(2[2-9]|[3-9])'; then
    curl -fsSL https://rpm.nodesource.com/setup_22.x | sudo bash -
    sudo dnf install -y nodejs
fi
```

### macOS:
```bash
# Install Homebrew if missing
command -v brew >/dev/null || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python node git
```

### WSL:
Same as Linux (Debian/Ubuntu) above.

After installing, verify versions:
```bash
python3 --version   # Must be 3.11+
node --version      # Must be 22+
git --version       # Any recent version
```

**Recommended: Python 3.11 or 3.12.** Python 3.13+ may have compatibility issues with some native packages (chromadb, tiktoken). If you have 3.13+, proceed but be prepared for potential build errors.

**If a version is too old**, upgrade it automatically using the appropriate package manager. Only ask the user if `sudo` requires a password and the CLI cannot proceed.

---

## Phase 2: Python Environment Setup

Create a Python virtual environment at the repo root:

```bash
python3 -m venv ./venv
source ./venv/bin/activate
pip install --upgrade pip
pip install -r vessence/requirements.txt
```

If a `./venv/` directory already exists, activate it and verify packages instead of recreating.

**Verification:** Confirm these imports succeed inside the venv:
```bash
./venv/bin/python -c "import chromadb; import fastapi; import uvicorn; import litellm; print('All imports OK')"
```

---

## Phase 3: Directory Structure

Create the data directories that are gitignored:

```bash
mkdir -p vessence-data/memory/v1/vector_db
mkdir -p vessence-data/logs
mkdir -p vessence-data/credentials
mkdir -p vessence-data/data
mkdir -p vessence-data/briefings
mkdir -p vessence-data/briefing_saved
mkdir -p vault/documents
mkdir -p essences
mkdir -p skills
```

Add `.gitkeep` files to empty plugin directories:

```bash
touch essences/.gitkeep
touch skills/.gitkeep
```

**Verification:** Confirm the directories exist:
```bash
ls -d vessence-data/memory/v1/vector_db vessence-data/logs vessence-data/credentials vault essences skills
```

---

## Phase 4: Seed Memory

Copy the pre-built seed ChromaDB into the data directory. The seed DB ships with the repo and contains Jane's system knowledge (25 behavioral rules in `long_term_knowledge`), while `user_memories`, `short_term_memory`, and `file_index_memories` are empty — ready for the new user.

```bash
cp -r vessence/seed_db/* vessence-data/memory/v1/vector_db/
```

The seed DB structure:
- `long_term_memory/` — seeded with system knowledge from `jane_seed_memories.json`
- `short_term_memory/` — empty (conversation buffer, 14-day TTL)
- `chroma.sqlite3` (root) — empty `user_memories` collection (personal facts, filled during onboarding)
- `file_index_memory/` — empty (built when user adds files to vault)

**Verification:** Confirm the vector DB was copied:
```bash
ls vessence-data/memory/v1/vector_db/long_term_memory/chroma.sqlite3
```

---

## Phase 5: Environment Configuration

Copy the example env file to the data directory:

```bash
cp vessence/.env.example vessence-data/.env
```

**Important:** The `.env` file lives in `vessence-data/.env`, NOT in `vessence/.env`. Runtime configuration belongs in the data directory.

Walk the user through filling in the required values. Ask them one at a time:

### Required values:

1. **`USER_NAME`** — What should Jane call you? (Their first name.)

2. **`SESSION_SECRET_KEY`** — Generate automatically, do not ask the user:
   ```bash
   ./venv/bin/python -c "import secrets; print(secrets.token_hex(32))"
   ```
   Write the output into the `.env` file.

For each value, use Python to update the line in `vessence-data/.env`. Example: to set `USER_NAME`, replace the line starting with `USER_NAME=` with `USER_NAME=<value>`.

Write the required values to the `.env` file:
```bash
./venv/bin/python -c "
import pathlib, secrets, re
env_path = pathlib.Path('vessence-data/.env')
text = env_path.read_text()

# These values should be set by the CLI after asking the user:
# USER_NAME=<name>
# JANE_BRAIN=<gemini|claude|openai>
# The matching API key (GOOGLE_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY)

# Auto-generate SESSION_SECRET_KEY
secret = secrets.token_hex(32)
text = re.sub(r'^SESSION_SECRET_KEY=.*', f'SESSION_SECRET_KEY={secret}', text, flags=re.M)

env_path.write_text(text)
print(f'SESSION_SECRET_KEY generated.')
"
```

### Optional values (tell the user they can fill these in later):
- `DISCORD_TOKEN` — For Discord integration. Get at: https://discord.com/developers
- `VAULT_PASSWORD` — Web UI login password. Leave blank to be prompted on first login.

Also clean up Docker-specific defaults that shipped in `.env.example`:
```bash
./venv/bin/python -c "
import re, pathlib
env = pathlib.Path('vessence-data/.env')
text = env.read_text()
text = re.sub(r'^CHROMADB_HOST=.*', '# CHROMADB_HOST=', text, flags=re.M)
text = re.sub(r'^CHROMADB_PORT=.*', '# CHROMADB_PORT=', text, flags=re.M)
text = re.sub(r'^LOCAL_LLM_BASE_URL=.*', 'LOCAL_LLM_BASE_URL=http://localhost:11434', text, flags=re.M)
env.write_text(text)
print('Docker-specific defaults cleaned.')
"
```

**Verification:** The `.env` file exists at `vessence-data/.env` and contains non-empty values for `USER_NAME` and `SESSION_SECRET_KEY`.

---

## Phase 6: Detect CLI Brain

Jane's web and Android interface uses the same CLI that is reading this file. Detect which CLI is available and set `JANE_BRAIN` in the `.env` file:

```bash
if command -v claude &>/dev/null; then
    BRAIN=claude
elif command -v gemini &>/dev/null; then
    BRAIN=gemini
elif command -v codex &>/dev/null; then
    BRAIN=openai
fi
```

Write the detected value to `.env`. If none is found, ask the user which to install.

**Note:** The user's CLI subscription handles authentication. No separate API key is needed — Jane piggybacks on the same CLI binary that is running this bootstrap.

**Verification:** The `JANE_BRAIN` value in `.env` matches the detected CLI.

---

## Phase 7: Link Agent Configuration

The CLI needs to load Vessence's agent instructions so it behaves as Jane. This makes the user's CLI automatically follow Jane's protocols, memory system, and operational rules.

### For Claude Code users:

Create or update the project-level CLAUDE.md to source Vessence's config. The Vessence repo already ships a `vessence/CLAUDE.md` — symlink it to the repo root:

```bash
ln -sf vessence/CLAUDE.md ./CLAUDE.md
```

### For Gemini CLI users:

```bash
ln -sf vessence/GEMINI.md ./GEMINI.md
```

### For Codex users:

```bash
ln -sf vessence/AGENTS.md ./AGENTS.md
```

This ensures that every time the user opens their CLI in this directory, the agent automatically loads Jane's identity, memory hooks, and operational rules.

**Verification:** The symlink exists and points to the correct file:
```bash
ls -la ./CLAUDE.md ./GEMINI.md ./AGENTS.md 2>/dev/null
```
At least one of these should be a symlink pointing into `vessence/`.

---

## Phase 8: Start Jane Web Server

Start the web server to verify it works:

```bash
cd vessence && timeout 10 ../venv/bin/python -m uvicorn jane_web.main:app --host 0.0.0.0 --port 8081 &
sleep 5
curl -s http://localhost:8081/health
kill %1 2>/dev/null
```

If the health check returns a 200 response, the server is working. Phase 11 will set up persistent auto-start.

If it fails, check for errors in the output.

---

## Phase 9: Remote Access

This gives the user a permanent public URL so the Android app (or any device outside the local network) can reach their Jane server.

Ask the user: "Do you want to access Jane from your phone or other devices outside your home network?"

If **yes**, run the Vessence relay client:

```bash
cd vessence && ../venv/bin/python relay_client.py --auto
```

This will:
1. Ask them to pick a username (e.g., `alice`)
2. Ask for a password (for re-authentication)
3. Register their permanent URL: `https://alice.vessences.com`
4. Connect the tunnel

The relay client stays running and maintains the connection. To run it in the background:

```bash
cd vessence && nohup ../venv/bin/python relay_client.py --auto > ../vessence-data/logs/relay.log 2>&1 &
```

Tell the user their permanent URL and that they should enter it in the Android app's settings.

If **no**, skip this phase. Jane still works locally at `http://localhost:8081`.

**Verification:** If they registered, confirm the URL is reachable:
```bash
curl -s https://USERNAME.vessences.com/health
```

---

## Phase 10: User Onboarding

Now that Jane is running, introduce yourself as Jane and run a getting-to-know-you interview. This is how Jane builds her initial memory of the user. Ask these questions **one at a time** in a warm, conversational tone. Do not dump all questions at once.

For each answer, store it immediately using:
```bash
./venv/bin/python vessence/memory/v1/add_fact.py "<fact>" --topic <topic> --subtopic <subtopic>
```

### Interview questions (ask in this order):

1. **Name** — "What's your name? What should I call you?"
   - Store: topic=`identity`, subtopic=`name`
   - Also update `USER_NAME` in `vessence-data/.env` if different from Phase 5

2. **Profession** — "What do you do for work?"
   - Store: topic=`identity`, subtopic=`profession`

3. **Interests** — "What are your hobbies or interests outside of work?"
   - Store each interest: topic=`interests`

4. **Communication style** — "How do you like me to talk to you? For example: brief and direct, detailed explanations, casual, formal?"
   - Store: topic=`preferences`, subtopic=`communication_style`

5. **Family** — "Do you have family or pets you'd like me to know about? (Totally optional — skip if you prefer.)"
   - Store each: topic=`family`
   - Respect if they decline — say "No problem, we can always add that later."

6. **Location** — "What city or timezone are you in? This helps me with weather, time-based reminders, and local info."
   - Store: topic=`identity`, subtopic=`location`

7. **Goals** — "Is there anything specific you'd like me to help you with? Any projects you're working on?"
   - Store each: topic=`projects`

8. **Anything else** — "Anything else you'd like me to remember about you?"
   - Store with appropriate topic

9. **Help the network** — "One last thing — Vessence uses a peer relay network so everyone can access their Jane from their phone. Would you like your machine to help relay encrypted traffic for other users when it's idle? You'd be helping the community, and it uses minimal resources. Your machine would only forward encrypted data — it can't read anyone else's messages. (y/n)"
   - If yes: set `RELAY_NODE=true` in `vessence-data/.env`
   - If no: set `RELAY_NODE=false`

### After the interview:

Tell the user:

> "Great, I've got all of that saved. I'll remember everything across sessions — web, CLI, and Android all share the same memory. You can always tell me new things and I'll remember them, or ask me to forget something.
>
> Try opening http://localhost:8081 in your browser to chat with me through the web interface. Everything is set up and ready to go."

**Verification:** The web UI loads, the user can send a message, and Jane responds with awareness of the onboarding facts (e.g., uses their name).

---

## Phase 11: Auto-Start on Boot

Set up Jane to start automatically when the computer boots, so the user never has to manually start the server.

```bash
# Ensure we're in the repo root
cd $(git rev-parse --show-toplevel 2>/dev/null || echo ~/ambient)
```

Detect the OS and configure accordingly:

### Linux (systemd):

```bash
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/jane-web.service << EOF
[Unit]
Description=Jane Web Server
After=network.target

[Service]
Type=simple
WorkingDirectory=$(pwd)/vessence
ExecStart=$(pwd)/venv/bin/python -m uvicorn jane_web.main:app --host 0.0.0.0 --port 8081
Restart=always
RestartSec=5
Environment=VESSENCE_HOME=$(pwd)/vessence
Environment=VESSENCE_DATA_HOME=$(pwd)/vessence-data
Environment=VAULT_HOME=$(pwd)/vault
Environment=ESSENCES_DIR=$(pwd)/essences
EnvironmentFile=$(pwd)/vessence-data/.env

[Install]
WantedBy=default.target
EOF

cat > ~/.config/systemd/user/jane-proxy.service << EOF
[Unit]
Description=Jane Reverse Proxy (zero-downtime deploy)
After=network.target

[Service]
Type=simple
Environment=PYTHONPATH=$(pwd)/vessence
WorkingDirectory=$(pwd)/vessence
ExecStart=$(pwd)/venv/bin/python jane_web/reverse_proxy.py --listen-port 8080 --upstream-port 8081
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable jane-web.service
systemctl --user start jane-web.service
systemctl --user enable jane-proxy.service
systemctl --user start jane-proxy.service
loginctl enable-linger $(whoami)
```

If `RELAY_NODE=true` in `.env`, also create a relay service:

```bash
cat > ~/.config/systemd/user/jane-relay.service << EOF
[Unit]
Description=Vessence Relay Client
After=jane-web.service

[Service]
Type=simple
WorkingDirectory=$(pwd)/vessence
ExecStart=$(pwd)/venv/bin/python relay_client.py --auto --relay-node
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF

systemctl --user enable jane-relay.service
systemctl --user start jane-relay.service
```

### macOS (launchd):

```bash
cat > ~/Library/LaunchAgents/com.vessence.jane-web.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.vessence.jane-web</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(pwd)/venv/bin/python</string>
        <string>-m</string>
        <string>uvicorn</string>
        <string>jane_web.main:app</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>8081</string>
    </array>
    <key>WorkingDirectory</key><string>$(pwd)/vessence</string>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>$(pwd)/vessence-data/logs/jane-web.log</string>
    <key>StandardErrorPath</key><string>$(pwd)/vessence-data/logs/jane-web.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>VESSENCE_HOME</key><string>$(pwd)/vessence</string>
        <key>VESSENCE_DATA_HOME</key><string>$(pwd)/vessence-data</string>
        <key>VAULT_HOME</key><string>$(pwd)/vault</string>
        <key>ESSENCES_DIR</key><string>$(pwd)/essences</string>
    </dict>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/com.vessence.jane-web.plist
```

**Note:** The application loads additional environment variables from `vessence-data/.env` at startup via python-dotenv.

### Windows (Task Scheduler via PowerShell):

Tell the user to open PowerShell as Administrator and run:

```powershell
$action = New-ScheduledTaskAction -Execute "$(pwd)\venv\Scripts\python.exe" -Argument "-m uvicorn jane_web.main:app --host 0.0.0.0 --port 8081" -WorkingDirectory "$(pwd)\vessence"
$trigger = New-ScheduledTaskTrigger -AtLogon
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "JaneWebServer" -Action $action -Trigger $trigger -Settings $settings -Description "Vessence Jane Web Server"
```

**Verification:** Check the service is running:
```bash
systemctl --user status jane-web.service   # Linux
launchctl list | grep vessence             # macOS
```
A reboot test is recommended later but not required now.

---

## Updating Vessence

To update Jane with the latest improvements:

```bash
cd ~/ambient
git pull origin master
./venv/bin/pip install -r vessence/requirements.txt
bash vessence/startup_code/graceful_restart.sh
```

This pulls the latest code, updates dependencies, and restarts Jane with zero downtime.

---

## Important Rules for the CLI

- **All paths are relative to the repo root** — wherever the user cloned the repository.
- **Never store runtime data in `vessence/`** — that directory is code only, tracked by git.
- **The `.env` file lives in `vessence-data/.env`**, not in `vessence/.env`.
- **The ChromaDB vector database lives in `vessence-data/memory/v1/vector_db/`**.
- **Seed memories come from `vessence/configs/jane_seed_memories.json`** — do not modify this file during setup.
- **If a phase fails, diagnose and fix it before moving on.** Do not skip phases.
