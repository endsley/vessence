# Master TODO Project List

This document outlines the ongoing projects and future goals. I must read this file at the start of every session to maintain awareness of our priorities.

Source of truth: mirrored from the personal Google Doc TODO list.

---

## Do it Immediately

1. Deal with some important email.

## For my students

1. Write the recommendation letter.

## For our Home

1. Put the TV from Kathia's room to the gym.
2. Clean downstairs.

## For the clinic

1. Curtain rods at Kathia's clinic.
2. The wooden block for the door at the clinic.

## Ambient project goals

1. Set it up so users simply use their Claude Code, or Gemini CLI, to run Jane.
2. Let the user have an easy web/Android Jane by registering an account — just their Google auth is enough.

---

## Completed Projects

### ✅ Secure Git Backup System (completed 2026-04)
- USB rsync rotation with incremental snapshots (`usb_sync.py`)
- `auto_pull.sh` cron job keeps vessence in sync with origin
- `.gitignore` protects secrets and large binaries

### ✅ Heart Beat — Autonomous Background Loop (completed 2026-04)
- 1 AM orchestrator runs all self-improvement jobs in sequence
- Dead code auditor, doc drift auditor, pipeline audit, transcript quality review all live
- Process watchdog cron kills zombies every 5 min

### ✅ Always-Listening Voice Mode (completed 2026-04)
- Wake word detection on Android with OpenWakeWord (`hey_jarvis_v0.1.onnx`, 0.98+ scores)
- Always-on mic pipeline: keyword detection → STT → Jane processing
- Privacy controls: local-only detection, visual indicators when active
- Trigger word training spec written (`configs/project_specs/trigger_word_training.md`)

### ✅ Fix Audio Output for Status Updates (completed 2026-04)
- `<spoken>` tag system separates TTS audio from full display text
- Status updates (grey text) excluded from TTS — only response text is spoken
- Works on both web and Android

### ✅ Amber Vault Browser Website (completed 2026-03-17)
*Vessence contribution: the vault is the person's digital life — photos, documents, audio, memories*
- Google Drive-style personal file browser for `/home/chieh/vessence/vault/`
- Hosted locally on port 8080, exposed via Cloudflare Quick Tunnel
- 4-tab UI: Vault, Chat, Music, Settings
- Location: `/home/chieh/vessence/vault_web/`

---

## Project Vessence — Full Spec

**Vision:** Vessel + Essence. A container that holds someone's essence.

**Product arc:**
- Year 1: Personal assistant that knows you
- Year 3: Digital companion that thinks like you
- Year 10: A vessel loved ones can talk to after someone is gone

**Key decisions:**
- Default: 1 Google API key (Gemini CLI for Jane, Gemini Flash for Amber, Gemini Flash Lite for memory)
- Advanced: Claude Code as Jane's brain (Anthropic API key, opt-in)
- Core stack: Docker Compose — works on Windows, Mac, Linux
- Ollama: advanced settings only (not required for core)
- Kokoro TTS, OmniParser, screen dimmer: excluded from Vessence (Project Ambient only)
- License: MIT

Reference Document: `/home/chieh/vessence/configs/project_specs/vessence.md`
