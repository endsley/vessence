# MASTER RECOVERY PROTOCOL — Project Ambient

> **INSTRUCTION FOR THE AI (Claude Code):**
> You are being initialized on a new system after a hardware failure or fresh install. You are **Jane**, the user's personal technical expert, powered by Claude Code. Your job right now is to fully rebuild this system from the USB backup and restore it to the exact state before the crash.
> Read this file completely before taking any action. Execute each phase in order.

---

## What's on the USB Backup

The USB contains a dated folder (e.g., `backup_20260316/`) with:
```
backup_YYYYMMDD/
  ambient/vessence/   ← All agent code, configs, and ADK runtime files
  ambient/vessence-data/ ← ChromaDB vector memory and runtime logs
  ambient/vault/      ← Vault documents and uploaded assets
  gemini_cli_bridge/  ← Jane's Discord bridge + .env (API keys)
  .claude/            ← Jane's persistent memory, hooks, settings.json
  CLAUDE.md           ← Jane's system prompt (your identity)
  .gemini/            ← Legacy Gemini config (reference only)
  .ssh/               ← SSH keys
  .bashrc / .profile / .vimrc
  litellm_config.yaml
```

**Secrets backed up (handle with care):** `.env` files in `ambient/vessence/` and `gemini_cli_bridge/` contain API keys and Discord tokens.

---

## PHASE 0: Restore Files from USB

```bash
# Find the USB mount point (or set USB root manually)
ls /media/$USER/

# Set these variables (adjust date and USB name as needed):
AMBIENT_BASE="${AMBIENT_BASE:-$HOME/ambient}"
VESSENCE_HOME="${VESSENCE_HOME:-$AMBIENT_BASE/vessence}"
VESSENCE_DATA_HOME="${VESSENCE_DATA_HOME:-$AMBIENT_BASE/vessence-data}"
USB="${USB_ROOT:-/media/$USER/USB DISK}/backup_YYYYMMDD"

# Restore core directories
rsync -av "$USB/my_agent/"           "$VESSENCE_HOME/"
rsync -av "$USB/gemini_cli_bridge/"  "$HOME/gemini_cli_bridge/"
rsync -av "$USB/.claude/"            "$HOME/.claude/"
cp        "$USB/CLAUDE.md"           "$HOME/CLAUDE.md"
rsync -av "$USB/.gemini/"            "$HOME/.gemini/"
rsync -av "$USB/.ssh/"               "$HOME/.ssh/" && chmod 600 "$HOME/.ssh/"*
cp        "$USB/.bashrc"             "$HOME/.bashrc"
cp        "$USB/.profile"            "$HOME/.profile"
cp        "$USB/.vimrc"              "$HOME/.vimrc"
cp        "$USB/litellm_config.yaml" "$HOME/litellm_config.yaml"
source ~/.bashrc
```

---

## PHASE 1: Rebuild the Soul (Read Identity)

Read and apply the startup sequence from
[`../configs/JANE_INITIALIZATION_SEQUENCE.md`](../configs/JANE_INITIALIZATION_SEQUENCE.md). That file is the canonical list of identity, architecture, and active priorities to re-establish before work.

---

## PHASE 2: Rebuild the Body (Run Provisioner)

Use the restore entry point documented in
[`../configs/STARTUP_REFERENCE.md`](../configs/STARTUP_REFERENCE.md).

This script handles:
- **Claude Code CLI** install (`npm install -g @anthropic-ai/claude-code`)
- **Ollama** install + `ollama pull qwen2.5-coder:14b` (the local reasoning model — ~20GB, takes time)
- System packages: `ffmpeg espeak-ng xclip xdotool wmctrl python3-pip python3-venv libnacl-dev`
- **Miniconda** install + `kokoro` conda env rebuild (TTS engine)
- **ADK venv** rebuild at `$HOME/google-adk-env/adk-venv/` from `requirements_adk.txt`
- **OmniParser venv** rebuild from `requirements_omniparser.txt`
- Health check: verifies `google.adk`, `discord`, `chromadb` all importable

---

## PHASE 3: Secrets Setup

The `.env` files should have been restored in Phase 0. Verify they exist and are populated:

```bash
# Check Amber's env
cat "$VESSENCE_HOME/.env" | grep -v "^#" | grep "="

# Check Jane's env
cat "$HOME/gemini_cli_bridge/.env" | grep -v "^#" | grep "="
```

Required keys:
| File | Key | Purpose |
|------|-----|---------|
| `ambient/vessence/.env` | `GOOGLE_API_KEY` | Amber's Gemini brain |
| `ambient/vessence/.env` | `DISCORD_TOKEN` | Amber's Discord bot token |
| `ambient/vessence/.env` | `DISCORD_CHANNEL_ID` | Primary Discord channel |
| `ambient/vessence/.env` | `OPENAI_API_KEY` | Fallback Tier 3 (GPT-4o) |
| `gemini_cli_bridge/.env` | `DISCORD_TOKEN` | Jane's Discord bot token |
| `gemini_cli_bridge/.env` | `DISCORD_CHANNEL_ID` | Primary Discord channel |

If keys are missing (backup didn't include `.env`), the user must provide them manually.

---

## PHASE 4: Verify Memory System

```bash
# Test ChromaDB + qwen2.5-coder:14b Librarian
"$VESSENCE_HOME/agent_skills/search_memory.py" "system restore check"
```

Expected output: a synthesized memory summary from Qwen. If it errors, check:
- Ollama is running: `ollama list` → should show `qwen2.5-coder:14b`
- ChromaDB exists: `ls "$VESSENCE_DATA_HOME/vector_db/"`

---

## PHASE 5: Go Live

Use the canonical startup command from
[`../configs/STARTUP_REFERENCE.md`](../configs/STARTUP_REFERENCE.md)
so launch behavior is described once.

This starts:
1. Amber ADK server on `localhost:8000`
2. Amber Discord bridge (`discord_bridge.py`)
3. Jane Discord bridge (`gemini_cli_bridge/bridge.py` → calls `claude -p`)

---

## PHASE 6: Announce Completion

Once everything is verified, send a Discord message (or tell the user directly):

> "Restore complete. Identity synced from backup. Memory system live. Amber and I are both online and ready to resume. All systems nominal."

---

## Known Limitations After Restore

| Item | Status | Action |
|------|--------|--------|
| Ollama models | Re-downloaded (not in backup — too large) | `ollama pull qwen2.5-coder:14b` (done by restore_agent.sh) |
| OmniParser weights | May be missing if not in backup | Download from HuggingFace: `microsoft/OmniParser` |
| Kokoro TTS weights | Rebuilt by conda env | Verify with: `python -c "import kokoro; print('ok')"` |
| Identity essays | Restored from vault | May be outdated if backup is old — regenerate with `generate_identity_essay.py` |
| Short-term session DB | Not backed up (ephemeral) | Normal — long-term ChromaDB memories are preserved |
| Claude Code auth | Requires re-login | Run `claude` and follow auth prompt |
