# Job #078 — Jane Windows Desktop App

Priority: 3
Status: pending
Created: 2026-04-20
Estimated effort: Large (multi-week)

## Summary

Build a native Windows desktop application for Jane using Tauri v2 (Rust + WebView2), achieving feature parity with the Android app. The app communicates with the existing jane_web server (port 8081) using the same NDJSON streaming API and provides native Windows integrations (system tray, toast notifications, global hotkey, share target, startup registration).

---

## Architecture Spec

### 1. Overview and Goals

**Primary goal:** Give Windows users a first-class Jane experience equivalent to the Android app — persistent system tray presence, native notifications, voice I/O, vault file browsing, essence views, and auto-updates — all in a lightweight native binary.

**Non-goals for this project:**
- Phone-specific features (SMS sending, call placement, notification listener, contacts sync). SMS can still be sent via the server relay if needed in the future.
- Wake word detection (requires always-on mic; deferred to a future phase).
- Offline mode (Jane requires the server; Windows app is a rich client).

**Design principles:**
1. **Server is the brain.** The Windows app is a client — all LLM processing, memory, context building, and tool execution happen on the jane_web server. The app sends messages and renders responses.
2. **Reuse web UI where possible.** The existing `vault_web/templates/jane.html` (2469 lines) is a mature, full-featured chat UI. Load it in the WebView2 for chat, vault, briefing, and essence views rather than rebuilding from scratch.
3. **Native shell, web content.** Tauri's Rust backend handles system tray, notifications, hotkeys, file system, and auto-update. The frontend is the existing web UI loaded via WebView2, extended with a thin TypeScript bridge for native integration.
4. **Small footprint.** Target <15 MB installed size (vs Electron's 150+ MB).
5. **No conversation bleed.** Windows must identify account, device, and chat thread separately so it can coexist with Android, web, and future users without sharing pending actions, request gates, persistent brain context, or session summaries.

### 1.1 Identity and Session Isolation

This app must follow the multi-user session isolation rules in `job_077_multi_user_account_isolation.md`. The Windows client is another first-class device, not a special browser tab.

Each Windows install must persist:

| Field | Example | Storage | Purpose |
|:------|:--------|:--------|:--------|
| `device_id` | `windows_7f6d4b8f-...` | `%APPDATA%/com.vessences.jane/settings.json`, DPAPI-protected if bundled with secrets | Separates this PC from Android/web devices |
| `client_session_uuid` | full UUID | app settings, resettable from UI | Separates chat threads on the same PC |
| `app_instance_id` | full UUID | app settings | Crash/update diagnostics without exposing device fingerprint |
| `server_url` | `https://jane.vessence.com` | app settings | Remote/local server target |

Every chat request must send both `device_id` and `session_id` (`client_session_uuid`). The server should resolve the canonical conversation key once:

```
<sanitized_email>__<device_id>__<client_session_uuid>
```

Windows must never rely on a generic ID like `jane_windows` or an 8-character suffix. If the app opens multiple chat windows later, each chat window gets its own `client_session_uuid` while sharing the same `device_id`.

Backend stores that must use the resolved canonical key:

- Jane in-memory `_sessions`
- per-session `request_gate`
- persistent Claude/Codex/Gemini manager sessions
- `ConversationManager`
- SQLite ledger rows
- session summaries
- recent-turn FIFO
- pending action resolver state
- prewarm/prefetch caches
- turn-dedupe replay buffers

If two Windows devices send requests simultaneously, they may contend for the same standing brain/local LLM capacity, but they must not share conversational state. Queueing should happen only inside shared model capacity, not because two devices collided on the same conversation key.

### 2. Tech Stack

| Layer | Technology | Rationale |
|:------|:-----------|:----------|
| **Native shell** | Tauri v2 (Rust) | Small binary, native Windows APIs, built-in updater, system tray, WebView2 |
| **Frontend** | WebView2 (Edge/Chromium) | Ships with Windows 10/11; no bundled browser needed |
| **UI content** | Existing `jane.html` + new TypeScript bridge | Reuse 2400+ lines of proven chat UI; add Windows-specific JS |
| **Build system** | Cargo + npm (Tauri CLI) | Standard Tauri toolchain |
| **Installer** | NSIS (Tauri default) or WiX/MSI | Tauri bundles both options out of the box |
| **Auto-updater** | `tauri-plugin-updater` | Built-in, points to `marketing_site/downloads/` |
| **Voice input** | Web Speech API (WebView2) | Same API used in `jane.html` today (`_startMicListening()` at L1756) |
| **Voice output** | Web Speech API or server TTS (`/api/tts/generate`) | Match existing web behavior; server TTS for higher quality |
| **IPC** | Tauri command system (`#[tauri::command]`) | Rust ↔ TypeScript bridge for native features |

### 3. Project Structure

```
windows/
├── src-tauri/
│   ├── Cargo.toml                # Rust dependencies
│   ├── tauri.conf.json           # Tauri configuration (window, updater, permissions)
│   ├── capabilities/
│   │   └── default.json          # Tauri v2 capability permissions
│   ├── src/
│   │   ├── main.rs               # Entry point, app setup, plugin registration
│   │   ├── tray.rs               # System tray icon, menu, click handler
│   │   ├── notifications.rs      # Windows toast notification bridge
│   │   ├── hotkey.rs             # Global hotkey registration (Ctrl+Space)
│   │   ├── autostart.rs          # Windows startup registry entry
│   │   ├── share_target.rs       # Windows Share Target registration
│   │   ├── vault_sync.rs         # Vault file sync via server API
│   │   ├── updater.rs            # Auto-update configuration
│   │   └── commands.rs           # Tauri IPC command handlers
│   ├── icons/
│   │   ├── icon.ico              # App icon (multi-res ICO)
│   │   ├── icon.png              # 512x512 PNG for notifications
│   │   └── tray-icon.png         # 32x32 system tray icon
│   └── build.rs                  # Build script
├── src/
│   ├── index.html                # Minimal shell that loads jane.html content
│   ├── bridge.ts                 # TypeScript bridge: Tauri IPC ↔ web UI
│   ├── native-notifications.ts   # Push notification handler
│   ├── vault-sync.ts             # Vault sync UI integration
│   ├── theme.ts                  # System dark/light mode detection
│   └── styles/
│       └── windows-overrides.css # Platform-specific CSS tweaks
├── package.json
├── tsconfig.json
└── README.md                     # Build instructions
```

### 4. Feature Mapping (Android → Windows)

| # | Android Feature | Android Implementation | Windows Equivalent | Notes |
|:--|:----------------|:----------------------|:-------------------|:------|
| 1 | **Chat with Jane** | `ChatScreen.kt` + `ChatViewModel.kt` (1564 lines), NDJSON streaming via `ChatRepository.kt` | Load existing `jane.html` in WebView2 | Same SSE/NDJSON protocol. Web UI already handles streaming, thoughts, tool use display. |
| 2 | **Voice input** | `SpeechRecognizer` (Android system STT) | Web Speech API in WebView2 (`_startMicListening()` already in jane.html L1756) | Already implemented in web UI. |
| 3 | **TTS responses** | `AndroidTtsManager.kt` + `HybridTtsManager.kt` (server TTS fallback) | Web Speech API + server TTS (`/api/tts/generate`) | Already implemented in web UI (`speakText()` at L1803). |
| 4 | **Essence views** | `EssencesScreen.kt`, `EssenceViewRouter.kt` | Load `/essences` web route in WebView2 | Web UI already renders essence list, activation, and per-essence pages. |
| 5 | **Vault file browser** | `VaultScreen.kt` + `VaultViewModel.kt` + `FileViewerScreen.kt` | Load `/vault` web route in WebView2 | Web UI already has vault browser. |
| 6 | **Music playlists** | `MusicScreen.kt` + `MusicViewModel.kt` + Media3 `PlaybackService` | Load `/vault` music section in WebView2; HTML5 `<audio>` playback | Web already supports audio playback via `/api/files/serve/` with Range requests. |
| 7 | **Daily Briefing** | `BriefingScreen.kt` (1080 lines) + `BriefingViewModel.kt` (569 lines) | Load `/briefing` web route in WebView2 | `briefing.html` (1361 lines) already exists with full topic filtering, TTS, search. |
| 8 | **Share-to** | `ShareReceiverActivity.kt` (362 lines) — Android share sheet target | Windows Share Target registration via `share_target.rs` + drag-and-drop handler | Register as a Windows Share Target for URLs/text/files. Also support drag-and-drop onto the window or system tray icon. |
| 9 | **Push notifications** | `ChatNotificationManager.kt` + `IncomingMessageAnnouncer.kt` + `VessenceNotificationListener.kt` | Windows toast notifications via `tauri-plugin-notification` + SSE listener | Listen to `/api/jane/live` SSE endpoint (same as `LiveBroadcastListener.kt` on Android) and show Windows toast notifications for proactive messages. |
| 10 | **Dark/light mode** | `ThemePreferences.kt` + `VessenceTheme.kt` (Material 3) | Detect Windows system theme via `window.matchMedia('(prefers-color-scheme: dark)')` + Tauri `theme()` API | Web UI already supports dark/light via CSS variables. Bridge system preference to web UI. |
| 11 | **Conversation sync** | `ChatPersistence.kt` (JSON file-based) + `ChatPreferences.getJaneSessionId()` | Same session ID via server API; `jane.html` already maintains session state | Server is the sync point. Same session cookie = same conversation across devices. |
| 12 | **Auto-update** | `UpdateChecker.kt` — polls `/api/app/latest-version`, uses DownloadManager | `tauri-plugin-updater` — checks `marketing_site/downloads/jane-windows-update.json` | Tauri's built-in updater downloads and applies MSI/NSIS updates silently. |
| 13 | **Crash reporting** | `CrashReporter.kt` — POST to `/api/crash-report` | Rust panic handler + JS error handler → POST to `/api/crash-report` | Same server endpoint. |

**Skipped Android features (phone-specific):**
- `ContactsSyncManager`, `SmsSyncManager` — phone contacts/SMS
- `ContactsCallHandler`, `ContactsSmsHandler` — phone calls/SMS sending
- `MessagesReadInboxHandler`, `MessagesFetchUnreadHandler` — reading phone SMS
- `AlwaysListeningService`, `OpenWakeWordDetector` — always-on wake word (deferred)
- `VessenceNotificationListener` — reading phone notifications

### 5. Communication with Server

The Windows app communicates with `jane_web` (port 8081) using the exact same protocol as Android and the web browser.

**Primary endpoints used:**

| Endpoint | Method | Purpose |
|:---------|:-------|:--------|
| `POST /api/jane/chat/stream` | POST | Streaming chat (NDJSON) |
| `POST /api/jane/init-session` | POST | Initialize session |
| `POST /api/jane/session/end` | POST | End session |
| `GET /api/jane/live` | GET (SSE) | Real-time updates, proactive messages |
| `GET /api/jane/announcements` | GET | System announcements |
| `POST /api/auth/google-token` | POST | OAuth authentication |
| `POST /api/auth/check` | POST | Session validation |
| `GET /api/essences` | GET | List essences |
| `POST /api/essences/{name}/activate` | POST | Activate essence |
| `GET /api/files/list/{path}` | GET | Vault directory listing |
| `GET /api/files/serve/{path}` | GET | Serve vault files |
| `POST /api/files/upload` | POST | Upload files |
| `GET /api/briefing/articles` | GET | News articles |
| `GET /api/app/settings` | GET | User preferences |
| `GET /api/playlists` | GET | Music playlists |
| `POST /api/tts/generate` | POST | Text-to-speech |
| `GET /api/app/latest-version` | GET | Version check for auto-update |

**Required server protocol additions before Windows MVP:**

| Addition | Reason |
|:---------|:-------|
| `device_id` in `POST /api/jane/chat/stream` and `POST /api/jane/init-session` | Enables canonical conversation key and prevents cross-device bleed |
| `platform: "windows"` and `app_version` in chat payloads | Lets server apply Windows-specific tool/capability rules and diagnostics |
| `POST /api/desktop/register-device` or equivalent | Allows first-run device registration, display name, and trusted-device association |
| `GET /api/desktop/bootstrap` | Returns server capabilities, auth status, current user, update endpoints, and whether managed-user isolation is enforced |
| `POST /api/crash-report` support for `platform=windows` | Reuses Android crash pipeline but separates Windows incidents |

**Streaming protocol (same NDJSON as Android, see architecture doc section 10.4):**
```json
{"type": "status", "data": "Loading memory..."}
{"type": "thought", "data": "thinking text"}
{"type": "tool_use", "data": {"tool": "name", "input": "..."}}
{"type": "tool_result", "data": "result text"}
{"type": "delta", "data": "token"}
{"type": "done", "data": "full response"}
{"type": "error", "data": "error message"}
```

**Server discovery:**
- Default: `http://localhost:8081` (same machine)
- Configurable: settings page allows entering a remote server URL (for users running jane_web on a different machine or via Cloudflare tunnel)
- Stored in: `%APPDATA%/com.vessences.jane/settings.json`

**Authentication:**
- Primary: system browser OAuth via a loopback or custom URI handoff. Google often blocks OAuth inside embedded WebViews, so the app should open the system browser and receive a one-time login result back into Tauri.
- Fallback: OTP login (same as Android `LoginScreen.kt`)
- Session cookie stored in WebView2's persistent cookie storage (encrypted by Windows DPAPI)

**Auth implementation detail that must be solved early:**

System-browser OAuth and WebView2 do not automatically share cookies. The MVP needs one explicit handoff path:

1. Windows app opens `GET /auth/google?desktop_callback=<nonce>` in the system browser.
2. Server completes Google OAuth in the browser.
3. Server redirects to a registered custom URI such as `jane://auth-complete?code=<one_time_code>`.
4. Tauri receives the URI and exchanges the one-time code for a Jane session cookie via a new endpoint such as `POST /api/desktop/exchange-login-code`.
5. The app injects/stores that cookie in the WebView2 profile and uses it for API calls.

Do not assume the existing web OAuth cookie will appear inside WebView2. If this handoff is not implemented, login may work in the browser but the desktop app will still appear unauthenticated.

### 6. Native Windows Integration Points

#### 6.1 System Tray

**Implementation:** `src-tauri/src/tray.rs`

- Jane icon in the Windows notification area (system tray)
- Left-click: show/focus the main window
- Right-click context menu:
  - "Open Jane" — show window
  - "Quick Chat..." — summon overlay input (see 6.3)
  - separator
  - "Vault Browser" — navigate to vault view
  - "Daily Briefing" — navigate to briefing view
  - separator
  - "Settings" — open settings
  - "Check for Updates"
  - "Quit Jane"
- Tray icon badge: unread notification dot (colored circle overlay)
- Minimize to tray instead of closing (configurable; default: minimize to tray)

#### 6.2 Windows Toast Notifications

**Implementation:** `src-tauri/src/notifications.rs`

- Use `tauri-plugin-notification` for Windows toast notifications
- Proactive messages from Jane (via `/api/jane/live` SSE):
  - SSE listener runs in the **Rust backend** (via `reqwest-eventsource`), NOT in JS — WebView2 may be suspended when minimized to tray, killing JS-based SSE connections
  - On `done` or `announcement` events: show toast notification via Rust
  - Toast click: open main window and scroll to message
- Notification categories:
  - **Jane message** — proactive messages, task completions
  - **Update available** — new version notification
  - **Briefing ready** — daily briefing is available
- Notification actions (toast buttons):
  - "Reply" — open chat and focus input
  - "Dismiss" — close notification

#### 6.3 Global Hotkey (Ctrl+Space)

**Implementation:** `src-tauri/src/hotkey.rs`

- Register `Ctrl+Space` as global hotkey via `tauri-plugin-global-shortcut`
- On press:
  1. If window is hidden: show window, focus input
  2. If window is visible but not focused: bring to front, focus input
  3. If window is focused: toggle a compact overlay chat mode (small floating window)
- Configurable hotkey in settings (stored in `%APPDATA%/com.vessences.jane/settings.json`)
- Graceful handling if hotkey is already registered by another app (Ctrl+Space conflicts with PowerToys Run, Listary, and some IME toggles) — show "Hotkey registration failed" in Settings and allow rebinding

#### 6.4 Windows Share Target

**Implementation:** `src-tauri/src/share_target.rs`

- Register as a Windows Share Target for:
  - Text/URLs — send to Jane as a chat message (like Android's `ShareReceiverActivity`)
  - Files — upload to vault via `/api/files/upload`
  - Images — upload + optionally ask Jane to describe/analyze
- Also support drag-and-drop:
  - Files dragged onto the main window → upload dialog
  - Files dragged onto the system tray icon → quick upload to vault root
  - URLs dragged → summarize via Jane

#### 6.5 File System Access (Vault Sync)

**Implementation:** `src-tauri/src/vault_sync.rs`

- Two-way vault sync between server and a local Windows directory
- Default sync folder: `%USERPROFILE%\Documents\Jane Vault\`
- Sync mechanism:
  1. On app startup: compare local file checksums with server via `GET /api/files/list/{path}` (which returns file metadata including modification times)
  2. Pull new/modified server files to local
  3. Push new/modified local files to server via `POST /api/files/upload`
  4. Use file system watcher (`notify` crate in Rust) for real-time local change detection
- Conflict resolution: server wins by default, but if a local file was modified more recently (UTC timestamp comparison), rename the server version as `.conflict` to avoid silent data loss — desktop users edit files with external editors more than mobile users
- Selective sync: user can choose which vault folders to sync locally
- Sync status indicator in system tray tooltip

#### 6.6 Windows Startup Registration

**Implementation:** `src-tauri/src/autostart.rs`

- Use `tauri-plugin-autostart` to add/remove registry entry at `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
- Default: enabled (start minimized to tray on Windows boot)
- Toggle in settings UI
- Start minimized: app launches to tray without showing window

### 7. Voice I/O

**Input (Speech-to-Text):**
- Primary: Web Speech API in WebView2 (same as `_startMicListening()` in jane.html L1756-1794)
- Already implemented in the web UI — no additional work needed for MVP
- The existing mic button and speech recognition flow works identically in WebView2
- Risk: Web Speech recognition support in WebView2 can vary by Windows version, Edge runtime, language pack, and privacy settings. The MVP must feature-detect it and show a clear fallback instead of a dead mic button.
- Fallback option: native Windows speech recognition through WinRT/Speech SDK or server-side transcription endpoint in a later phase.

**Output (Text-to-Speech):**
- Primary: Web Speech API (same as `speakText()` in jane.html L1803-1823)
- Enhanced: Server TTS via `/api/tts/generate` (XTTS, higher quality)
- Already implemented in web UI — both paths work in WebView2
- Toggle between browser TTS and server TTS in settings (same as web UI)
- Server TTS should be preferred for parity with Android sentence-level playback, but browser TTS remains the offline/low-latency fallback.

**Voice acceptance requirements:**

- Mic permission prompt appears once and can be recovered from Settings if denied.
- If WebView2 STT is unavailable, the UI states that voice input is unavailable on this Windows install.
- TTS must not speak internal tags, tool JSON, class protocols, or duplicate final confirmations. See the Android transcript evidence in `job_077_multi_user_account_isolation.md` for the current leak pattern.
- Voice mode should preserve the same conversation key as typed chat from the same window.

**Future enhancement (post-MVP):**
- Windows Speech Platform API via Rust for always-listening wake word detection
- Would mirror Android's `AlwaysListeningService` but using Windows audio APIs
- Requires background audio capture permission and careful power management

### 8. Vault Sync

**Architecture:**

```
┌──────────────────┐          ┌──────────────────┐
│  Windows App     │          │  jane_web Server  │
│                  │          │  (port 8081)      │
│  Local Vault Dir │◄────────►│  /api/files/*     │
│  (Documents\     │  HTTP    │                   │
│   Jane Vault\)   │          │  Vault Dir        │
│                  │          │  (~/ambient/vault/)│
└──────────────────┘          └──────────────────┘
```

**Sync protocol (reuses existing server API):**

1. **Initial sync:** `GET /api/files/list/` recursively to build remote file tree. Compare with local tree. Download missing/newer files via `GET /api/files/serve/{path}`.
2. **Incremental sync:** Poll `GET /api/files/list/{path}` periodically (every 60s by default). Use modification timestamps to detect changes.
3. **Local changes:** Rust `notify` crate watches local directory. On file create/modify: `POST /api/files/upload`. On file delete: `DELETE /api/files/{path}` (requires new server endpoint — must be implemented in Phase 2 for vault sync to work correctly; without it, deleted files reappear on next sync).
4. **Bandwidth optimization:** Only sync file metadata on polls. Download file content on-demand or when user opens vault browser.

**Server API gaps to close before reliable sync:**

- `GET /api/files/list/{path}` needs stable machine-readable metadata: relative path, file size, UTC modified timestamp, content hash or ETag, MIME type, and directory flag.
- Add recursive or paginated tree listing so the Windows app does not walk large vaults through hundreds of small requests.
- Add `DELETE /api/files/{path}` with server-side auth, path traversal protection, and Chroma file-index cleanup.
- Add overwrite/conflict controls to `POST /api/files/upload`, such as `If-Match`/ETag or explicit `conflict_strategy`.
- Add a per-user vault root check for managed users from `job_077_multi_user_account_isolation.md`; Windows sync must never mirror Chieh's global vault for another account.
- File index Chroma entries must update when Windows sync uploads, renames, or deletes files.
- All timestamps must be UTC and timezone-aware. Do not compare local Windows wall-clock strings to server timestamps.

**Sync safety rules:**

- Default MVP mode should be on-demand read/download, not full two-way sync.
- Two-way sync should be opt-in per folder after conflict handling and delete semantics are tested.
- Never delete local or server files silently. First implementation should move deleted/overwritten files into a `.jane-conflicts/` or `.jane-trash/` area with a visible recovery path.
- Ignore transient/editor files by default: `~$*`, `.tmp`, `.crdownload`, `.part`, Office lock files, and files still open for writing.
- Use Windows long-path-safe file operations (`\\?\` prefix in Rust) and normalize Unicode filenames consistently before comparing paths.

**Sync modes (user-configurable):**
- **On-demand** (default for MVP): Files visible in vault browser; downloaded when opened
- **Selective sync**: User picks folders to keep locally synced
- **Full sync**: Mirror entire vault locally (for power users)

### 9. Auto-Update Mechanism

**Implementation:** Tauri's built-in `tauri-plugin-updater`

**Update flow:**
1. App checks `https://<server>/downloads/jane-windows-update.json` on startup and every 6 hours
2. Update manifest format (Tauri standard):
   ```json
   {
     "version": "1.2.3",
     "notes": "Bug fixes and performance improvements",
     "pub_date": "2026-04-20T00:00:00Z",
     "platforms": {
       "windows-x86_64": {
         "url": "https://<server>/downloads/jane-windows-v1.2.3-setup.exe",
         "signature": "<ed25519 signature>"
       }
     }
   }
   ```
3. If newer version available: show toast notification + update banner in app
4. User clicks "Update": download in background, apply on next restart
5. Silent updates (optional): download and install without user interaction

**Integration with existing version system:**
- Server endpoint `GET /api/app/latest-version` already returns version info (used by Android `UpdateChecker.kt`)
- Add a `windows` section to the response, or use a separate update manifest at `marketing_site/downloads/jane-windows-update.json`
- Version bumping: extend `startup_code/bump_android_version.py` or create `bump_windows_version.py` that updates `windows/src-tauri/tauri.conf.json`

**Code signing:**
- Self-signed for initial development
- Purchase an EV code signing certificate for production distribution (eliminates SmartScreen warnings)
- Signature included in update manifest for verification

### 10. Build and Distribution

**Build toolchain:**
```bash
# Prerequisites
rustup install stable
npm install

# Development
cd windows/
npm run tauri dev

# Production build
npm run tauri build
# Output: windows/src-tauri/target/release/bundle/nsis/Jane-Setup-x.y.z.exe
#         windows/src-tauri/target/release/bundle/msi/Jane-x.y.z.msi
```

**Distribution artifacts:**
| Artifact | Size (est.) | Purpose |
|:---------|:------------|:--------|
| `Jane-Setup-x.y.z.exe` | ~8-12 MB | NSIS installer (recommended) |
| `Jane-x.y.z.msi` | ~8-12 MB | MSI installer (enterprise/GPO) |
| `jane-windows-update.json` | <1 KB | Update manifest |

**Deployment to marketing site:**
- Installers placed in `marketing_site/downloads/`
- Update `marketing_site/index.html` and `marketing_site/install.html` with Windows download links
- Add a "Download for Windows" button alongside the existing Android download

**CI/CD (future):**
- GitHub Actions workflow: `windows-build.yml`
- Trigger: push to main with changes in `windows/`
- Steps: install Rust + Node, `npm run tauri build`, sign, upload artifacts to releases
- Could extend existing `.github/workflows/docker-publish.yml`

**System requirements:**
- Windows 10 (build 1903+) or Windows 11
- WebView2 Runtime (ships with Windows 10 21H2+ and all Windows 11; installer bundles bootstrapper as fallback)
- ~50 MB disk space installed
- Network access to jane_web server

### 11. MVP vs Full Feature Set Phasing

#### Phase 1: MVP (Weeks 1-3) — Chat + System Tray + Notifications

**Goal:** A usable Jane client that lives in the system tray and supports chat.

**Deliverables:**
- [ ] Tauri v2 project scaffolding (`windows/` directory)
- [ ] Load existing `jane.html` in WebView2 as the main view
- [ ] Server URL configuration (settings page or first-run dialog)
- [ ] Google OAuth login through system browser plus desktop one-time-code handoff into WebView2 cookie storage
- [ ] Persistent Windows `device_id` and full-UUID chat `session_id` sent with every Jane request
- [ ] Server-side canonical conversation key support verified against Android/web sessions
- [ ] System tray icon with context menu (Open, Settings, Quit)
- [ ] Minimize to tray (close button minimizes, not quits)
- [ ] Global hotkey (Ctrl+Space) to summon/hide window
- [ ] Windows toast notifications for Jane proactive messages (SSE listener)
- [ ] Auto-start on Windows boot (optional, via settings)
- [ ] Dark/light mode following Windows system theme
- [ ] Basic crash reporting to server

**What works "for free" by loading jane.html:**
- Full chat UI with streaming, thoughts, tool use display
- Voice input (Web Speech API mic button)
- Voice output (browser TTS + server TTS toggle)
- Essence browsing and activation
- Message queue
- Provider switching (Claude/Gemini/OpenAI)
- Permission approval UI
- File attachments via file picker

#### Phase 2: Essences + Vault + Briefing (Weeks 4-6)

**Goal:** Full content browsing and vault integration.

**Deliverables:**
- [ ] In-app navigation: Chat | Vault | Briefing | Essences | Settings (tab bar or sidebar)
- [ ] Vault browser: load `/vault` web route with native file-open integration
- [ ] "Open in Explorer" for vault files (Tauri shell commands)
- [ ] Vault sync: selective folder sync to local `Documents\Jane Vault\`
- [ ] File system watcher for local vault changes
- [ ] Briefing view: load `/briefing` web route
- [ ] Music playback: HTML5 audio via vault file serving
- [ ] Essence views: load `/essence/{name}` routes
- [ ] Drag-and-drop file upload (onto window → vault upload)
- [ ] Settings page: server URL, theme, hotkey config, sync folders, auto-start toggle

#### Phase 3: Voice + Share + Polish (Weeks 7-9)

**Goal:** Native Windows integration and distribution readiness.

**Deliverables:**
- [ ] Windows Share Target registration (receive shared text/URLs/files)
- [ ] Auto-updater: check `marketing_site/downloads/` for new versions
- [ ] Update manifest generation in build pipeline
- [ ] NSIS installer with proper icons, Start Menu shortcut, uninstaller
- [ ] Code signing (self-signed initially, EV cert for production)
- [ ] Marketing site updates: Windows download button, install instructions
- [ ] Keyboard shortcuts: Ctrl+Enter to send, Escape to minimize, etc.
- [ ] Window state persistence: remember size, position, maximized state
- [ ] Notification click handling: deep-link to specific chat message
- [ ] Connection status indicator (server reachable/unreachable)
- [ ] Offline graceful degradation (show cached conversation, queue messages)

#### Phase 4: Advanced (Weeks 10+, stretch goals)

- [ ] Always-listening wake word via Windows audio APIs
- [ ] Multi-window support (detach vault browser, briefing into separate windows)
- [ ] Windows widgets (Windows 11 widget board integration)
- [ ] Clipboard monitoring (optional): detect copied text, offer to send to Jane
- [ ] Screen capture: screenshot region → send to Jane for analysis
- [ ] Portable mode: run from USB drive without installation
- [ ] ARM64 Windows build (Surface Pro X, Snapdragon laptops)

### 12. Security Considerations

**Authentication:**
- Session cookies stored in WebView2's persistent cookie storage (encrypted by Windows DPAPI)
- No credentials stored in plain text
- OAuth tokens managed by the server, not the client
- Session expiry follows server policy

**Network:**
- All communication over HTTP to localhost (same-machine deployment) or HTTPS to remote server
- Tauri CSP (Content Security Policy) restricts WebView2 to only connect to the configured server URL
- No arbitrary URL loading in the main WebView2 context

**File system:**
- Tauri v2 security scoping: app can only access:
  - `%APPDATA%/com.vessences.jane/` (app config/data)
  - User-selected vault sync directory
  - Temp directory for downloads
- No unrestricted file system access
- Vault sync respects server-side auth (session cookie required for all API calls)

**Auto-update:**
- Update manifests signed with Ed25519 (Tauri's default)
- Signature verification before applying updates
- Update URLs pinned to configured server (no redirect-following to arbitrary hosts)

**Privacy:**
- No telemetry sent to third parties
- Crash reports go only to the user's own jane_web server
- Voice data processed locally via Web Speech API (browser's built-in STT)
- No data leaves the local network unless the user configures a remote server

**System integration security:**
- Global hotkey only summons the Jane window (no command injection)
- Share target validates input before sending to server
- Auto-start registry key is user-scoped (HKCU, not HKLM) — no admin rights needed

---

## Implementation Plan

### Pre-work (before Phase 1)
1. Install Rust toolchain and Tauri CLI on the development machine
2. Create `windows/` directory in the vessence repo
3. Run `npm create tauri-app@latest` to scaffold the project
4. Verify `jane.html` loads correctly in WebView2 (test basic chat flow)
5. Identify any jane.html features that need polyfills or adjustments for WebView2

### Phase 1 Execution (MVP)
1. Configure `tauri.conf.json`: window title, icon, size, CSP for server URL
2. Add first-run setup: server URL prompt, server bootstrap check, OAuth login handoff
3. Persist and send Windows `device_id`, full chat `session_id`, `platform=windows`, and `app_version`
4. Verify server canonical conversation key before enabling chat
5. Implement `tray.rs`: system tray icon + context menu
6. Implement `hotkey.rs`: Ctrl+Space global shortcut
7. Implement `autostart.rs`: Windows startup registration
8. Implement `notifications.rs`: Rust SSE listener + toast notifications
9. Implement minimize-to-tray behavior
10. Wire up dark/light theme detection via `bridge.ts`
11. Add crash reporting (Rust panic handler + JS error boundary)
12. Test on Windows 10 and Windows 11

### Phase 2 Execution
1. Add navigation sidebar/tabs to switch between Chat/Vault/Briefing/Essences
2. Implement `vault_sync.rs`: initial sync + file watcher
3. Add "Open in Explorer" and drag-and-drop handlers
4. Test audio playback (HTML5 audio through WebView2)
5. Settings page with all configuration options

### Phase 3 Execution
1. Implement Windows Share Target manifest
2. Configure `tauri-plugin-updater` with update endpoint
3. Create update manifest generation script
4. Build NSIS installer with icons and shortcuts
5. Update marketing site with Windows download section
6. End-to-end testing: install → first-run → chat → vault → update → uninstall

---

## Acceptance Criteria

### Phase 1 (MVP) Complete When:
- [ ] `npm run tauri build` produces a working Windows installer
- [ ] App loads `jane.html` and user can chat with Jane (streaming responses work)
- [ ] System-browser OAuth handoff creates a valid WebView2/API session without requiring embedded Google login
- [ ] Every chat/init request sends `device_id`, full UUID `session_id`, `platform=windows`, and `app_version`
- [ ] Two Windows installs logged into the same account use different canonical conversation keys and cannot answer each other's pending follow-ups
- [ ] System tray icon appears; left-click shows window, right-click shows menu
- [ ] Ctrl+Space summons the window from any application
- [ ] Toast notification appears when Jane sends a proactive message
- [ ] App starts minimized to tray on Windows boot (when enabled)
- [ ] Dark/light mode matches Windows system setting
- [ ] Voice UI feature-detects STT support and fails visibly if WebView2 speech recognition is unavailable
- [ ] App survives 24-hour run without memory leaks or crashes

### Phase 2 Complete When:
- [ ] User can browse vault files and open them locally
- [ ] Vault sync keeps a local folder in sync with the correct account vault, never another user's vault
- [ ] Delete, overwrite, and conflict handling are tested before two-way sync is enabled
- [ ] Briefing articles display with TTS playback
- [ ] Essences can be browsed, loaded, and activated
- [ ] Music playlists play audio through the app

### Phase 3 Complete When:
- [ ] Windows Share dialog includes "Jane" as a target
- [ ] Auto-updater detects and installs new versions
- [ ] Installer is code-signed (no SmartScreen warning)
- [ ] `marketing_site/index.html` has a "Download for Windows" button
- [ ] Install → use → update → uninstall flow works cleanly

### Overall Complete When:
- [ ] Feature parity with Android app (minus phone-specific features)
- [ ] Installed size under 15 MB
- [ ] Binary passes Windows Defender and VirusTotal checks
- [ ] Architecture documented in `configs/CODE_MAP_WINDOWS.md`
- [ ] Entry added to `configs/Jane_architecture.md` section 15 (Communication Channels)

---

## Review Panel Notes (2026-04-20)

**Gemini** reviewed and approved the spec. Key feedback (all incorporated above):
1. **DELETE API required** — vault sync without file deletion is broken (files reappear). Added to Phase 2 requirements.
2. **OAuth in WebView2 risky** — Google blocks embedded browser OAuth. Switched to system browser loopback via `tauri-plugin-oauth`.
3. **SSE must run in Rust** — WebView2 suspends JS when minimized to tray, killing notifications. Moved SSE listener to Rust backend.
4. **Hotkey collision** — Ctrl+Space conflicts with PowerToys/IME. Added rebind UI and graceful failure handling.
5. **Vault sync conflict safety** — "Server wins" causes silent data loss on desktop. Added `.conflict` file strategy for locally-modified files.
6. **Windows long path support** — Use `\\?\` prefix in Rust file operations to bypass 260-char MAX_PATH limit.
7. **WebView2 bootstrapper** — NSIS installer must bundle the Evergreen Bootstrapper for Windows 10 LTSC/Enterprise machines missing WebView2.

**Codex** — timed out (unavailable).

## Follow-up Review Notes (2026-04-20)

Additional review after the multi-user conversation-bleed discussion:

1. **Conversation identity was underspecified.** Added a mandatory Windows
   `device_id`, full chat UUID, and canonical server key
   `<sanitized_email>__<device_id>__<client_session_uuid>`. This prevents two
   devices from sharing request gates, pending actions, FIFO, summaries, or
   persistent brain context.
2. **OAuth cookie handoff was too optimistic.** System-browser OAuth does not
   automatically authenticate the WebView2 profile. Added a one-time desktop
   login code exchange requirement.
3. **Server protocol needs Windows fields.** Added required `device_id`,
   `platform=windows`, and `app_version` request fields plus desktop bootstrap
   and device registration endpoints.
4. **Vault sync needs stronger server contracts.** Added metadata/hash/ETag,
   recursive listing, delete endpoint, conflict strategy, Chroma file-index
   cleanup, and per-user vault-root requirements.
5. **WebView2 speech support may vary.** Added STT feature detection and visible
   fallback requirements.
6. **MVP order changed.** Authentication and canonical conversation-key
   verification now happen before tray/hotkey polish, because otherwise a
   polished app could still leak conversation state.
