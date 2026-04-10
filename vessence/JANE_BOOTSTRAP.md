# JANE_BOOTSTRAP.md — Vessence Setup Guide

**You are an AI CLI assistant.** Your job right now is to help the user get their own personal Jane AI up and running. Follow every phase in order. Read through a phase completely before executing it. Explain what you're doing to the user in plain language as you go — they should never feel lost or confused.

**What is Vessence?**
Jane is a personal AI assistant that runs entirely on the user's own computer. Their data never leaves their machine. They can chat with Jane through a web browser, through this CLI, or through a phone app. Jane remembers everything they tell her across all of those interfaces. As they use it, they can extend Jane with new skills (sending texts, controlling smart home devices, playing music) and switch between specialized personas called essences (a tax accountant, a fitness coach, etc.).

**Windows users:** WSL2 is required. Run `wsl --install` in PowerShell as Administrator, reboot, then re-run this bootstrap inside the WSL terminal.

---

## Phase 1 — Check Prerequisites

Tell the user: *"Let me check what's already installed on your system."*

Run these checks:

```bash
python3 --version
git --version
```

**Python 3.11 or 3.12 is required.** If Python is missing or older than 3.11, install it:

- **Ubuntu/Debian:** `sudo apt update && sudo apt install -y python3.12 python3.12-venv python3.12-dev`
- **Fedora/RHEL:** `sudo dnf install -y python3.12`
- **macOS:** `brew install python@3.12` (install Homebrew first if missing: https://brew.sh)

If `git` is missing: `sudo apt install -y git` or `brew install git`

**Python 3.13+ note:** May have compatibility issues with some packages. 3.11 or 3.12 is the sweet spot. If the user only has 3.13+, proceed anyway — it usually works fine.

After installing anything, confirm the versions look right and tell the user what was found.

---

## Phase 2 — Python Environment

Tell the user: *"Setting up a Python environment. This keeps Vessence's packages separate from your system Python so nothing conflicts."*

```bash
# Run from the repo root (~/ambient)
python3 -m venv ./venv
source ./venv/bin/activate   # On Windows/WSL: source ./venv/Scripts/activate
pip install --upgrade pip --quiet
pip install -r vessence/requirements.txt
```

This installs all of Jane's server packages. It will take 1-3 minutes on first run. Let the user know it's working — show them a progress line if possible.

**Verify it worked:**
```bash
./venv/bin/python -c "import chromadb, fastapi, uvicorn; print('Environment OK')"
```

If you see `Environment OK`, move on. If there's an import error, read the error message and fix it (usually a missing system library — tell the user what to install).

---

## Phase 3 — Create Data Directories

Tell the user: *"Creating folders for Jane's memory, logs, and your personal vault. These folders are separate from the code so updates never touch your data."*

```bash
mkdir -p vessence-data/memory/v1/vector_db
mkdir -p vessence-data/logs
mkdir -p vessence-data/credentials
mkdir -p vault/documents
mkdir -p essences
mkdir -p skills
touch essences/.gitkeep skills/.gitkeep
```

No output needed — just confirm it's done.

---

## Phase 4 — Seed Jane's Memory

Tell the user: *"Giving Jane her starting knowledge — the rules and behaviors that define how she works. Your personal memories start empty and will grow as you use her."*

```bash
cp -r vessence/seed_db/* vessence-data/memory/v1/vector_db/
```

**Verify:**
```bash
ls vessence-data/memory/v1/vector_db/long_term_memory/chroma.sqlite3
```

If the file exists, the seed is in place.

---

## Phase 5 — Configure Jane

Tell the user: *"Now I need to set up your configuration file. I'll walk you through what's needed — there are only a few required things."*

```bash
cp vessence/.env.example vessence-data/.env
```

### Ask the user these questions (one at a time):

**Question 1: Your name**
Ask: *"What's your name? Jane will use this to address you."*
Write their answer into `vessence-data/.env` as `USER_NAME=<their answer>`.

**Question 2: Which AI brain to use**

Explain: *"Jane uses an AI CLI as her brain. I can detect which ones you have installed — let me check."*

Run:
```bash
which claude 2>/dev/null && echo "claude found"
which gemini 2>/dev/null && echo "gemini found"
which codex  2>/dev/null && echo "codex found"
```

- If **one is found**: say *"Found [name] — I'll use that."* Set `JANE_BRAIN=<name>` in `.env`. Skip to Question 3.
- If **multiple found**: ask which they prefer.
- If **none found**: explain the options and ask which they want to set up:

  > *"Jane needs an AI CLI to think. The three options are:*
  > - *Claude Code (from Anthropic) — best overall, requires a paid Claude subscription or API key. Install: `npm install -g @anthropic-ai/claude-code`, then run `claude` to log in.*
  > - *Gemini CLI (from Google) — free tier available, good for most users. Install: `npm install -g @google/gemini-cli`*
  > - *Codex (from OpenAI) — requires an OpenAI API key. Install: `npm install -g @openai/codex`*
  >
  > *Which would you like to use?"*

  Help them install the one they choose (install Node.js first if `npm` isn't available: https://nodejs.org). After installing, ask them to log in / set up their key, then re-detect.

**Question 3: API key (if needed)**

- **Claude Code via subscription**: No API key needed — the CLI handles auth. Ask them to run `claude` to confirm they're logged in.
- **Gemini CLI**: Ask: *"Do you have a Google Gemini API key? It's free — get one at https://aistudio.google.com (click 'Get API key'). It looks like `AIzaSy...`"* Write it as `GOOGLE_API_KEY=<key>`.
- **OpenAI/Codex**: Ask for their OpenAI API key (https://platform.openai.com/api-keys). Write as `OPENAI_API_KEY=<key>`.

Note: Even if using Claude Code as the brain, a `GOOGLE_API_KEY` is also useful for weather and other background services (optional).

### Auto-generate the session secret:

```bash
./venv/bin/python -c "
import secrets, re, pathlib
env = pathlib.Path('vessence-data/.env')
text = env.read_text()
secret = secrets.token_hex(32)
text = re.sub(r'^SESSION_SECRET_KEY=.*', f'SESSION_SECRET_KEY={secret}', text, flags=re.M)
env.write_text(text)
print('Session secret generated.')
"
```

Tell the user: *"Generated a security key for your session cookies — nothing you need to worry about."*

**Verify:** `grep -E "USER_NAME|JANE_BRAIN" vessence-data/.env` shows non-empty values.

---

## Phase 6 — Link Agent Configuration

Tell the user: *"Connecting your CLI to Jane's identity and protocols. This is what makes your CLI behave as Jane rather than as a generic assistant."*

Based on the detected brain from Phase 5:

```bash
# For Claude Code users:
ln -sf vessence/CLAUDE.md ./CLAUDE.md

# For Gemini CLI users:
ln -sf vessence/GEMINI.md ./GEMINI.md

# For Codex users:
ln -sf vessence/AGENTS.md ./AGENTS.md
```

Create the hooks directory (Claude Code only):
```bash
# Claude Code only — hooks run automatically on each session
mkdir -p .claude/hooks
ln -sf ../../vessence/startup_code/claude_smart_context.py .claude/hooks/context_build.py 2>/dev/null || true
```

**Verify:** `ls -la CLAUDE.md` (or GEMINI.md / AGENTS.md) shows a symlink.

---

## Phase 7 — Start Jane (Test Run)

Tell the user: *"Let's do a quick test to make sure everything's working before we set up auto-start."*

```bash
export VESSENCE_HOME=$(pwd)/vessence
export VESSENCE_DATA_HOME=$(pwd)/vessence-data
export VAULT_HOME=$(pwd)/vault
export ESSENCES_DIR=$(pwd)/essences

cd vessence
../venv/bin/python -m uvicorn jane_web.main:app \
    --host 127.0.0.1 --port 8081 --log-level warning &
SERVER_PID=$!
cd ..

sleep 4
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/ 2>/dev/null)
kill $SERVER_PID 2>/dev/null
wait $SERVER_PID 2>/dev/null
```

- If `HTTP_STATUS` is `200` or `302`: ✓ server works. Tell the user and continue.
- If it fails: read the server output, diagnose, and fix before moving on. Common issues: port 8081 already in use (`lsof -i :8081`), missing `.env`, import errors.

---

## Phase 8 — Auto-Start on Boot

Tell the user: *"Setting up Jane to start automatically when your computer boots, so it's always available."*

Detect the OS:
```bash
uname -s   # Linux or Darwin (macOS)
```

### Linux (systemd) — most common:

```bash
REPO_ROOT=$(pwd)
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/jane-web.service << SVCEOF
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

systemctl --user daemon-reload
systemctl --user enable jane-web.service
systemctl --user start jane-web.service
loginctl enable-linger $(whoami)
```

**Verify:** `systemctl --user status jane-web.service` shows `active (running)`.

### macOS (launchd):

```bash
REPO_ROOT=$(pwd)
mkdir -p ~/Library/LaunchAgents

cat > ~/Library/LaunchAgents/com.vessence.jane-web.plist << PLISTEOF
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

launchctl load ~/Library/LaunchAgents/com.vessence.jane-web.plist
```

**Verify:** `launchctl list | grep vessence` shows the service.

---

## Phase 9 — Remote Access (Optional)

Tell the user:

> *"Jane is now running locally at http://localhost:8081. If you want to access her from your phone or tablet — from anywhere, not just at home — I can set up a permanent public URL for you through the Vessences relay network.*
>
> *The relay forwards encrypted traffic to your machine. It never stores or reads your data. Would you like to set this up? (y/n)"*

If **yes**:
```bash
cd vessence && ../venv/bin/python relay_client.py --setup
```

This will guide the user through:
1. Picking a username (their permanent URL will be `https://USERNAME.vessences.com`)
2. Creating a password for future logins
3. Connecting the tunnel

After setup, create a persistent service for the relay (same pattern as Phase 8, using `relay_client.py --auto` as the ExecStart).

Tell the user: *"Your Jane is now accessible at https://USERNAME.vessences.com. Use that URL in the Android app settings."*

If **no**: *"No problem. You can always set this up later by running `python vessence/relay_client.py --setup` from the repo root."*

---

## Phase 10 — Get to Know the User

Tell the user: *"Jane is running. Before you open the web UI, I'd like to ask you a few quick questions so Jane already knows you when you first meet her. You can skip anything you don't feel like answering."*

Ask these **one at a time** in a warm, natural tone. For each answer, save it immediately:

```bash
./venv/bin/python vessence/agent_skills/add_fact.py "<fact>" --topic <topic>
```

1. **Name/nickname** — *"What should Jane call you?"*
   - Save: `--topic identity --subtopic name`
   - Also update `USER_NAME` in `vessence-data/.env` if different from Phase 5

2. **Profession** — *"What do you do for work — or are you a student?"*
   - Save: `--topic identity --subtopic profession`

3. **Interests** — *"What are your hobbies or interests?"*
   - Save each: `--topic interests`

4. **How to talk** — *"How do you like to be talked to? Quick and direct? Detailed? Casual?"*
   - Save: `--topic preferences --subtopic communication_style`

5. **Location** — *"What city or timezone are you in? Useful for weather and scheduling."*
   - Save: `--topic identity --subtopic location`

6. **Goals** — *"Is there anything specific you want Jane to help you with — projects, routines, anything?"*
   - Save: `--topic projects`

7. **Optional — family** — *"Anything about your family or living situation you'd like Jane to know? Completely optional."*
   - Save if answered: `--topic family`

After the last question, say:

> *"Got it — Jane knows the basics about you now. This carries across all sessions and devices. You can always tell her new things and she'll remember, or ask her to forget something.*
>
> **Open http://localhost:8081 in your browser to start talking to Jane.** She'll already know your name."*

---

## Phase 11 — Wrap Up

Tell the user a brief summary of what was set up:

> *"Here's what's running:*
> - *Jane web UI: http://localhost:8081*
> - *Brain: [their chosen CLI]*
> - *Auto-starts on boot: yes*
> - *Remote access: [yes at https://USERNAME.vessences.com / no, local only]*
>
> *A few useful things to know:*
> - *To update Jane: `git pull && ./venv/bin/pip install -r vessence/requirements.txt` then restart*
> - *Logs: `journalctl --user -u jane-web.service -f` (Linux) or `tail -f vessence-data/logs/jane-web.log` (macOS)*
> - *Android app: download from https://vessences.com/downloads — enter your server URL in settings*
>
> *Is there anything you'd like to adjust or ask about before we finish?"*

---

## Rules for the CLI

- **Never skip a phase if verification fails** — diagnose and fix it first.
- **Explain what you're doing** — the user should always know what's happening and why.
- **All runtime data goes in `vessence-data/`** — never write user data into `vessence/` (that's code only).
- **The `.env` file lives at `vessence-data/.env`**, not `vessence/.env`.
- **If you hit an error you can't fix**, show the user the exact error, explain what it means in plain English, and ask them to paste it into https://github.com/endsley/vessence/issues.
