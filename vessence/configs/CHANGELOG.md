# Vessence Changelog

## v0.2.4 (2026-04-09)
- Version bump.

## v0.2.3 (2026-04-09)
- Version bump.

## v0.2.2 (2026-04-09)
- Version bump.

## v0.2.1 (2026-04-09)
- Version bump.

## v0.2.0 (2026-04-09)
- Version bump.

## v0.1.118 (2026-04-09)
- Version bump.

## v0.1.117 (2026-04-08)
- Version bump.

## v0.1.116 (2026-04-08)
- Version bump.

## v0.1.115 (2026-04-08)
- Version bump.

## v0.1.114 (2026-04-08)
- Version bump.

## v0.1.113 (2026-04-08)
- Version bump.

## v0.1.112 (2026-04-08)
- Version bump.

## v0.1.111 (2026-04-08)
- Version bump.

## v0.1.110 (2026-04-07)
- Version bump.

## v0.1.109 (2026-04-07)
- Version bump.

## v0.1.108 (2026-04-07)
- Version bump.

## v0.1.107 (2026-04-06)
- Version bump.

## v0.1.106 (2026-04-06)
- Version bump.

## v0.1.105 (2026-04-06)
- Version bump.

## v0.1.104 (2026-04-06)
- Version bump.

## v0.1.103 (2026-04-06)
- Version bump.

## v0.1.102 (2026-04-06)
- Version bump.

## v0.1.101 (2026-04-06)
- Version bump.

## v0.1.100 (2026-04-06)
- Version bump.

## v0.1.99 (2026-04-06)
- Version bump.

## v0.1.98 (2026-04-06)
- Version bump.

## v0.1.97 (2026-04-06)
- Version bump.

## v0.1.96 (2026-04-06)
- Version bump.

## v0.1.95 (2026-04-06)
- Version bump.

## v0.1.94 (2026-04-06)
- Version bump.

## v0.1.93 (2026-04-06)
- Same as v0.1.92.

## v0.1.92 (2026-04-06)
- **Standalone XTTS-v2 TTS server + Android hybrid TTS.** New persistent FastAPI server on port 8095 replaces Docker-per-request approach (~2s warm vs 10-15s). Android HybridTtsManager tries server XTTS-v2 streaming first, falls back to Android TTS. Idle auto-unload after 5min frees GPU. Switch gemma_summarize from gemma3:4b to gemma4:e4b. Remove dead kokoro_tts code.

## v0.1.91 (2026-04-06)
- **Briefing: Vault-backed saved articles with custom groups.** Saved articles now write to `vault/saved_articles/<group>/` as JSON files. Removed preset categories — users create their own groups via the "New Group" field. Groups become vault folders searchable by Jane.

## v0.1.90 (2026-04-06)
- Same as v0.1.89.

## v0.1.89 (2026-04-06)
- **Briefing: Saved articles view + new group creation.** Added "Saved" chip to category bar for browsing saved articles with category filters. Save dropdown now includes "New Group" text field for custom groups. "Shared" tab is now first (before "All") with fallback to All when no shared articles exist.

## v0.1.88 (2026-04-06)
- **Fix: SMS handler TTS deadlock — root cause of all SMS send failures.** Removed ALL `queue.speak()` calls from `ContactsSmsHandler`. The handler now runs SILENTLY — Jane's chat response text handles all user-facing speech. The redundant handler TTS was causing a deadlock: chat TTS flushed the handler's utterance mid-play via QUEUE_FLUSH, Android dropped the utterance without firing any callback, the handler's coroutine suspended forever waiting for onDone, tool results never reached the server. Also: `AndroidTtsManager.stop()` now resumes all pending continuations before stopping the engine, and `onStop()` callback added for API 23+ utterance interruption. Handler diagnostic reporting added to `ClientToolDispatcher` — posts start/finish events to `/api/device-diagnostics` for server-side visibility.

## v0.1.87 (2026-04-05)
- **Fix: SMS draft expiry silent drop.** `commitDraft` now proceeds with send on expired drafts (was silently failing after 120s). `updateDraft` refreshes the expiry timer on edit so drafts stay alive through edit cycles. Eliminates missed sends where Jane confirmed success but the recipient never received the message.

## v0.1.86 (2026-04-05)
- Changelog sync for build tooling version gate.

## v0.1.85 (2026-04-05)
- **Fix: SMS draft expiry on re-entry (continued).** Version bump to align with build tooling after changelog verification gate caught a mis-bump.

## v0.1.84 (2026-04-05)
- **Fix: SMS draft expiry on re-entry.** `commitDraft` no longer fails silently when the 120-second draft lifetime expires before the user confirms "send it" — it now logs a warning and proceeds with the send. `updateDraft` refreshes the expiry timer when a draft is edited after expiry, keeping the draft alive through edit cycles. Eliminates the class of missed SMS sends where Jane confirmed success but the recipient never received the message.

## v0.1.83 (2026-04-05)
- **Fix: SMS draft expiry silently dropping confirmed sends.** When more than 120 seconds elapsed between `sms_draft` and `sms_send`, the draft expired and the SMS was never sent — with no user-facing feedback. `commitDraft` now logs a warning but proceeds with the send instead of failing. `updateDraft` refreshes the timer on expired drafts so edits keep working. Root cause of the recipient not receiving the "I'll be home late" text.

## v0.1.81 (2026-04-05)
- **Fix: SMS contact resolution matching wrong contacts.** Searching for a contact name was matching unrelated contacts because `ContactsResolver` used raw `LIKE %query%` substring search on the full display name, which matched the query inside parenthetical annotations. Replaced with Android's `CONTENT_FILTER_URI` (smart locale-aware matching) + a three-tier local ranking: Tier 1 = exact full-name match, Tier 2 = name token exact match, Tier 3 = token prefix match. Lower-tier results (substring inside parenthetical notes) are DISCARDED when higher-tier matches exist. Also: verbose tier logging (`findCallable('<name>'): raw=N → tier1=X tier2=Y tier3=Z → returning X`) so debugging is immediate. This was the root cause of all SMS send failures — every `sms_draft` returned `needs_user` (ambiguous contact), the draft slot was never opened, and `sms_send` failed with "no open draft to send."
- **Compact Gemma4 prompt** — system prompt reduced 75% (7,496 → 1,876 chars) to fix intermittent format-compliance failures where Gemma dropped the CLASSIFICATION/RESPONSE wrapper and output raw answers. History budget changed from turn count (5 turns) to character count (600 chars max). Diagnostic logging added: when classification fails, Gemma's raw output is now dumped to the log.
- **Text-mode skip** — Gemma initial ack layer is now ONLY activated for voice/TTS conversations. Text-only messages go straight to Opus with no intermediary, eliminating classification delay and misclassification risk for typed input.
- **Standing brain CWD flip** — brain now runs from `~/ambient/vessence/` instead of `/tmp`. Loads CLAUDE.md, discovers project tree, fires hooks. Standing-brain override instruction added to context builder to skip automation rules (self-continuation, job queue) that are CLI-interactive-only. Memory dedup guard prevents double injection when hooks provide per-turn fresh memory.
- **Temporary playlist cleanup** — `create_music_playlist_from_query` now deletes prior "Playing:*" / "Random Mix" playlists before creating a new one so they don't accumulate.
- **Kokoro dead code removed** — deleted `kokoro_tts.py`, `test_kokoro.py`, uninstalled `kokoro-onnx` pip package. Was never called from any runtime path.

## v0.1.80 (2026-04-05)
- **Fix: `ForegroundServiceDidNotStartInTimeException` crash on Android 13+** — the true root cause of the "Software caused connection abort" error reported. Crash report from device proved the app process was being KILLED BY THE OS, not losing network. `AlwaysListeningService` was being restarted redundantly from multiple callers (`ChatViewModel.endVoiceConversation`, `MainActivity.onResume`, `BriefingViewModel`, `MusicViewModel`, `JaneChatScreen`, `ChatInputRow`) and on Android 13+ each `startForegroundService()` call starts a new hard 5-second deadline for `Service.startForeground()`, which was being missed under main-thread load. Three-layer fix: (1) `startForeground()` now happens in `onCreate()` with a minimal placeholder notification that does NOT touch SharedPreferences disk I/O, guaranteeing promotion within budget; `onStartCommand()` only UPDATES the notification with the user's real trigger phrase via `NotificationManager.notify`. (2) `AlwaysListeningService.start()` is now atomically idempotent via `AtomicBoolean.compareAndSet` — two rapid callers can no longer both fire `startForegroundService()`. Flag cleared in `onStartCommand` (post-promotion) and `onDestroy` (teardown). The old `_running` check was racy because it flipped deep inside `startListeningLoop` after promotion. (3) Removed the swallowed `try/catch` on `startForegroundWithPlaceholder` — if foreground promotion fails, the app crashes fast at the true failure point instead of entering a zombie state that the OS kills seconds later with a less obvious trace. Codex caught both the race and the swallowed-catch in post-fix review.

## v0.1.79 (2026-04-05)
- **Fix: "Software caused connection abort" on mobile during long Jane tasks.** The user's Android client was hitting OkHttp read-timeout at ~114s when Jane's mind was silently thinking on a complex task. Root cause: `ApiClient.kt` set `readTimeout(120, SECONDS)`, and the server's `_emit_keepalive` heartbeat was sending empty-payload SSE events which some mobile carrier NATs / intermediate proxies drop or buffer at the chunked-encoding boundary — so bytes never reached the client and the read timeout fired. **Two-part fix:** (1) server heartbeats now carry a non-empty `{timestamp}:{seq}` payload guaranteeing real bytes on the wire at 3s intervals; (2) Android `readTimeout` raised from 120s → 600s (10 min) as a backstop for the longest legitimate Jane task. Long-term solution documented in memory (stream_reliability topic): decouple OkHttp readTimeout from application-level stream health via a Kotlin watchdog that tracks "last SSE event received" and reconnects on quiet-for-30s.
- **SMS tool debugging: verbose tool_result logging.** The user reported SMS sends are failing. The previous log line only said "received N tool result(s)" without the payload, and Jane's ack echo was truncated at 60 chars. Added full logging of `tool`/`status`/`message`/`data` fields for every received tool result in `stream_message` and `send_message` paths so the next reproduce immediately tells us which handler failed and why (permission denied vs stale draft_id vs SmsManager exception vs sanitizer-blanked body, etc).

## v0.1.78 (2026-04-05)
- **Jane Phone Tools Phase 7 (tool loader + enforcement) + audit-driven fixes.** Phase 7a: new `jane/tool_loader.py` discovers `tools/<name>/mcp.json` + `prompt.md` + `server/__init__.py::register()` hooks at runtime. Kernel `context_builder.py` now pulls prompt sections from the loader instead of hardcoding `PHONE_TOOLS_PROTOCOL` per tool. Kernel `jane_proxy.py` delegates SMS-draft detection to the loader's pre-dispatch filter pipeline; the old hardcoded `_has_open_sms_draft` + regexes were deleted. Phase 7b: new Gradle task `generateToolSources` copies `tools/*/android/src/**/*.kt` into `build/generated/source/tools/` before Kotlin compilation so tool Kotlin can live outside the main source tree; proof-of-concept `tools/phone/android/src/.../PhoneToolMarker.kt` verifies the pipeline end-to-end. Phase 7c: git pre-commit hook at `scripts/hooks/pre-commit` enforces tool/kernel isolation at commit time; static `check-kernel-hygiene.sh` lint scans kernel Python + Kotlin for forbidden per-tool references (passes clean against current allowlist). Installed via `git config core.hooksPath`. **Audit-driven fixes (codex + gemini full review of shipped code):** (1) fixed `has_open_sms_draft` same-turn close bug — a turn containing draft+send or draft+cancel was incorrectly reported as still-open; (2) `ToolMarkerExtractor._find_marker_end` now has a `_MAX_HOLD` cap so a runaway 6KB+ JSON payload fails open to visible text instead of unbounded scan; (3) `_format_tool_results_for_brain` neutralizes delimiter-injection attempts (a malicious SMS body cannot forge the `[END PHONE TOOL RESULTS]` block boundary); (4) `send_message` sync path now runs tool-result extraction + marker stripping so it cannot silently leak raw markers into the UI; (5) sync path lacks structured `client_tool_call` emission — logged warning if markers appear there; (6) `ContactsSmsHandler.sanitizeBody` preserves newlines instead of collapsing them (was destroying SMS formatting); tool marker strip in body now uses brace-counting instead of naive regex so JSON containing `]` doesn't break the strip; (7) `RecentMessagesBuffer.record` wrapped in synchronized block to prevent rapid-fire concurrent posts from duplicating entries; (8) `ContactsSmsHandler.commitDraft` now holds `slotMutex` across the ENTIRE send so a concurrent cancel/update can't race with send; (9) `ActionQueue.startActivity` returns the launch error so `ContactsCallHandler` can surface ACTION_CALL failures via `ToolActionStatus.Failed` instead of reporting silent success; (10) `tool_loader.load_all_tools(force_reload=True)` now purges prior tool modules from `sys.modules` + refuses to follow symlinks. **Duplicate-code cleanup (user's explicit ask):** extracted `asSafeString`/`asSafeInt`/`requireString` Gson helpers to shared `tools/JsonExtensions.kt` (was duplicated across 5 handler files); extracted `isListenerEnabled`/`isPhoneLocked`/`isPlaceholderBody`/`OTP_REGEX`/`MAX_BODY_CHARS`/`filterSafe` to shared `notifications/NotificationSafety.kt` (was duplicated between `MessagesReadRecentHandler` + `MessagesFetchUnreadHandler`); extracted `VessenceNotificationListener.extractMessages()` as the single source of truth for turning a `StatusBarNotification` into `RecentMessagesBuffer.Entry` records, used by both `onNotificationPosted` and `snapshotActiveMessages`. **Memory notes saved:** kernel/apps mental model (Jane=kernel, tools+essences=apps), enforcement hook requirement, queued gmail/android_ui/facebook_marketplace project.

## v0.1.77 (2026-04-05)
- **Jane Phone Tools Phase 6 — unread message triage.** New tool `messages.fetch_unread` that returns the user's currently-unread messaging notifications (SMS, WhatsApp, Signal, iMessage relay, etc.) as structured data via the TOOL_RESULT feedback channel. Jane's mind sees the list in a `[PHONE TOOL RESULTS]` context block on the next turn and decides the response mode: (A) summary-by-sender ("you have 4 unread: 2 from Contact A, 1 from mom, 1 from Contact B"), (B) triaged read (skip promos/OTP/delivery updates, read personal/actionable ones verbatim, mention what was skipped), or (C) direct quote of a specific sender the user asked about. `NotificationListenerService` gained `snapshotActiveMessages()` that queries the live `activeNotifications` set (not the stale ring buffer) so "unread" matches user intuition. `ToolResult` and `ToolActionStatus.CompletedWithData` extended to carry arbitrary JSON payloads. `_extract_tool_results` in `jane_proxy.py` upgraded from non-greedy regex to brace-counting + string-escape tracking so nested JSON and `}]` inside string values parse correctly (7/7 unit tests). `prependPendingToolResults` wired into `ChatViewModel.executeSend` so tool results actually reach the server on the next user turn — that plumbing was missing in Phase 4. `_format_tool_results_for_brain` helper formats parsed results as a human-readable context block Jane's mind can parse. **Also in this release: SMS body sanitizer** strips `[ACK]`/`<spoken>`/`<visual>`/residual tool markers from draft bodies before `SmsManager.sendTextMessage`, appends " — via Jane" signature, and uses `sendMultipartTextMessage` for bodies >160 chars. **Also: auto-permission prompt at first launch** — MainActivity now proactively requests READ_CONTACTS, CALL_PHONE, SEND_SMS via a batched `RequestMultiplePermissions` launcher so handlers don't hit permission-denied on first tool use. **Also: jane-web version-restart fix** — `PUBLIC_RELEASE_DOWNLOADS` no longer bakes the APK path at module load time; `_resolve_android_apk_path` resolves dynamically at request time by reading `version.json` fresh, so future APK bumps don't require a jane-web restart.

## v0.1.76 (2026-04-05)
- **Phone tools enabled by default:** Flipped the `PREF_PHONE_TOOLS_ENABLED` feature flag default from OFF to ON, so SMS drafting/sending, calls, and notification reading are active out of the box without needing to toggle a hidden setting.

## v0.1.75 (2026-04-05)
- **Jane Phone Tools (scaffolding, flag-gated):** Added the complete server + Android pipeline for three phone capabilities — placing calls, a multi-turn SMS draft loop, and reading recent messaging notifications aloud. **Ships with the feature flag `PREF_PHONE_TOOLS_ENABLED` defaulted to OFF** so there is zero user-visible behavior change until the flag is flipped. Server side: new `ToolMarkerExtractor` in `jane_web/jane_proxy.py` (JSON-aware, fence-aware, 27/27 unit tests passing), `[TOOL_RESULT:{json}]` feedback channel on incoming user turns, `_has_open_sms_draft` scan that bypasses the initial ack layer during active SMS drafts, and a new `PHONE_TOOLS_PROTOCOL` section in Jane's standing-brain system prompt. MCP descriptor added at `tools/phone/mcp.json`. Android side: 11 new files under `tools/` and `contacts/` and `notifications/` implementing `ClientToolDispatcher`, `ActionQueue` (mutex-serialized TTS + intent launcher), `ContactsResolver` (single shared on-device query), `ContactsCallHandler` (10-second countdown before ACTION_CALL), `ContactsSmsHandler` (4 sub-commands with draft_id validation and a 120-second draft lifetime), `MessagesReadRecentHandler` (OTP filtering, lock-screen check, four-way empty-state distinction), `VessenceNotificationListener` (NotificationCompat.MessagingStyle parsing, rebind-on-disconnect), and `RecentMessagesBuffer` (20-entry ring). Runtime permissions added: `READ_CONTACTS`, `CALL_PHONE`, `SEND_SMS`. `BIND_NOTIFICATION_LISTENER_SERVICE` declared. Full design spec at `configs/jane_phone_tools_v1_design.md`. Two codex review passes applied before ship. Feature flag flip and permission-prompt wiring are the remaining steps to user-visible launch.

## v0.1.72 (2026-04-05)
- **Wake word v7 model:** Retrained with ~35K negative sources — added 15K LibriSpeech train-clean-100 clips and 5K clips cut from the user's vault Music library on top of v6's set (total negatives dataset ~31.7K on disk, ~80K after augmentation). Best F1=0.8790, FPR@0.6=0.56% (down from v6's 0.78%), all real "hey jane" recordings score ≥0.9988, 0/500 false positives on held-out speech commands. First model trained against the user's actual music to reduce false triggers during playback.

## v0.1.71 (2026-04-04)
- **Music playlist freeze fix:** After playing for a while (or after a server restart / network drop), ExoPlayer would enter STATE_IDLE or STATE_ENDED, and subsequent `play()` calls silently no-op'd — UI showed "playing" but nothing played. Added `ensurePlayerReady()` that calls `prepare()` + re-adds media items when needed, called from both `playTrack` and `togglePlayPause`. Also added `onPlaybackStateChanged` logging and surfaces an error banner on recoverable interruptions.

## v0.1.70 (2026-04-04)
- **Delete playlist button:** Each playlist in the Music Playlist list now has a red trash icon that opens a confirmation dialog before deleting.
- **Server-down login message:** When the server is unreachable during login, the error shown is now "The server seems to be down. Please try again later." instead of Google's cryptic "Developer console is not set up correctly" or raw network exception.

## v0.1.69 (2026-04-04)
- **Fix music track-switch crash:** Rapidly switching tracks in the Music Playlist caused AlwaysListeningService to start/stop on every track transition, which could interrupt the oww-listener thread mid-sleep() and crash the app with an unhandled InterruptedException. Two-part fix: (1) wake word listener now catches InterruptedException and exits cleanly, (2) MusicViewModel no longer restarts always-listen on every transient isPlaying=false — only when the user leaves the Music screen (onCleared).

## v0.1.68 (2026-04-04)
- **Fix music playback:** Track paths were stored as `vault/Music/...` instead of `Music/...` (off-by-one in `.parent.parent` vs `.parent`), so `/api/files/serve/` couldn't find the files. Music now actually plays.
- **ExoPlayer error surfacing:** Added onPlayerError listener in MusicViewModel so playback failures are logged and shown in UI instead of silently stuck.
- **Tightened gemma4 acks:** System prompt now bans generic phrases ("good question", "digging into that") and requires at least one concrete noun from the user's message.

## v0.1.67 (2026-04-04)
- **Gemma4 music routing:** Gemma4 now classifies music requests (any phrasing) and extracts a clean search query. Proxy creates the playlist via a shared helper, emits [MUSIC_PLAY:id]. No more regex prefix matching, no duplicated code paths.
- **No inline audio players in chat bubbles:** `{{play:...}}` tags are stripped from display; music only plays via the Music Playlist view.
- **No STT after music autoplay:** When music plays, `sttActive` is cleared and `onSendComplete` no longer relaunches STT — conversation ends cleanly.
- **Code dedup:** Consolidated 4 music-playlist-creation paths into one `create_music_playlist_from_query()` in main.py.

## v0.1.66 (2026-04-04)
- **Stop Jane button:** Replaces the old speaker button in chat header. Visible only while Jane is thinking — tap to interrupt the current response (like pressing Esc in the terminal).
- **Wake word v6 model:** Trained on 10K LibriSpeech negatives, F1=0.9089, FPR=0.78%, 0 false positives on held-out speech commands.
- **Repo cleanup:** Stripped 9GB of old debug APKs, installer zips, and Flutter build artifacts from git history.

## v0.1.64 (2026-04-04)
- **Fix gemma4 delegate ack:** Gemma4's contextual ack was being discarded on delegate path. Now properly extracted and spoken.
- **Remove Python ack fallback:** If gemma4 has no ack, Claude handles it via [ACK] block instead of generic random phrases.

## v0.1.63 (2026-04-04)
- **Fix music auto-play on re-navigation:** MusicScreen now checks pending playlist via LaunchedEffect instead of relying on ViewModel init (which only runs once).

## v0.1.62 (2026-04-04)
- **Instant music play:** "play X" is handled deterministically at the proxy — no LLM needed. Creates playlist, emits [MUSIC_PLAY:id], Android navigates to Music Playlist and auto-plays.
- **File download links:** Markdown links in chat render as clickable blue text for downloading files.
- **Stop Speaking ends conversation:** No STT popup, always-listen resumes for wake word.

## v0.1.61 (2026-04-04)
- **Clickable download links in chat:** Markdown links render as tappable blue text. Jane can now put file download links directly in chat bubbles.
- **Stop Speaking ends conversation:** Pressing Stop Speaking now ends the voice conversation (no STT popup) and restarts always-listen for wake word detection.
- **Race condition fix:** If TTS is cancelled mid-speech, auto-listen no longer fires spuriously.

## v0.1.60 (2026-04-04)
- **Instant STT on wake word:** No navigation delay, no retry, no screen switching. STT popup launches immediately from any screen. Results go through SttResultBus to ChatViewModel regardless of current view.

## v0.1.59 (2026-04-04)
- **Eliminated all StateFlow chains for STT:** speechLauncher moved to MainActivity.launchStt(). Wake word, mic button, and auto-listen all call the same function directly. No more WakeWordBridge/WakeWordPendingFlag/wakeWordTriggered indirection.

## v0.1.58 (2026-04-04)
- Version bump fix

## v0.1.57 (2026-04-04)
- **Fix wake word STT not firing:** ChatViewModel now observes WakeWordPendingFlag and sets wakeWordTriggered. Single LaunchedEffect in JaneChatScreen handles both wake word and auto-listen.

## v0.1.56 (2026-04-04)
- **Simplified wake word → STT:** Direct path — navigate to Jane + set WakeWordPendingFlag. No more indirection through jane_wake or pendingChatTarget.

## v0.1.55 (2026-04-04)
- **Remove Stage 2 WakeWordVerifier:** Headless SpeechRecognizer was rejecting real triggers due to mic contention. Reverted to 5-frame temporal smoothing only.

## v0.1.54 (2026-04-04)
- **Single wake word handler:** VessencesApp is the sole observer of WakeWordBridge. Navigates to Jane + sets WakeWordPendingFlag. JaneChatScreen consumes flag and launches STT. No racing collectors, no duplicate triggers.
- **Always-listen off during conversation:** sttActive properly cleared on conversation end (silence timeout, user cancel, end phrase).

## v0.1.53 (2026-04-04)
- **Fix wake word navigation from non-chat screens:** ChatViewModel now delays consuming WakeWordBridge signal by 500ms so VessencesApp can observe it for navigation first.

## v0.1.52 (2026-04-04)
- **Faster STT on wake word:** Reduced delay from 800ms to 200ms. STT popup appears immediately without waiting for chat scroll.

## v0.1.51 (2026-04-04)
- **Fix double STT (root cause v3):** Restored wake word navigation from non-Jane screens. Added 3s dedup guard in LaunchedEffect. Clear trigger before delay to prevent recomposition re-fire. Single STT popup in all cases.

## v0.1.50 (2026-04-04)
- **Fix double STT (simplified):** Removed all intermediary flags. LaunchedEffect keyed directly on wakeWordTriggered — fires once, launches STT, clears trigger. Removed VessencesApp wake word observer. Single consumer, single trigger.

## v0.1.49 (2026-04-04)
- **Fix double STT (root cause):** Single event source — WakeWordBridge.signal() is the only wake word trigger. Removed pendingChatTarget from wake word path. VessencesApp observes WakeWordBridge for navigation. ChatViewModel consumes for STT. No duplicate signals.

## v0.1.48 (2026-04-04)
- **Fix double STT trigger on wake word:** 3-second debounce prevents WakeWordBridge and navigation from both launching STT.

## v0.1.47 (2026-04-04)
- **Always-listen pauses during all audio:** Music playback, briefing read-aloud, and Jane TTS all pause wake word listening. Resumes when audio finishes.

## v0.1.46 (2026-04-04)
- **Auto-play music from Jane:** "Play the scientist" navigates to Music Player and starts playing automatically.
- **Always-listen pauses during music:** Mic is disabled while music plays. Resumes when music stops.
- **MCP capability queries:** "What can you do with the music playlist?" returns tool capabilities from mcp.json.

## v0.1.45 (2026-04-04)
- **Music playback via Jane:** "Play the scientist" or "play some Shakira" → creates playlist from vault search → navigates to Music Player → auto-plays. Server endpoint, Android navigation, and MCP all wired up.
- **MCP spec defined:** Music Playlist is the first tool with a complete mcp.json.

## v0.1.44 (2026-04-04)
- **Stage 2 wake word verification:** After 5 consecutive DNN detections, runs headless SpeechRecognizer to transcribe audio and verify "jane" is actually spoken. False positives are suppressed. Fail-open on error/timeout.
- **Strip markup tags from chat bubbles:** <spoken>, <visual>, <think>, <artifact> tags no longer flash during streaming.
- **Gemma4 prewarm on server startup:** Router model loads into VRAM automatically.
- **Weather: gemma includes high/low + AQI.** Location configurable via .env.

## v0.1.43 (2026-04-03)
- **Fix always-listen during conversation:** sttActive flag now properly set/cleared. onResume won't restart wake word service during active voice conversation.
- **Tighten gemma4 router:** Only handles pure greetings/jokes/math/weather. Everything else delegates to Claude. Prevents nonsensical responses to technical questions.

## v0.1.42 (2026-04-03)
- **Two-stage wake word verification:** Requires 5 consecutive frames (~400ms) above threshold before triggering. Kills random single-frame spikes from background speech.
- **Weather integration:** Daily 3:30am cron fetches 7-day forecast + air quality for Medford, MA. Gemma4 router answers weather questions directly from cached data.
- **Fix premature STT:** Auto-listen removed from speakIfEnabled, only triggers after final response.
- **Fix threshold slider crash:** No longer restarts service on slider drag.

## v0.1.41 (2026-04-03)
- **Fix premature STT after ack:** Auto-listen removed from speakIfEnabled() — only triggers after final response via onSendComplete. Prevents STT opening before Claude responds.
- **Fix threshold slider crash:** No longer restarts service on every slider move. Threshold saves to prefs and applies on next service start.

## v0.1.40 (2026-04-03)
- **Wake word threshold slider restored** in Settings (0.50–0.95 range). User can tune in real-time. Default 0.80. Service reads from settings on each start.

## v0.1.39 (2026-04-03)
- **Retrained wake word model (v5):** Removed speech-mixed positives that caused false triggers. Clean TTS + real recordings only. Should have much better discrimination against background speech.

## v0.1.38 (2026-04-03)
- **Remove security bypass warnings:** Removed USE_FULL_SCREEN_INTENT, lock screen bypass, and full-screen notification code. Wake word only works when app is focused — no need for these aggressive permissions.

## v0.1.37 (2026-04-03)
- **Raise wake word threshold to 0.80:** False triggers scoring 0.74-0.75, real voice at 0.9999. Provides clear margin.

## v0.1.36 (2026-04-03)
- **Wake word only when app is focused:** Service starts on app resume, stops on app pause. Eliminates screen-off false triggers, rapid loops, and battery drain. Screen-off wake word code preserved for future re-enablement.

## v0.1.35 (2026-04-03)
- **Fix STT not launching after wake word:** 2s delay for full-screen intent to settle. Stop always-listen before STT to free mic. Quick-cancel guard prevents restart loop when STT fails to start.

## v0.1.34 (2026-04-03)
- **Reliable screen-off wake word:** Uses full-screen intent notification (like phone calls) to wake screen and launch app on Android 10+. Added USE_FULL_SCREEN_INTENT permission and high-priority notification channel.
- **Build guard:** Gradle now fails if any .onnx.data file exists in assets (prevents recurring model loading bug).

## v0.1.33 (2026-04-03)
- **Fix wake word model loading:** Inlined ONNX weights again (training recreated the .data file). Permanently fixed train_oww.py to always inline.

## v0.1.32 (2026-04-03)
- **Lower wake word threshold to 0.55:** 0.85 was too aggressive, blocking all detections. 0.55 balances responsiveness with false-positive rejection.

## v0.1.31 (2026-04-03)
- Version bump (no code changes)

## v0.1.30 (2026-04-03)
- Version bump (no code changes)

## v0.1.29 (2026-04-03)
- Build fix for v0.1.28

## v0.1.28 (2026-04-03)
- **Fix screen-off wake word:** Reactive navigation (StateFlow) so wake word works when app is backgrounded.
- **30s wake word cooldown:** Prevents rapid false-trigger loops from background noise.
- **Wake word threshold raised to 0.85:** Further reduces false positives while keeping 0.9999 on real voice.
- **Retrained wake word model (v4):** Speech-mixed positives improve robustness to background conversation (F1: 0.93).
- **Server health check:** Auto-restarts jane-web if unresponsive (checks every 2 min).

## v0.1.27 (2026-04-03)
- **Fix Gemma ACK not spoken:** Gemma's quick acknowledgment now emits as "ack" event (was "delta"), so Android TTS actually speaks it.
- **Fallback ACK on Gemma failure:** If Gemma router times out or crashes, a fallback acknowledgment is still emitted so the user is never left in silence.

## v0.1.26 (2026-04-03)
- **Reduce wake word false positives:** Threshold raised to 0.7 (from 0.5) to reject background speech triggers.
- **Fix auto-listen after TTS:** Unified STT path uses wakeWordTriggered for consistent Google STT popup every turn.
- **Fix "ok" end phrase:** "ok"/"okay" now only ends conversation on exact match (won't trigger on "ok tell me a joke").
- **STT silence timeouts:** 4s complete silence, 6s mid-sentence pause (consistent across all paths).
- **Removed red X FAB** from home screen (stop-listening available in chat view).

## v0.1.25 (2026-04-03)
- **Remove duplicate stop-speaking button:** Removed X button from top bar (web + Android); bottom "Stop speaking" button is the only control.
- **Fix STT auto-relaunch:** Speech-to-text popup now re-opens every turn, not just the first.
- **Fix always-listen after STT timeout:** Wake word service now restarts when STT expires or is cancelled without input.

## v0.1.24 (2026-04-03)
- **Fix wake word crash:** Inlined ONNX model weights (removed stale .data file that caused OrtException on Android).

## v0.1.23 (2026-04-03)
- **Improved wake word model:** Rejects standalone "jane", "a jane", "did jane" (0 false positives). Threshold hardcoded at optimal 0.5. Removed sensitivity slider from Settings.
- **Quick ack fix:** Python classifier now emits instant ack to Android/web instead of suppressing it silently.
- **End phrase:** Added "ok" and "okay" as standalone conversation-ending phrases.

## v0.1.22 (2026-04-03)
- **Fix wake word model:** hey_jane.onnx was exported with external data that Android couldn't load; repacked as self-contained file

## v0.1.21 (2026-04-03)
- **"Hey Jane" wake word:** Retrained wake word model with edge-tts (47 voices), source-disjoint validation, temporal jitter. F1=0.92, 0% false positives on speech, 100% recall on real recordings. Default trigger phrase changed from "hey jarvis" to "hey jane".

## v0.1.20 (2026-04-03)
- Version bump (build fix)

## v0.1.19 (2026-04-03)
- Version bump (build fix)

## v0.1.18 (2026-04-03)
- **Stop speaking button visible:** Red X now appears next to volume toggle while TTS is playing, instead of replacing it. Both buttons always accessible.

## v0.1.17 (2026-04-03)
- **Keep screen on by default:** Screen stays on while app is open. Can be turned off in Settings.

## v0.1.16 (2026-04-03)
- **Consistent STT UI:** Auto-listen after TTS now shows the same Google STT popup as mic button and wake word. All three voice paths use the same code.

## v0.1.15 (2026-04-03)
- **Fix: always-listen restarts after end-phrase in auto-listen mode.** End-phrase detection was only in ChatInputRow (mic button path), not in VoiceController (auto-listen path). Created shared EndPhraseDetector used by both. endVoiceConversation() now properly restarts the service.

## v0.1.14 (2026-04-03)
- Fix: always-listen restarts after end-phrase detection. Added diagnostic logging for debugging.

## v0.1.13 (2026-04-03)
- Fix end-phrase detection: normalize smart quotes, strip punctuation, add apostrophe-free variants for STT
- Debug logging for unmatched end phrases

## v0.1.12 (2026-04-03)
- Version bump / rebuild

## v0.1.11 (2026-04-03)
- **Default Assistant registration:** New "Set as Default Assistant" button in Settings. Long-press home opens Jane instead of Google Assistant. May improve background wake word on some devices.
- **85 end-phrase triggers:** Expanded from 20 to 85 phrases across 5 categories (goodbyes, stop/cancel, thank you, casual, etc.)
- Reviewed by Codex — fixed session launch (startVoiceActivity), added onShutdown cleanup

## v0.1.10 (2026-04-03)
- **End-phrase silently ends conversation:** Saying "I'm done", "goodbye", "stop" etc. no longer sends to Jane or triggers TTS — just silently returns to wake word listening
- **Keep screen on toggle:** New setting prevents screen from sleeping. Ensures wake word works reliably when on charger.
- 7 new briefing topics: Qwen, AI Breakthroughs, New ML Algorithms, Wind Energy, Solar Energy, Humanoid Robots, Home Automation

## v0.1.9 (2026-04-03)
- Version bump / rebuild

## v0.1.8 (2026-04-03)
- **Fix text cutoff in chat bubbles:** Replaced regex-based ACK stripping with incremental character parser. No more double updateAiMessage calls, no trimStart() eating real content, no regex failing across delta boundaries. ACK markup never leaks into visible text.
- **Briefing: newest articles first** (server-side sort fix)

## v0.1.7 (2026-04-02)
- **Fix wake word icon always grey:** Icon now reflects AlwaysListeningService state, not just VoiceController. Green when service is actively listening, grey when stopped.

## v0.1.6 (2026-04-02)
- **Fix update banner showing same version:** Suppresses banner when server version_name matches installed version_name
- **Fix download notification truncation:** Title changed to "Vessence 0.1.6" (short, version fully visible)
- Reviewed by Gemini + Codex

## v0.1.5 (2026-04-02)
- **Pause wake word during media playback:** Always-listening pauses when music, videos, or other audio is playing (uses AudioManager.isMusicActive). Resumes automatically when audio stops.

## v0.1.4 (2026-04-02)
- **Fix service restart race:** MainActivity no longer auto-starts service on wake word intent (was fighting ChatInputRow's stop)
- **Fix competing mic:** VoiceController no longer starts its own wake word detector when always-listen is on
- **Fix early service restart:** ChatInputRow no longer restarts service on STT result if conversation continues (auto-listen)
- Bugs found by Gemini + Codex review panel

## v0.1.3 (2026-04-02)
- **Fix recursive crash:** endVoiceConversation() was calling itself → infinite recursion/stack overflow
- **Auto-start always-listening on app launch:** Service now starts from MainActivity if setting is enabled — no longer requires chat screen to be open
- Quick ack system: categorized messages skip ack, uncategorized get Opus-generated ack

## v0.1.2 (2026-04-02)
- **STT debug toast:** Shows error message if Google STT intent fails to launch

## v0.1.1 (2026-04-02)
- **Fix STT popup not appearing:** Added 600ms delay after wake word to let Activity fully resume before launching Google STT
- **Fix mic contention on manual mic tap:** Stop AlwaysListeningService before launching STT, restart when STT completes

## v0.1.0 (2026-04-02)
- **New session confirmation:** + button now shows "Are you sure?" dialog before clearing session
- **Voice status: icon instead of banner.** Green/grey icon in header replaces full-width banner
- **Fix mic contention:** VoiceController no longer starts its own wake word detection (was fighting AlwaysListeningService for mic)
- **Update banner auto-dismiss:** Banner hides after tapping Install
- **Edge-to-edge display:** White status bar removed
- **Prompt queue hamburger removed** (deprecated)
- **New Session text → + icon**

## v0.0.100 (2026-04-02)
- **New Session button:** Replaced text with a compact + icon

## v0.0.99 (2026-04-02)
- **Removed white status bar:** App now draws edge-to-edge behind system bars, reclaiming the top space
- **Removed prompt queue hamburger button:** Prompt list feature deprecated
- Wake word now launches same Google STT popup as mic button (from v0.0.98)

## v0.0.98 (2026-04-02)
- **Wake word now launches the SAME Google STT popup as the mic button.** No more separate SpeechRecognizer code. Wake word sets a flag → ChatInputRow sees it → launches the same `ACTION_RECOGNIZE_SPEECH` intent with the system UI.
- Removed all duplicate STT code (startAndroidSpeechRecognizer, activeRecognizer, sttRetryCount).

## v0.0.97 (2026-04-02)
- **Wake word now uses same STT as mic button:** Replaced separate startAndroidSpeechRecognizer() with startPushToTalk() — exact same code path, same UI, same behavior. No more duplicate STT implementations.

## v0.0.96 (2026-04-02)
- **Radical simplification of wake word → STT handoff:** Service now STOPS completely on detection instead of polling sttActive. ChatViewModel restarts the service when conversation ends (silence, end-phrase, or error). Eliminates all timing/race condition issues.
- **Fix RECOGNIZER_BUSY:** Track activeRecognizer and destroy previous before creating new one.
- **endVoiceConversation():** Single method handles both releasing sttActive AND restarting wake word service.

## v0.0.95 (2026-04-02)
- **Fix STT race condition:** Service now waits for sttActive to become TRUE first (up to 15s) before waiting for conversation to end. Previously used fixed 3s sleep which wasn't enough for Activity launch from screen-off.
- **Fix RECOGNIZER_BUSY:** Track and destroy previous SpeechRecognizer before creating new one. Prevents leaked recognizers from blocking new STT attempts.
- **Fixed idle check:** Daily briefing now uses idle_state.json (real user input) instead of log file mtime (touched by background processes).

## v0.0.94 (2026-04-02)
- **End-phrase detection in chat:** Saying "we're done", "goodbye", "stop", etc. during voice conversation now ends the loop and releases mic back to wake word
- **Conversation wait extended to 5 min:** Wake word service now waits up to 300s for multi-turn conversations (was 60s — caused mic conflicts)
- **Diagnostics endpoint live:** Restarted jane-web to enable /api/device-diagnostics

## v0.0.93 (2026-04-02)
- **Wake word STT error visibility:** STT errors now show as system messages in the chat (e.g., "[Wake word] STT error: RECOGNIZER_BUSY — retrying...") so we can see exactly what's failing. Added `isRecognitionAvailable()` check before attempting STT. Retry logic now handles CLIENT errors and backs off with increasing delays (up to 3 retries). Also removed status banner from Android chat (batched from earlier).

## v0.0.92 (2026-04-02)
- **Keep always-listen paused during full conversation:** sttActive flag now stays true through the entire wake word conversation loop (user speaks → Jane TTS → auto-listen → user speaks → ...). Service only resumes wake word detection when the conversation ends: STT timeout (user stops talking), empty result, or auto-listen is disabled.

## v0.0.91 (2026-04-02)
- **Fix download notification version truncation:** Changed DownloadManager title from "Vessences 0.0.X" to "v0.0.X — Vessence update" so the version number shows first and doesn't get cut off.

## v0.0.90 (2026-04-02)
- **Fix "voice unavailable" after wake word:** AlwaysListeningService was grabbing the mic back after 3s, conflicting with SpeechRecognizer. Added sttActive flag to WakeWordBridge — service now waits until STT finishes (up to 60s) before resuming wake word detection.

## v0.0.89 (2026-04-02)
- **Heavy wake word diagnostics:** Added 30s heartbeat from service, periodic score reports (~50s), detailed logging at every stage (model init, mic open, audio read, detection). DiagnosticReporter.init() now called from service too (was only in Activity — service restarts without Activity would silently fail to send diagnostics). Added "Send diagnostic ping" button in Settings to test server connectivity.

## v0.0.88 (2026-04-02)
- **Wake word STT fix:** Added 1.5s delay before activating SpeechRecognizer after wake word — lets the activity fully launch first. Added error logging and auto-retry for busy/audio errors.

## v0.0.87 (2026-04-02)
- **Wake word sensitivity slider:** New slider in Settings (10%-90%) to tune wake word detection threshold. Default lowered from 50% to 30%. Changing the slider auto-restarts the listening service.

## v0.0.86 (2026-04-02)
- **Wake word wakes screen:** When "hey Jarvis" is detected with screen off, screen turns on, app shows over lock screen, keyguard dismisses, and STT activates. Screen returns to normal timeout after conversation.

## v0.0.85 (2026-04-02)
- **Wake word triggers chat mic:** Wake word no longer captures speech itself. It just detects "hey Jarvis", vibrates, opens the Jane chat screen, and auto-activates the same STT mic button. Your speech shows up as a normal chat bubble.
- Removed all SpeechRecognizer code from AlwaysListeningService — service is now purely a wake word detector.

## v0.0.84 (2026-04-02)
- **Wake word works from any screen:** Bridge now uses StateFlow (persists until consumed) instead of SharedFlow (was dropped if chat screen wasn't open). Wake word also navigates directly to Jane chat screen.

## v0.0.83 (2026-04-02)
- **Wake word shares chat pipeline:** Removed duplicate streaming/TTS/follow-up code from AlwaysListeningService. Wake word now routes commands through ChatViewModel's sendMessage() via WakeWordBridge — same session, same memory, same TTS, same everything.
- **Shared session ID:** ChatViewModel and AlwaysListeningService use the same Jane session ID (stored in SharedPreferences). No more isolated one-shot requests.
- **Voice always speaks back:** fromVoice messages always trigger TTS response regardless of TTS toggle state.

## v0.0.82 (2026-04-02)
- **Fix Always Listen crash:** SecurityException on TelephonyManager.getCallState — missing READ_PHONE_STATE permission on Android 13+. Wrapped in try-catch.
- Added DiagnosticReporter: sends wake word status, mic state, errors to server
- Server endpoint: GET/POST /api/device-diagnostics

## v0.0.80 (2026-04-02)
- Fix crash when toggling Always Listen — added try-catch around ONNX model init
- Removed unused import

## v0.0.79 (2026-04-02)
- Mic permission: shows dialog with "Open Settings" button when permission is denied for Always Listen
- Process safety: TTS Docker containers now limited to 1 at a time with memory/CPU caps
- Briefing cron capped at 30 minutes max runtime
- Added process watchdog (every 5 min) to kill zombie containers and idle build daemons

## v0.0.78 (2026-04-02)
- **Wake word fix:** Switched from broken hey_jane.onnx to working hey_jarvis_v0.1.onnx model
- "Hey Jarvis" now triggers wake word detection (hey_jane model will be retrained later)

## v0.0.77 (2026-04-02)
- Version skipped (bad Flutter build)

## v0.0.76 (2026-04-01)
- **Wake word model fix:** hey_jane.onnx was missing weight data (external .data file not copied). Re-exported with all weights embedded inline (15KB → 215KB)

## v0.0.75 (2026-04-01)
- **Chat crash fix:** Replace deprecated `RequestBody.create(null, ...)` with `toRequestBody(null)`
- **Wake word fix:** Persistent mel-frame buffering — detection was completely non-functional (embeddings never computed)
- **Wake word fix:** Mic contention race — listener thread now blocks until conversation turn completes
- **Wake word fix:** Audio ghosting — drains mic buffer during TTS instead of sleeping
- **Wake word fix:** Soft reset preserves mel warmth after detection (no cold-start delay)
- **ProGuard:** Added ONNX Runtime keep rules for release builds
- **Threshold:** Lowered wake word threshold from 0.5 to 0.3 for mobile audio
- **Resource safety:** try/finally on all ONNX tensor operations to prevent native leaks

## v0.0.74 (2026-03-31)
- **Bug fixes:** Rebuilt with bug fixes from previous session (version bump for auto-update)

## v0.0.73 (2026-03-31)
- **"Hey Jane" wake word:** Custom trained OpenWakeWord model — say "hey jane" instead of "hey jarvis"

## v0.0.72 (2026-03-31)
- **Always-On Voice fix:** Fixed corrupted ONNX model files (were HTML pages, not actual models)

## v0.0.71 (2026-03-31)
- **Always-On Voice fix:** Skip trigger training — OpenWakeWord uses pre-trained models, no training needed
- **Always-On Voice fix:** Toggle now enables immediately after granting mic permission
- **Audio cues:** Beep when SpeechRecognizer is ready, ack tone when done listening

## v0.0.70 (2026-03-31)
- **Always-On Voice:** Replace Vosk (50MB) with OpenWakeWord (1.8MB) — 10x less battery drain
- **Always-On Voice:** Full conversation loop: wake word → command → TTS reply → auto-listen follow-up
- **Always-On Voice:** End-conversation phrases ("we're done", "goodbye", etc.)
- **Always-On Voice:** Stop button in notification + home screen FAB
- **Always-On Voice:** Battery optimization exemption, Android 14+ foreground service type
- **Always-On Voice:** 9 bugs fixed from team review (integer overflow, resource leaks, race conditions)
- **TTS mute fix:** Volume toggle now actually mutes voice responses
- **Briefing save:** Bookmark button on article cards with category dropdown
- **Debug/release signing:** Both build variants now use release key

## v0.0.69 (2026-03-31)
- **Google sign-in fix:** Rebuilt APK with correct release signing key to match Google Cloud OAuth configuration

## v0.0.68 (2026-03-31)
- Skipped (build issue)

## v0.0.67 (2026-03-31)
- **Briefing audio player:** Tap Brief/Full on a card to open a dedicated player view with play/pause, auto-start, and back button
- **Briefing audio player:** Switch between brief and full summary, open full article, save articles to categories (permanent)
- **Saved articles:** Bookmarked briefing articles persist permanently with category grouping, audio preserved across cleanup
- **Mic toggle button:** Jane web chat mic is off by default, tap to enable continuous voice input, persisted in localStorage
- **TTS mute button:** Quick mute/unmute for Jane's voice responses in web chat

## v0.0.66 (2026-03-30)
- **Image viewer:** Tap image thumbnails in chat to view fullscreen, tap again to dismiss
- **Rich content tags:** Jane now uses {{image:path}} tags so images render inline in chat

## v0.0.65 (2026-03-30)
- **Download notification title shortened** — now shows "Vessences 0.0.65" instead of truncated longer title

## v0.0.64 (2026-03-30)
- **File uploads work:** Android file attachments now upload to vault, get indexed in ChromaDB, and saved to memory

## v0.0.63 (2026-03-30)
- **Voice: silence timeout** — possibly-complete silence bumped from 4s to 6s to match complete silence
- **Voice: auto-listen uses Android SpeechRecognizer** — consistent high-accuracy throughout conversation

## v0.0.62 (2026-03-30)
- **Fix: auto-listen uses Android SpeechRecognizer** — after Jane speaks, auto-listen now uses Google cloud STT (same as mic button) instead of falling back to Vosk

## v0.0.61 (2026-03-30)
- **Fix: mic button voice response** — messages from mic button now correctly trigger voice response (fromVoice was missing)
- **Fix: TTS for SpeechRecognizer path** — direct TTS when VoiceController is not active

## v0.0.60 (2026-03-29)
- **Voice: STT silence timeout** — mic button now passes 6s/4s silence hints to Google STT so it doesn't cut off mid-sentence
- **Auto-scroll fix** — Jane's streaming response now stays pinned to the bottom; user scrolling up correctly pauses auto-scroll
- **Voice reply fix** — mic button now passes `fromVoice=true` so Jane speaks her response back after you speak to her

## v0.0.59 (2026-03-29)
- **Removed TTS toggle** — voice input always gets voice response, text input gets text only. Mute button stops mid-speech.

## v0.0.58 (2026-03-29)
- **Notification deep-link:** Tapping a Jane notification now opens her chat directly instead of the home screen
- **ACK TTS in Android:** Jane speaks the [ACK] acknowledgment immediately during streaming
- **Notification title fix:** Download notification now shows full version ("Vessences update v0.0.58")
- **Continuous voice conversation:** Auto-listen restarts in command mode after Jane speaks (not wake-word mode)

## v0.0.57 (2026-03-29)
- **Voice: extended listening window** — auto-listen timeout bumped from 6s to 30s; idle timeout from 8s to 30s

## v0.0.56 (2026-03-29)
- **Voice: TTS fallback** — always speaks something when response completes; fixes silent responses during tool-heavy work
- **Voice: stream-end bug fix** — accumulated text was being dropped when stream ended without a done event

## v0.0.55 (2026-03-29)
- **Voice: longer silence timeout** — bumped from 1.3s to 4s so you can pause and think without getting cut off
- **Voice: listening beep** — short beep plays when mic starts recording so you know when to speak
- **Voice: stop listening button** — mic button turns into a red X while listening; tap to cancel immediately
- **Version: single source of truth** — version.json at project root drives both Android app and server

## v0.0.54 (2026-03-29)
- **Android: ACK TTS** — Jane now speaks the [ACK] acknowledgment immediately during streaming
- **Android: Continuous voice conversation** — after Jane speaks, auto-listen restarts in command mode (not wake-word mode), enabling free-flowing voice conversation
- **Android: Strip [ACK] tags** from displayed response text

## v0.0.53 (2026-03-29)
- **Fix auto-scroll during streaming:** Use instant scroll instead of animated scroll to prevent animation queue buildup when deltas arrive rapidly. Scroll pauses correctly when user scrolls up to read history.

## v0.0.52 (2026-03-28)
- **Android update** (user-initiated changes)

## v0.0.51 (2026-03-28)
- **Briefing: Brief/Full audio buttons** on every article card (no need to open detail sheet)
- **Briefing: Archive button** per article — dims card and moves to bottom; tap again to restore
- **Briefing: Archive viewer** via history icon in top bar (browse past days' briefings)

## v0.0.50 (2026-03-28)
- **Comprehensive System Architecture:** Complete rewrite with hub + 11 subpages covering all Vessence components in plain language

## v0.0.49 (2026-03-28)
- **Fix System Architecture crash:** SettingsViewModel now created with proper factory (was missing Context)
- **Fix Briefing crash:** Added ProGuard keep rule for Gson TypeToken (R8 was stripping generic type info)

## v0.0.48 (2026-03-28)
- **Fix download notification:** Version number now leads the title ("v0.0.48 Vessences") so it's never truncated

## v0.0.47 (2026-03-28)
- **Fix download notification:** Shows "Vessences v0.0.47" instead of truncated "Update v0.0"

## v0.0.46 (2026-03-28)
- **Fix APK signing:** Release APK now properly signed (was unsigned, causing "package appears invalid" on install)
- **Briefing Read All:** Both Brief and Full audio options on Android and web
- **TTS chunking + Opus:** XTTS-v2 splits text by sentence, compresses to Opus/OGG (~10x smaller)

## v0.0.45 (2026-03-27)
- User code updates

## v0.0.44 (2026-03-27)
- **Provider error detection:** Stderr monitoring detects rate limit/billing errors from Claude, Gemini, OpenAI CLIs
- **Runtime provider switching:** One-click switch to another provider when current one hits limits (web + Android)
- **Intermediary steps on Android:** Thought, tool_use, tool_result events now show in Android chat (collapsible disclosure triangle)
- **TTS mode improvements:** Short conversational answers (2-5 sentences) instead of long detailed responses when TTS is on

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
