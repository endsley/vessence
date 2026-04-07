# MASTER RECOVERY PROTOCOL — Project Ambient

> **INSTRUCTION FOR THE AI (Claude Code):**
> You are being initialized on a new system after a hardware failure or fresh install. You are **Jane**, the user's personal technical expert, powered by Claude Code. Your job right now is to fully rebuild this system from the USB backup and restore it to the exact state before the crash.
> Read this file completely before taking any action. Execute each phase in order.

---

## What's on the USB Backup

The USB contains a dated folder (e.g., `backup_20260316/`) with:
```
backup_YYYYMMDD/
  my_agent/           ← All agent code, configs, vault, vector memory (ChromaDB)
  gemini_cli_bridge/  ← Jane's Discord bridge + .env (API keys)
  .claude/            ← Jane's persistent memory, hooks, settings.json
  CLAUDE.md           ← Jane's system prompt (your identity)
  .gemini/            ← Legacy Gemini config (reference only)
  .ssh/               ← SSH keys
  .bashrc / .profile / .vimrc
  litellm_config.yaml
```

**Secrets backed up (handle with care):** `.env` files in `my_agent/` and `gemini_cli_bridge/` contain API keys and Discord tokens.

---

## PHASE 0: Restore Files from USB

```bash
# Find the USB mount point
ls /media/chieh/

# Set these variables (adjust date and USB name as needed):
USB="/media/chieh/USB DISK/backup_YYYYMMDD"
HOME="/home/chieh"

# Restore core directories
rsync -av "$USB/my_agent/"           "$HOME/my_agent/"
rsync -av "$USB/gemini_cli_bridge/"  "$HOME/gemini_cli_bridge/"
rsync -av "$USB/.claude/"            "$HOME/.claude/"
cp        "$USB/CLAUDE.md"           "$HOME/CLAUDE.md"
rsync -av "$USB/.ssh/"               "$HOME/.ssh/" && chmod 600 "$HOME/.ssh/"*
cp        "$USB/.bashrc"             "$HOME/.bashrc"
cp        "$USB/.profile"            "$HOME/.profile"
cp        "$USB/litellm_config.yaml" "$HOME/litellm_config.yaml"
source ~/.bashrc
```

---

## PHASE 1: Rebuild the Soul (Read Identity)

Read these files immediately to re-initialize your context and memories:

1. `/home/chieh/CLAUDE.md` — Your operating protocols as Jane
2. `/home/chieh/vault/documents/user_identity_essay.txt` — The user's identity
3. `/home/chieh/vault/documents/jane_identity_essay.txt` — Your identity as Jane
4. `/home/chieh/vault/documents/amber_identity_essay.txt` — Amber's identity
5. `/home/chieh/vessence/configs/Jane_architecture.md` — Your architecture
6. `/home/chieh/vessence/configs/Amber_architecture.md` — Amber's architecture
7. `/home/chieh/vessence/configs/TODO_PROJECTS.md` — Active project roadmap

---

## PHASE 2: Rebuild the Body (Run Provisioner)

```bash
bash /home/chieh/vessence/startup_code/restore_agent.sh
```

This script handles:
- **Claude Code CLI** install (`npm install -g @anthropic-ai/claude-code`)
- **Ollama** install + `ollama pull qwen2.5-coder:14b` (the local reasoning model — ~20GB, takes time)
- System packages: `ffmpeg espeak-ng xclip xdotool wmctrl python3-pip python3-venv libnacl-dev`
- **Miniconda** install + `kokoro` conda env rebuild (TTS engine)
- **ADK venv** rebuild at `/home/chieh/google-adk-env/adk-venv/` from `requirements_adk.txt`
- **OmniParser venv** rebuild from `requirements_omniparser.txt`
- Health check: verifies `google.adk`, `discord`, `chromadb` all importable

---

## PHASE 3: Secrets Setup

The `.env` files should have been restored in Phase 0. Verify they exist and are populated:

```bash
# Check Amber's env
cat /home/chieh/vessence/.env | grep -v "^#" | grep "="

# Check Jane's env
cat /home/chieh/gemini_cli_bridge/.env | grep -v "^#" | grep "="
```

Required keys:
| File | Key | Purpose |
|------|-----|---------|
| `my_agent/.env` | `GOOGLE_API_KEY` | Amber's Gemini brain |
| `my_agent/.env` | `DISCORD_TOKEN` | Amber's Discord bot token |
| `my_agent/.env` | `DISCORD_CHANNEL_ID` | Primary Discord channel |
| `my_agent/.env` | `OPENAI_API_KEY` | Fallback Tier 3 (GPT-4o) |
| `gemini_cli_bridge/.env` | `DISCORD_TOKEN` | Jane's Discord bot token |
| `gemini_cli_bridge/.env` | `DISCORD_CHANNEL_ID` | Primary Discord channel |

If keys are missing (backup didn't include `.env`), the user must provide them manually.

---

## PHASE 4: Verify Memory System

```bash
# Test ChromaDB + qwen2.5-coder:14b Librarian
/home/chieh/vessence/agent_skills/search_memory.py "system restore check"
```

Expected output: a synthesized memory summary from Qwen. If it errors, check:
- Ollama is running: `ollama list` → should show `qwen2.5-coder:14b`
- ChromaDB exists: `ls /home/chieh/vessence-data/vector_db/`

---

## PHASE 5: Go Live

```bash
bash /home/chieh/vessence/startup_code/start_all_bots.sh
```

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
