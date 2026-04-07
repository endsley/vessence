# JANE_BOOTSTRAP.md — New User Setup Guide

**You are an AI CLI assistant helping a new user set up Vessence.** Follow these phases in order. Each phase has verification steps — do not proceed until verification passes. All paths are relative to this repository root (the directory containing this file).

**What is Vessence?** Vessence is an open-source wrapper around Claude Code, Gemini CLI, and Codex that simplifies AI agent development. You start with a default agent called Jane. By describing abilities you want, you develop tools (capabilities like sending texts, controlling lights, playing music) and essences (personas like a tax accountant or fitness coach). You can also download tools and essences that others have built from the Vessence marketplace.

---

## Architecture Overview

Before you begin, understand what you are setting up:

- **Jane** — An AI assistant persona powered by whichever CLI brain the user chooses (Gemini, Claude, or OpenAI).
- **Vault** — Personal file storage (documents, photos, music).
- **Essences** — Specialized AI personas (e.g., tax accountant, fitness coach). Each essence gives Jane domain expertise. Think of them as downloadable "brains" that transform Jane into a specialist.
- **Tools** — Capability plugins (daily briefing, music player, SMS, smart home control, etc.) that extend what Jane can do. Tools are shared across all essences.
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

## Phase 1: System Requirements Check

Verify the following are installed and meet minimum versions:

```bash
python3 --version   # Must be 3.11+
node --version      # Must be 22+
git --version       # Any recent version
```

Detect the operating system:
```bash
uname -s   # Expected: Linux, Darwin (macOS), or Linux under WSL
```

If on WSL, confirm:
```bash
cat /proc/version   # Should contain "Microsoft" or "WSL"
```

**Verification:** All three tools are installed and meet version requirements. Report the OS to the user.

**If any requirement is missing:** Tell the user exactly what to install and how, then wait for them to confirm before proceeding.

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
mkdir -p vault
mkdir -p essences
mkdir -p tools
```

Add `.gitkeep` files to empty plugin directories:

```bash
touch essences/.gitkeep
touch tools/.gitkeep
```

**Verification:** Confirm the directories exist:
```bash
ls -d vessence-data/memory/v1/vector_db vessence-data/logs vessence-data/credentials vault essences tools
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

2. **`GOOGLE_API_KEY`** — Required for Gemini mode (the default and free option).
   - Get one free at: https://aistudio.google.com -> Get API key -> Create API key
   - Looks like: `AIzaSy...` (39 characters)

3. **`SESSION_SECRET_KEY`** — Generate automatically, do not ask the user:
   ```bash
   ./venv/bin/python -c "import secrets; print(secrets.token_hex(32))"
   ```
   Write the output into the `.env` file.

### Optional values (tell the user they can fill these in later):

- `ANTHROPIC_API_KEY` — For Claude mode. Get at: https://console.anthropic.com
- `OPENAI_API_KEY` — For OpenAI mode. Get at: https://platform.openai.com/api-keys
- `DISCORD_TOKEN` — For Discord integration. Get at: https://discord.com/developers
- `VAULT_PASSWORD` — Web UI login password. Leave blank to be prompted on first login.

**Verification:** The `.env` file exists at `vessence-data/.env` and contains non-empty values for `USER_NAME`, `GOOGLE_API_KEY`, and `SESSION_SECRET_KEY`.

---

## Phase 6: Install CLI Brain

Jane's intelligence comes from whichever AI CLI the user is running. Detect which one is available and set `JANE_BRAIN` in the `.env` file:

- If the user is running **Claude Code** → set `JANE_BRAIN=claude`
- If the user is running **Gemini CLI** → set `JANE_BRAIN=gemini`
- If the user is running **Codex CLI** → set `JANE_BRAIN=openai`

If multiple are available, ask the user which they prefer. If none are globally installed, install the one matching the API key they provided:

```bash
# Gemini (default — free tier available):
npm install -g @google/gemini-cli

# Claude:
npm install -g @anthropic-ai/claude-code

# OpenAI/Codex:
npm install -g @openai/codex
```

Update `JANE_BRAIN` in `vessence-data/.env` to match.

**Verification:** The chosen CLI is installed and callable from the terminal. The `JANE_BRAIN` value in `.env` matches.

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

Start the web server:

```bash
cd vessence && ../venv/bin/python -m uvicorn jane_web.main:app --host 0.0.0.0 --port 8081
```

Or, to run it in the background:

```bash
cd vessence && nohup ../venv/bin/python -m uvicorn jane_web.main:app --host 0.0.0.0 --port 8081 > ../vessence-data/logs/jane-web.log 2>&1 &
```

**Verification:**
```bash
curl -s http://localhost:8081/health
```
Should return a 200 response. If it fails, check `vessence-data/logs/jane-web.log` for errors.

---

## Phase 9: Remote Access (Guided — User Does This)

Tell the user:

> Your server is running locally at http://localhost:8081. To access Jane from your phone or another device, you can set up a Cloudflare Tunnel:
>
> 1. Create a free account at https://dash.cloudflare.com
> 2. Go to Zero Trust -> Networks -> Tunnels -> Create tunnel
> 3. Install `cloudflared` on this machine (instructions at https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
> 4. Create a tunnel pointing to `localhost:8081`
> 5. Your public URL will be something like `jane.yourdomain.com`
> 6. Put this URL in the Android app's settings
>
> This step is optional. Skip it if you only want to use Jane on this machine.

Do not attempt to install or configure Cloudflare automatically. This step requires the user's own domain and Cloudflare account.

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

### After the interview:

Tell the user:

> "Great, I've got all of that saved. I'll remember everything across sessions — web, CLI, and Android all share the same memory. You can always tell me new things and I'll remember them, or ask me to forget something.
>
> Try opening http://localhost:8081 in your browser to chat with me through the web interface. Everything is set up and ready to go."

**Verification:** The web UI loads, the user can send a message, and Jane responds with awareness of the onboarding facts (e.g., uses their name).

---

## Important Rules for the CLI

- **All paths are relative to the repo root** — wherever the user cloned the repository.
- **Never store runtime data in `vessence/`** — that directory is code only, tracked by git.
- **The `.env` file lives in `vessence-data/.env`**, not in `vessence/.env`.
- **The ChromaDB vector database lives in `vessence-data/memory/v1/vector_db/`**.
- **Seed memories come from `vessence/configs/jane_seed_memories.json`** — do not modify this file during setup.
- **If a phase fails, diagnose and fix it before moving on.** Do not skip phases.
