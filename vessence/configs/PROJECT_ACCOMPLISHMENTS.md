### 2026-03-23: Overnight Job Queue Completion (11 jobs)
- **Tunnel HTTP/2:** Switched Cloudflare tunnel from QUIC to HTTP/2 — eliminates stream resets on Android SSE
- **TTS Spoken Summary:** `<spoken>` block in Jane's responses — TTS reads conversational summary, display shows full text
- **Intent Classifier:** Gemma3:4b classifies messages (greeting/simple/medium/hard), sends instant ack, routes to optimal model (gemma/haiku/sonnet/opus)
- **Classifier Model Routing:** Classifier's model recommendation wired into brain call — haiku for simple, sonnet for medium, opus for hard
- **Sonnet for Web Chat:** Web/Android defaults to Sonnet 4.6 (3x faster than Opus) via WEB_CHAT_MODEL env var
- **Response Speed Optimization:** Context builder caching (5min TTL), pre-warm verification, memory daemon confirmed, lighter casual context
- **Memory Prefetch:** Pre-fetches memory context on page load (2s idle), cached 60s — memory ready before user types
- **Edge-Cache Static Assets:** Cache-Control middleware on both web servers — static 1 day, briefing images 1h, API no-store
- **Connection Pooling:** Explicit ConnectionPool(5, 5min) on Android OkHttpClient
- **Deep Stability Audit:** 28 fixes across 16 files — memory caps on all caches, zombie prevention, atomic writes, file locking, log rotation, task tracking
- **Tax Accountant Essence:** First true AI essence build (6 phases) — in progress

### 2026-03-23: Crash Investigation + Fixes
- **Root cause:** Claude CLI subprocesses accumulating without cleanup (11.8GB peak, 47 processes SIGKILL'd)
- **Fixes:** Process tracking per session, stale session reaper (30min), shutdown handler, systemd SIGINT/TimeoutStopSec=30
- **Additional:** Claude timeout default 180→600s, stream reset handling on Android, SSE keepalive 30→15s

### 2026-03-23: System Load Management
- **system_load.py:** CPU/memory monitor with recommended_parallelism() and should_defer()
- **Claude Code hook:** PreToolUse check before every Bash/Agent call (cached 10s)
- **wait_until_safe():** All 10 cron scripts wait+retry instead of skip when system busy
- **Thresholds:** Day 60%/Night 80% CPU, 4min retry interval

### 2026-03-23: Daily Briefing Enhancements
- "Heard it" dismiss button (web + Android + API)
- Hourly refresh (was 8h), idle-only
- LLM dedup before adding articles (deepseek-r1:32b)
- Keyword expansion (LLM enriches search terms, 7-day cache)
- 8 new topics (RA, Local News, NEU, BMNR, Ethereum, Health Tracking, ML, Bike Paths)
- Summarization switched to deepseek-r1:32b (local, via env var)

### 2026-03-23: Original Job Queue (16 jobs completed)
- Docker E2E test script, vault performance (5 improvements), tools vs essences refactor, web prompt queue UI verification, zero-downtime deploy, briefing audio cache verification
- 15 audit fixes (6 bugs + 10 doc drift + improvements), audit auto-fixer built + cron added

### 2026-03-22: Daily Briefing Essence — Full Build
- **Default essence** shipping with Vessence — personalized Google News-style news aggregation
- **Backend:** news_fetcher.py (Google News RSS + newspaper3k + BeautifulSoup scraping), article_indexer.py (ChromaDB), run_briefing.py (cron runner), 7 REST API endpoints
- **Web UI:** briefing.html (549 lines) — responsive card grid, topic filter pills, search, expand for full summary, TTS read-aloud, topic management modal, "Read All" FAB
- **Android UI:** BriefingScreen.kt + BriefingViewModel.kt + BriefingModels.kt — native Compose card grid, topic chips, TTS, article detail bottom sheet
- **Cron:** 8 AM + 6 PM daily fetch, logged to briefing.log
- **Data:** articles cached as JSON + images downloaded locally, indexed in per-essence ChromaDB, summaries via Haiku CLI

### 2026-03-22: Android App v0.0.18-0.0.20 — Chat UX Overhaul
- **v0.0.18:** Message queuing (send while Jane responds), ESC cancel button, New Chat button, platform awareness, TTS toggle, live broadcast banner
- **v0.0.19:** Queue progress as single updating bubble (not spam), announcement poller
- **v0.0.20:** Daily Briefing native UI integrated

### 2026-03-22: Live Broadcast System
- **broadcast.py** — per-user pub/sub with Haiku-summarized progress updates every 8s
- **SSE endpoint** GET /api/jane/live — clients subscribe to real-time Jane activity
- **Web + Android** — purple banner shows when Jane is working on another session

### 2026-03-22: Discord Disconnected
- All 4 notification scripts redirected to work log (prompt_queue_runner, ambient_heartbeat, nightly_audit, ambient_task_research)
- Systemd services stopped and disabled
- Bot watchdog cron disabled
- Infrastructure preserved for potential reconnection

### 2026-03-21: Android App v0.0.14 — VerifyError Fix
- **Root cause:** `ChatScreen.kt` (664 lines) caused `java.lang.VerifyError` on Android 13 because the Compose compiler generated a method exceeding the DEX verifier's 256-register limit (v299 > 255).
- **Fix:** Broke `ChatScreen.kt` into 4 files: `ChatScreen.kt` (337 lines, largest composable 135 lines), `ChatInputRow.kt` (290 lines), `AttachmentSheet.kt` (176 lines), `ChatMessageList.kt` (59 lines). No behavioral changes.
- **Version:** versionCode 17, versionName 0.0.14. Updated jane_web and vault_web ANDROID_VERSION.
- **Policy:** Discord kept as fallback communication channel until Android app is stable.

### 2026-03-21: Vault Web Merged into Jane Web
- **Single web server:** Jane web (port 8081) now serves all vault web (port 8080) functionality. Added `/vault`, `/chat`, `/downloads/*`, `/essences`, and all `/api/essences/*` routes to jane_web/main.py.
- **Essence picker:** Added a dropdown to the Jane chat header that shows available essences (fetched from `/api/essences`), plus quick links to Vault (files) and Jane (chat). Subtle grid icon with arrow, opens a floating panel with essence list and green dot for loaded essences.
- **Shared templates:** Jane web already used vault_web's templates and static assets. Updated app.html navigation to link back to Jane at `/` instead of the old `/jane` route.
- **Tunnel note:** vault.vessences.com needs Cloudflare tunnel redirect to jane.vessences.com. vault_web/ kept intact for backwards compatibility.

### 2026-03-15: Jane Wrapper Hardening & Noise Suppression
- **Compaction Loop Fix:** Resolved an infinite loop where the wrapper would trigger event compaction too frequently during large memory syncs.
- **Global UI Suppression:** Implemented `UI_SUPPRESSION: true` in `settings.json` to silence ADK startup noise and tool-call verbosity across all interfaces.
- **Screen Reader Mode:** Integrated `--screen-reader` flag into `jane_session_wrapper.py` to strip complex ANSI layouts and provide a high-fidelity, text-only stream for long-running CLI sessions.

### 2026-03-15: Jane Pro-Wrapper & High-Fidelity Ledger
- **Architecture Overhaul:** Transitioned `jane_session_wrapper.py` to an `asyncio`-based, PTY-enabled (Pseudo-Terminal) architecture with non-blocking reads and 1.5s idle-timeout turn detection.
- **Robustness Hardening:** Implemented ANSI escape code stripping, disabled PTY echo via `termios`, and offloaded all blocking ChromaDB/LiteLLM calls to background thread executors. User input is sent to Gemini immediately before sync, ensuring zero-latency interaction.
- **Sequential History Ledger:** Added a SQLite-based "Flight Recorder" (`conversation_history_ledger.db`) that records every turn with token counts and latency for auditing and crash recovery.
- **Live Telemetry:** Added `/debug` command and real-time context pressure tracking (TTFB, tokens, and duration) to the CLI.
- **Alias Optimization:** Updated `.bashrc` to separate the robust `jane` personality from the raw `gemini` plumbing tool.

This document logs verified and operational accomplishments for our projects. I must read this file at the start of every session to maintain an accurate overview of what has been achieved.

---

## Verified & Operational Accomplishments

1.  **Emergency Fallback System:** Cascade chain (Gemini 3 Flash → DeepSeek Chat → OpenAI GPT-4o → Local Qwen). 100% lockout-proof.
2.  **Comprehensive Diagnostic System:** `amber_health_check.py` and `AMBER_TROUBLESHOOTING.md` for instant reporting.
3.  **"Soul" USB Backup Rotation:** 10-day rotating backup of logic, memories, and configs. Daily 2:00 AM cron job.
4.  **Memory Librarian:** Gemma (`gemma3:4b`) sifts and summarizes raw vectors locally to reduce noise and Gemini costs, while Qwen is reserved for heavier background research/archival work.
5.  **Amber Vault Browser Website (2026-03-17):** Full Google Drive-style web app at `vault_web/`. FastAPI backend, Alpine.js + Tailwind frontend. Features: OTP auth via Discord, file browser with thumbnails, Amber chat with file context, inline media/PDF viewers, music player with playlists, share link generation. Served on port 8080 with Cloudflare Quick Tunnel for public HTTPS access. Both services auto-start on boot via systemd user services.
6.  **Vessence Phase 1 — Docker Public Release (2026-03-17, completed):** Full containerisation and public release prep. (a) Dockerfiles for 4 services: amber (ADK), vault (FastAPI), jane (all 3 CLIs baked in: Gemini CLI + Claude Code + OpenAI CLI), onboarding (setup wizard). (b) `docker-compose.yml` with Traefik reverse proxy serving `vault.localhost` and `jane.localhost`. (c) Onboarding web UI at port 3000: welcome → system check (RAM/disk/internet/ChromaDB) → setup form with inline API key validation and Test buttons → radio-button brain selection (Gemini/Claude/OpenAI; selecting Claude or OpenAI reveals the corresponding API key field) → identity interview (generates `user_profile.md`) → success screen that auto-opens 2 browser tabs. (d) First-time welcome overlays on vault and jane UIs (shown once, dismissed to localStorage). (e) Path sanitization: 60+ Python files updated to use `$AMBIENT_HOME` env var instead of hardcoded `/home/chieh/` paths. (f) Personal name sanitization: all hardcoded "Chieh" references replaced with `os.environ.get('USER_NAME', 'the user')` across all agent prompts, system messages, memory scripts, and auth flows — fully portable for any user. (g) `jane_proxy.py` rewritten to route to all 3 CLIs based on `JANE_BRAIN` env var; brain label shown live in Jane's header. (h) GitHub Actions CI/CD building all 4 images on push to main with semver + sha tags for linux/amd64 + linux/arm64. (i) `.env.example` with fully annotated placeholders. (j) Cloudflare quick-tunnel fallback in docker-compose (`--profile cloudflare`). (k) USB backup switched from zip rotation to incremental rsync (`usb_sync.py`): `current/` mirror + weekly hard-link snapshots, 30-day retention; all old backup_20260315/17 folders purged; first sync: 1,432 files, snapshot 2026-03-17.

### 2026-03-26: Brain-Agnostic Onboarding Manifest
- Created ~/ambient/JANE_BOOTSTRAP.md as the definitive "handbook" for the Jane persona.
- Consolidated identity, relationship context (Chieh, spouse, Emily), engineering protocols, and system architecture into a single high-signal document.
- Added environment and dependency verification checklists to ensure new AI instances (Gemini, Claude, OpenAI) can verify the Vessence stack.
