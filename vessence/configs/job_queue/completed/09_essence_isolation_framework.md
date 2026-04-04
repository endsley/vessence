# Job: Essence Isolation Framework — Zero-Pollution Essence Architecture

Status: complete
Priority: 1
Created: 2026-03-22

## Objective
Build the framework so that any new essence is 100% self-contained within its own folder. Installing an essence = dropping a folder into `essences/`. Uninstalling = deleting the folder. Zero changes to Vessence core code.

## Problem
Currently, Daily Briefing touches 4 Vessence core files (main.py, briefing.html, jane.html, crontab). This is fine for built-in essences we ship with Vessence, but unacceptable for user-created or marketplace essences. A downloaded essence must work without modifying any Vessence source.

## Design Principle
An essence folder is a complete, portable package. Everything lives inside:
```
essences/my_essence/
├── manifest.json          # Declaration: name, routes, tools, schedule, UI, permissions
├── personality.md          # System prompt / identity
├── functions/
│   ├── custom_tools.py     # Callable functions (Jane can invoke these)
│   └── *.py                # Any additional logic
├── ui/
│   ├── layout.json         # UI type declaration (card_grid, form, chat, custom)
│   └── template.html       # Custom HTML template (rendered inside Vessence shell)
├── knowledge/              # Pre-filled data, reference docs
├── essence_data/           # Runtime data (articles, indexes, etc.)
├── user_data/              # User-specific config (topics.json, preferences)
├── working_files/          # Temp/cache files
├── docs/
│   ├── README.md           # Usage manual
│   └── CHANGELOG.md        # Version history
└── cron/                   # Scheduled task declarations
    └── jobs.json           # [{"schedule": "0 */8 * * *", "script": "functions/run_briefing.py"}]
```

## Vessence Platform Responsibilities

### 1. Dynamic Route Mounting
On startup (and when essences change), Vessence reads each essence's `manifest.json` and auto-mounts:
- **Page route**: `/essence/<name>` → renders the essence's `ui/template.html` inside the Vessence shell (header, nav, auth)
- **API routes**: `/api/essence/<name>/<tool_name>` → calls the corresponding function in `functions/custom_tools.py`
- No hardcoded routes in `main.py` for individual essences

### 2. UI Shell Rendering
Vessence provides a standard shell (header, sidebar, auth). The essence provides the content:
- **Option A (HTML template)**: Essence provides `ui/template.html` which gets rendered inside an iframe or injected into the shell
- **Option B (Layout JSON)**: Essence declares a layout type (`card_grid`, `list`, `form`, `chat`) and Vessence renders it with standard components
- **Option C (Full custom)**: Essence provides a complete SPA that Vessence serves at its route

For Android: Vessence renders essence UIs in a WebView pointed at `/essence/<name>`, or uses native components for declared layout types.

### 3. Cron/Schedule Manager
Instead of manual crontab entries, Vessence reads `cron/jobs.json` from each loaded essence:
```json
[
  {
    "schedule": "0 */8 * * *",
    "script": "functions/run_briefing.py",
    "idle_only": true,
    "description": "Fetch news articles"
  }
]
```
A single Vessence cron job (`essence_scheduler.py`) runs every minute, checks all loaded essences' schedules, and executes due jobs.

### 4. Tool Registry
On essence load, Vessence scans `functions/custom_tools.py` for callable functions and registers them:
- Jane knows about them (injected into context)
- API endpoints are auto-created
- Each function's docstring becomes the tool description

### 5. Navigation Auto-Discovery
The essence picker dropdown and home screen read from the loaded essences list. No hardcoded navigation links. Essence ordering rule still applies (Jane first, Work Log last, rest alphabetical).

## Implementation Steps

### Step 1: `essence_scheduler.py`
New agent skill that replaces per-essence crontab entries:
- Reads `cron/jobs.json` from each loaded essence
- Checks if any job is due (based on schedule + last run time)
- Checks idle gate if `idle_only: true`
- Executes the script via subprocess
- Logs results

Add a single crontab entry: `* * * * * essence_scheduler.py`

### Step 2: Dynamic API mounting in `main.py`
- On startup, scan loaded essences
- For each essence with `functions/custom_tools.py`, create API routes
- Route pattern: `POST /api/essence/{name}/{function_name}`
- Dispatch: import the function, call it with the request body as kwargs
- Auth required on all essence API routes

### Step 3: Dynamic page routing
- Route: `GET /essence/{name}`
- Renders the essence's `ui/template.html` inside the Vessence shell template
- Or returns a standard layout if `ui/layout.json` is used

### Step 4: Navigation auto-discovery
- Remove hardcoded essence links from `jane.html`
- Essence picker reads from `/api/essences` (already does this)
- Route resolution uses essence name, not hardcoded paths

### Step 5: Migrate Daily Briefing
- Move the 7 briefing API endpoints from `main.py` into `custom_tools.py` (they mostly already call custom_tools functions)
- Move `briefing.html` into `essences/daily_briefing/ui/template.html`
- Add `cron/jobs.json` to the essence folder
- Remove the manual crontab entry
- Remove hardcoded briefing routes from `main.py`

## What This Enables
- **Download an essence** → drop folder into `essences/` → restart → it works
- **Delete an essence** → remove folder → restart → it's gone
- **No Vessence core changes** for any new essence
- **Marketplace ready** — essences are portable zip files

## Files Involved
- New: `agent_skills/essence_scheduler.py` — cron manager for all essences
- Update: `jane_web/main.py` — dynamic route mounting, remove hardcoded briefing routes
- Update: `agent_skills/essence_loader.py` — load tool registry, cron schedules
- Update: `vault_web/templates/jane.html` — dynamic navigation
- Migrate: `vault_web/templates/briefing.html` → `essences/daily_briefing/ui/template.html`
- New: `essences/daily_briefing/cron/jobs.json`

## Non-Goals (for this job)
- Android native UI for arbitrary essences (WebView is fine for now)
- Essence sandboxing (trust model is explicit — user accepts permissions)
- Marketplace upload/download flow (separate job)

## Notes
- Built-in essences (Daily Briefing, Work Log, Music, Life Librarian) can stay hardcoded for now, but should eventually be migrated to this framework
- The framework must handle essence load/unload at runtime without server restart
- Hot-reload: when an essence folder changes, Vessence detects it and re-mounts routes
