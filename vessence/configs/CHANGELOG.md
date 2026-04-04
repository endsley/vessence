# Vessence Changelog

## v0.0.43 (2026-03-25)
- **Docker rebuild:** Packaging all v0.0.42 features into Docker images
- **Download package optimized:** 210 MB compressed (Jane + Onboarding)
- **Security verified:** No personal data, cleaned paths, hardened .dockerignore

## v0.0.42 (2026-03-24)
- **Standing Brain:** 3 long-lived CLI processes (haiku/sonnet/opus) via stream-json — eliminates subprocess spawn per message
- **Context caching:** Turn 2+ skips context build entirely (0ms vs 30s)
- **Brain thoughts streaming:** Thinking blocks and tool use shown as white text in web UI
- **Instant commands:** show job queue, show prompt list, my commands bypass LLM (<100ms)
- **Essence mode:** Tax Accountant loads as Jane essence (/?essence=tax_accountant_2025), not separate page
- **Docker slim-down:** 1.3 GB → 210 MB download. Amber removed, ChromaDB pulled from Hub, CLIs install at boot, pip trimmed 162 MB
- **Onboarding:** switched to Alpine (265 MB → 139 MB)
- **Essences fix:** Race condition on dropdown — pre-fetch cache + loading indicator
- **Jane Default Seeds:** 25 universal habits extracted for new user first-boot
- **Prompt queue:** Now uses internal web API (no subprocess), dedicated persistent session
- **Briefing audio:** 65 files generated with GPU XTTS, web UI has brief/full toggle with server audio
- **Security:** 20 files sanitized (no /home/chieh paths), .dockerignore hardened, Dockerfiles remove all .db files
- **Offline banner:** Requires 2 consecutive health check failures (no more flicker)
- **Scrollbar:** Width 6px → 12px, brighter, visible track
- Code map generator split into core/web/android maps with architecture section
- Read discipline hook installed for grep-first, diff-aware editing
- Gemma pre-warm at startup (first classification 29s → 2ms)
- Memory daemon fast path (skip slow gemma synthesis when daemon is available)
- Custom NDJSON reader (no asyncio 64KB buffer limit)

## v0.0.41 (2026-03-24)
- Tax Accountant 2025 essence fully built (ChromaDB knowledge, web UI, API routes)
- Briefing model switched from deepseek-r1:32b to gemma3:12b
- Briefing cron changed from hourly to daily at 2:10 AM
- Model label shown on each Jane response bubble
- CLAUDE_BIN env var fix for jane-web service
- Code map index generator added

## v0.0.40 (2026-03-23)
- Daily Briefing added as built-in card on Android home screen
- Web essences page restructured: hub with Jane, Essences, and Tools sections

## v0.0.39 (2026-03-22)
- New Session properly kills Claude CLI session + auto-reinitializes context
- Voice input auto-sends in empty chat state (no manual send needed)
- Update banner persists in ViewModel (no more flash-disappear)
- Briefing summarization model configurable (DeepSeek R1:32b for personal use)
- Copy button inside user bubbles

## v0.0.38 (2026-03-22)
- Copy button inside user message bubbles (bottom-right, matches Jane bubbles)

## v0.0.37 (2026-03-22)
- Removed TTS voice reading of status updates during streaming (was distracting)

## v0.0.36 (2026-03-22)
- Tag count badge + tag chips on briefing article cards (shows relevance)
- Articles sorted by tag count (most relevant first)

## v0.0.35 (2026-03-22)
- Reverted chat TTS to device on-device engine (instant playback)
- Server XTTS-v2 kept for Daily Briefing pre-generated audio only

## v0.0.34 (2026-03-22)
- Jane chat now uses server XTTS-v2 for TTS (near-human voice quality)
- New `/api/tts/generate` endpoint with caching (same text = cached audio)
- Falls back to device TTS if server generation fails
- GPU support for XTTS-v2 Docker (NVIDIA Container Toolkit)

## v0.0.33 (2026-03-22)
- Auto-listen fix: falls back to Android SpeechRecognizer when Vosk not available
- 6-second silence timeout on auto-listen after TTS
- Transcript auto-sends as next message

## v0.0.32 (2026-03-22)
- Briefing audio smart cache: auto-download on WiFi, stream on mobile data
- Daily cleanup of cached audio files (older than 1 day)
- Playback priority: local cache → server stream → device TTS
- XTTS-v2 for personal use, VITS for distribution (controlled by TTS_MODEL env var)
- Mandatory changelog check enforced by Gradle build

## v0.0.31 (2026-03-22)
- Auto-listen after TTS: Jane automatically listens for voice input after speaking (6s timeout, default ON)
- Server-generated XTTS audio for briefing articles (plays via MediaPlayer, falls back to device TTS)
- Stop audio FAB in briefing: turns red with X whenever any audio is playing (not just read-all)

## v0.0.30 (2026-03-22)
- Fixed header text wrapping: "Jane Your personal genie" now stays on one line with ellipsis overflow
- Version number shown in essence list view (reads from APK dynamically)

## v0.0.29 (2026-03-22)
- Jane's photo replaces Psychology icon in empty chat state and top bar
- Empty chat state centered properly
- Subtitle changed to "Your personal genie"
- "New Session" text replaces + icon button
- TTS voice picker: network/cloud voices included, distinct names with quality labels
- Session pre-warm fires on every app launch (not just empty history)
- TTS status voice interval changed to 10 seconds

## v0.0.28 (2026-03-22)
- Version bump to trigger update notification

## v0.0.27 (2026-03-22)
- Daily Briefing IllegalStateException fix (JSON parsing for cards/topics API)
- Essence ordering: Jane first, Work Log always last, rest alphabetical
- Jane's photo in essence list home screen
- Update banner persists with Install/OK buttons (rememberSaveable)
- TTS speaks status updates every 6s during streaming
- Copy button on AI and user message bubbles
- Prompt Queue management bottom sheet (list, add, reorder, delete, retry)
- Settings sync between server and Android
- Session pre-warm on app launch (wake-up greeting)
- Smart auto-scroll (only when near bottom)
- Collapsible "Jane worked through N steps" status logs
- Bubble splitting: new work cycle after response = new bubble
- Download progress in Android status bar (DownloadManager)

## v0.0.26 (2026-03-22)
- Jane's photo on login page (both compact/Android and full/web)
- Work log: removed essence load/unload/activate spam
- Daily Briefing: tag-based redesign (categories, multi-tag matching, relevance sorting)
- Essence Isolation Framework: dynamic route mounting, essence scheduler, generic tool API
- Jane-to-Essence Tool Bridge: CLI entry points, tools injected into Jane's context

## v0.0.25 (2026-03-22)
- Daily Briefing news fetcher: googlenewsdecoder for real article URLs
- Both short + long Haiku summaries for articles
- Briefing cron: every 8 hours, idle-only, daily reset
- App settings sync API (GET/PUT /api/app/settings)
- Android SettingsSync utility

## v0.0.24 (2026-03-22)
- Persistent Claude session streaming: chunk-based reading (fixes 64KB limit crash)
- Context window monitor with auto-rotation at 70% capacity
- Self-healing audit: runs every 6h, idle-only, fixes issues in yolo mode
- Memory janitor upgraded to Claude Opus 4.6, stricter merge rules (threshold 5)
- Jane web managed by systemd (no more nohup conflicts)
- Prompt queue management API endpoints
- Essence ordering in web UI
- Session init endpoint for pre-warming
