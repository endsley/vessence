# Vault Browser Website — Full Specification
**Project:** Amber Vault Browser
**Status:** Pending Build
**Last Updated:** 2026-03-17

---

## Overview

A Google Drive-style personal file browser for Chieh's vault (`/home/chieh/vessence/vault/`), hosted on this machine and made publicly accessible via Cloudflare Quick Tunnel. All file operations are done by talking to Amber in a chat panel — the UI reflects changes automatically. Built mobile-first and fully responsive.

---

## Tech Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Backend | FastAPI (Python) | Fits existing Python ecosystem |
| Frontend | HTML + Tailwind CSS + Alpine.js | Lightweight, no build step |
| PDF viewer | PDF.js | In-browser PDF rendering |
| Audio/Video | HTML5 `<audio>` / `<video>` | Native browser playback |
| Sessions/Devices/Shares/Playlists | SQLite (`vault_web.db`) | Simple, local |
| Tunnel | Cloudflare Quick Tunnel (`cloudflared`) | Free, no domain needed |
| Process manager | systemd | Auto-start on boot |

---

## Directory Structure

```
/home/chieh/vessence/vault_web/
├── main.py               # FastAPI app entry point
├── auth.py               # OTP, sessions, trusted devices
├── files.py              # Vault file browsing + metadata
├── amber_proxy.py        # Proxy requests to Amber ADK API
├── share.py              # Share link generation + validation
├── playlists.py          # Playlist CRUD
├── vault_web.db          # SQLite: sessions, devices, shares, playlists
├── static/
│   ├── app.js            # Frontend logic
│   ├── style.css         # Custom styles (minimal, Tailwind handles most)
│   └── icons/            # File type icons (SVG)
└── templates/
    ├── login.html
    └── app.html           # Main SPA shell
```

---

## Authentication System

### OTP Flow (Login)
1. User visits the site → redirected to `/login`
2. User clicks "Send me a code"
3. Server generates a 6-digit OTP, valid for **2 minutes**
4. Amber sends it to Chieh's private Discord channel: `"🔐 Vault login code: 483921 (expires in 2 min)"`
5. User enters the code → server validates
6. On success: session cookie set (1 week for trusted devices, session-only for new devices)
7. On failure: attempt counter incremented

### Failed Attempt Lockout
- **5 failed attempts** → 30-minute lockout
- During lockout, login form is disabled with countdown timer
- Chieh can ask Amber to unlock: `"Amber, unlock the vault"` → Amber clears the lockout
- Lockout is per-IP

### Trusted Device Flow
- After successful login on a **new device/browser**:
  - Prompt: *"Trust this device for 1 week?"*
  - If YES: set a persistent `trusted_device` cookie (1 week), store device fingerprint in SQLite
  - If NO: session cookie only (expires when browser closes)
- Trusted devices page: `/settings/devices` — lists all trusted devices with:
  - Browser/OS label
  - First seen date
  - Last used date
  - Revoke button

### Session
- Trusted device: 1 week
- Untrusted: browser session (expires on close)
- Session stored server-side in SQLite with device fingerprint

### Sharing (with spouse)
1. Chieh asks Amber: *"Share the images folder with spouse"*
2. Amber asks Chieh to confirm and generates a 6-digit share code
3. Chieh gives spouse the current tunnel URL + the share code
4. spouse visits the URL, enters the share code → gains access to that folder + all subfolders
5. Share links do not expire automatically — Chieh revokes them via Amber or the settings page
6. spouse uses Amber with Chieh's full memory (single-user for now; multi-user identity deferred)

---

## Layout — Main App

Two-tab layout, persistent across navigation:

```
┌─────────────────────────────────────────────────┐
│  🗄 Amber Vault          [Vault] [Chat] [Music]  │
├─────────────────────────────────────────────────┤
│                                                  │
│  (active tab content)                            │
│                                                  │
└─────────────────────────────────────────────────┘
```

**Tab 1 — Vault** (file browser)
**Tab 2 — Chat** (Amber conversation)
**Tab 3 — Music** (saved playlists)

---

## Tab 1 — Vault Browser

### Folder Navigation
- Mirrors vault folder structure exactly:
  ```
  vault/
  ├── audio/
  ├── documents/
  ├── images/
  ├── others/
  ├── pdf/
  ├── research/
  └── videos/
  ```
- Subfolders displayed recursively (collapsible tree on left sidebar)
- Breadcrumb trail at top (e.g. `Vault > images > family`)
- Folder cards show: folder name + file count badge

### File Grid
- **Images**: thumbnail grid (small icons), click to open full view
- **PDF**: file icon + filename, click to open inline PDF.js viewer
- **Audio**: music note icon + filename, click to open inline player; checkbox to add to playlist
- **Video**: video icon + filename, click to open inline HTML5 player; checkbox to add to playlist
- **Documents**: document icon + filename, click to download
- **Others**: generic icon + filename, click to download

### Sort Controls
- Sort bar at top of file grid
- Options: Name (A→Z, Z→A), Date Added, File Size
- Selected sort persists in localStorage

### File Detail Panel
Opens as a right-side panel (or modal on mobile) when clicking a file:
- **Filename** (display only — rename via Amber)
- **File type / size / date added**
- **Preview** (thumbnail for images, mini-player for audio/video)
- **Description** — editable inline text field with a save button (updates ChromaDB directly without Amber; also logs change to short-term memory)
- **All ChromaDB metadata** displayed as read-only tags
- **"Talk to Amber about this file"** button — opens Chat tab with file context pre-loaded

### Automatic UI Refresh
- Frontend polls `/api/files/changes` every 10 seconds
- When Amber renames/modifies a file via chat, the vault tab reflects the change within 10s without manual refresh

---

## Tab 2 — Chat (Amber)

### Layout
- Full-height chat panel with message history
- Input bar at bottom
- Current file context banner at top when launched from a file (e.g. "📎 Talking about: spouse_portrait.jpg")

### Amber Capabilities via Chat
Amber understands and can perform (non-exhaustive):
- `"Rename this to spouse_birthday.jpg"` → renames file on disk + updates ChromaDB path
- `"Update the description to: portrait of spouse at her birthday dinner"` → updates ChromaDB, logs to short-term memory
- `"Create a playlist of all jazz tracks in the audio folder"` → creates named playlist, saves to permanent memory
- `"What files do I have in the images folder?"` → Amber lists and can display inline
- `"Share the vacation folder with spouse"` → Amber prompts confirm, generates share code
- `"What's the current vault URL?"` → Amber reports the active Cloudflare Quick Tunnel URL
- `"Unlock the vault"` → clears login lockout
- Amber can display images inline in the chat panel

### Memory Protocol for Chat
| Event | Memory Destination |
|-------|-------------------|
| File description changed | ChromaDB permanent memory |
| Rename or file op | ChromaDB short-term memory (exact change + timestamp) |
| Any fact worth remembering about a file | ChromaDB long-term memory |
| Playlist created/modified | ChromaDB permanent memory |

### Chat History
- Follows existing Project Ambient memory protocol
- Chat history is not stored in `vault_web.db` — managed by Amber's existing session/memory system

---

## Tab 3 — Music (Playlists)

### Playlist Features
- Lists all saved playlists (name, track count, duration)
- Click a playlist → full track list with inline player controls
- Play, pause, skip, shuffle, repeat
- Amber can create playlists from chat: `"Make a playlist of all tracks in audio/jazz"`
- Playlists saved to:
  1. `vault_web.db` (for fast UI access)
  2. ChromaDB permanent memory (so Amber remembers them across sessions)
- Playlists can include both audio and video files

---

## File Operations — All via Amber

No operation buttons in the Vault UI (no rename button, no delete button, no move button). All file operations are issued through the Amber chat panel. The Vault UI updates automatically.

**Supported operations (Phase 1):**
- Rename (renames on disk + updates ChromaDB metadata path)
- Update description (also available via inline edit in file panel)
- If rename target already exists: Amber asks *"A file with that name already exists. Overwrite, keep both, or cancel?"*

**Deferred to Phase 2:**
- Upload
- Delete
- Move between folders

---

## Sharing

- Amber generates a 6-digit share code for a file or folder (including all subfolders)
- Share code stored in `vault_web.db` with: path, code, created_at, created_for ("spouse")
- No automatic expiry — Chieh revokes via Amber: `"Revoke spouse's access to the vacation folder"`
- Settings page `/settings/shares` shows all active shares with revoke button
- Recipient (spouse) enters share code at `/share` → session with access scoped to that path only

---

## Cloudflare Quick Tunnel

### Auto-start on Boot
- systemd service: `vault-web.service` — starts FastAPI on `localhost:8080`
- systemd service: `vault-tunnel.service` — runs `cloudflared tunnel --url http://localhost:8080`
- Both start automatically on boot

### URL Discovery
- `cloudflared` prints the assigned URL to its log at startup
- Amber has a skill to read that log and report the current URL
- Chieh asks: `"Amber, what's the vault URL?"` → Amber reads the log and replies

---

## Mobile Responsiveness

- Tailwind CSS responsive breakpoints throughout
- On mobile (`< 768px`):
  - Sidebar collapses to hamburger menu
  - File grid switches to 2-column layout (vs 4-column on desktop)
  - File detail panel opens as full-screen modal
  - Chat panel is full-screen
  - Tab bar moves to bottom of screen (native app feel)
- Touch-friendly tap targets (min 44×44px)

---

## Settings Pages

### `/settings/devices` — Trusted Devices
- List: browser label, OS, first seen, last used
- Revoke button per device

### `/settings/shares` — Active Share Links
- List: path shared, created for, created at
- Revoke button per share

---

## Security Notes

- All routes require valid session cookie (except `/login` and `/share`)
- OTP codes are single-use and deleted after successful validation
- Session tokens are cryptographically random (32-byte hex)
- Vault files are served through FastAPI (not as static files) so path traversal is blocked
- Cloudflare Quick Tunnel provides HTTPS automatically

---

## Deferred (Phase 2)

- Multi-user identity (spouse gets her own Amber memory, separate from Chieh's)
- File upload from browser
- Delete files from browser
- Move files between folders
- Persistent domain name (when Chieh buys a domain)
- Notifications to Discord when spouse opens a shared link

---

## Open Questions / Assumptions

- Amber chat proxy: POSTs to Amber ADK API at `http://localhost:8000/run` with `user_id=chieh`
- Chieh's Discord channel ID for OTP: loaded from `config.py / .env`
- vault_web.db location: `/home/chieh/vessence/vault_web/vault_web.db`
- FastAPI port: 8080
