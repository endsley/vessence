# Master TODO Project List

This document outlines the ongoing projects and future goals. I must read this file at the start of every session to maintain awareness of our priorities.

---

## The North Star: Project Vessence

**Everything below feeds into this ultimate goal.**

Project Vessence is a platform for building a **digital clone and living memory of a person** — a vessel that holds someone's essence. The minor projects below are not independent goals; they are the building blocks of Vessence. Each one makes the clone more capable, more complete, more human.

See full spec: `/home/chieh/vessence/configs/project_specs/vessence.md`

**Phase 1 COMPLETE (2026-03-17):** Dockerfiles, docker-compose (Traefik), onboarding UI, identity interview, path sanitization, GitHub Actions CI/CD, .env.example, Cloudflare quick-tunnel, first-run welcome overlays. Ready to push to Docker Hub and go public.

**Phase 2 (next):** Docker Hub push, public GitHub repo cleanup (remove personal vault files, ChromaDB data), landing page at vessence.ai, beta user feedback.

---

## Building Blocks (feed into Vessence)

### 1. Cross-Platform Native App ⭐ PRIORITY #1
*Vessence contribution: the primary interface for interacting with the digital clone on any device*
- Build a native cross-platform app (Linux, Windows, Android, macOS) with a ChatGPT-identical UI that talks directly to Amber's ADK server.
- Phase 1 (MVP): Core chat UI, dark theme, markdown + code rendering, ADK HTTP client, LAN/localhost connectivity, local conversation history (SQLite), connection status indicator.
- Phase 2 (Streaming & Polish): SSE streaming endpoint on Amber side, word-by-word typewriter animation, file/image attachments, Windows + macOS builds, light/dark theme.
- Phase 3 (Voice): Microphone input → Whisper STT → Amber, Kokoro TTS playback from server, hands-free mode.
- Phase 4 (Remote & Advanced): Tailscale remote access, push notifications / Heart Beat integration, vault browser, optional iOS.
- Reference Document: `/home/chieh/vessence/configs/project_specs/ambient_app.md`

### 2. Local Google Photos Sync & Intelligence
*Vessence contribution: the clone's visual memory — faces, places, life moments stored and recognized*
- Phase 1 (Collector): Google Photos API integration (OAuth2, list_library, download_photo, sync_all with throttling).
- Phase 2 (Analyst): Local facial recognition (DeepFace/dlib, 128-d encodings, identity mapping for User/Wife/Daughter, auto-sorting to family folders, and semantic memory tagging).
- Phase 3 (Pipeline): Android sync app pushing new mobile photos directly to Amber's local FastAPI receiver.

### 3. Secure Git Backup System
*Vessence contribution: the clone must be immortal — resilient to hardware failure, always restorable*
- Initialize private Git repository for core logic (`/my_agent`, `/gemini_cli_bridge`).
- Configure `.gitignore` to protect secrets (`.env`, API keys) and large binary files (`vault/`).
- Automate regular pushes of shared vector database and `CLAUDE.md` to ensure quick recovery after system failure.

### 4. Multi-Modal "See & Do" Automation
*Vessence contribution: the clone can act in the world, not just respond to it*
- Integrate Search Brain and Motor Brain for complex tasks (e.g., flight booking, research).
- Enable Amber to navigate websites autonomously and provide visual summaries via screenshots.

### 5. Unified Action Bridge
*Vessence contribution: one unified identity across all interfaces — the clone feels like one person*
- Create a tool for Jane (Gemini CLI / Claude Code) to trigger actions in Amber (Discord/ADK).
- Achieve "Unified Identity" where both interfaces can command the other's unique tools.

### 6. Proactive Learning & Interactive Training
*Vessence contribution: the clone actively improves its own knowledge — asks, learns, self-corrects*
- Implement a feedback loop where Amber asks for clarification on unknown faces or conflicting facts.
- Use Discord/Telegram as an interactive training interface to improve the local Identity Map.

### 7. Heart Beat (Autonomous Background Loop)
*Vessence contribution: the clone thinks even when not being talked to — it grows on its own*
- Phase 1 (Autonomous Loop): Recurring loop that checks TODO list and decides on proactive tasks.
- Phase 2 (Context Consolidation): Summarizes research findings and updates shared vector memory autonomously.
- Phase 3 (Active Goal Achievement): Initiates and tracks long-running actions, reports via Jane or Amber.

### 8. Always-Listening Voice Mode
*Vessence contribution: hands-free interaction — the clone is always present and ready to respond*
- Trigger word training interface: let users record samples and train a custom wake word (e.g., "Hey Amber").
  - **Spec written:** `configs/project_specs/trigger_word_training.md` — covers dual-backend (Porcupine + OpenWakeWord), in-app recording UI, live test mode, per-essence wake word routing.
- Always-on mic pipeline: low-power keyword detection → full STT → Amber processing.
- Privacy controls: local-only wake word detection, visual/audio indicators when active.

### 9. Voice Cloning
*Vessence contribution: the clone sounds like the person — the most human part of the digital legacy*
- Record and process voice samples from the real person.
- Train or fine-tune a TTS model (e.g. XTTS v2) on their voice.
- Amber speaks in the person's actual voice — not just their words, but their sound.

### 10. Fix Audio Output for Status Updates
- When Jane reads a response aloud (TTS), status update text should not be included in the audio
- Only the actual response text (white text) should be spoken, not the grey intermediate steps
- Applies to both web and Android

### 11. Retrain hey_jane Wake Word Model
- `hey_jane.onnx` is currently broken — always fires false positives
- Using `hey_jarvis_v0.1.onnx` as a stopgap (works well, 0.98+ scores)
- Need to collect clean audio samples and retrain with OpenWakeWord toolkit
- Goal: custom "Hey Jane" model with similar accuracy to hey_jarvis

### 12. Screen-Off Wake Word on OnePlus
- OnePlus battery optimization aggressively kills foreground services
- User must manually disable battery optimization for Vessence in system settings
- No programmatic workaround found — `ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` is not sufficient on OnePlus
- Document this as a known requirement for OnePlus users

### 13. DiagnosticReporter Uses Raw HttpURLConnection
- `DiagnosticReporter.kt` uses raw `HttpURLConnection` instead of `ApiClient` (OkHttp/Retrofit)
- This may not route through the relay properly since it bypasses cookie management
- Should be migrated to use `ApiClient` for consistency and proper auth

### 14. Build Emulator Test Infrastructure for Android
- Attempted to set up Android emulator for automated testing
- Emulator lacks Google Play Services, which breaks Google OAuth and some APIs
- Need to either use a Play Store emulator image or mock the Google dependencies
- Consider Robolectric for unit-level UI tests as alternative

---

## Completed Projects

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
