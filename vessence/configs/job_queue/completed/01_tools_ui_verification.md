# Job: Tools UI Verification — Ensure All Tools Show Up Properly

Status: complete
Completed: 2026-03-23
Notes: All 4 tools load from ~/ambient/tools/ with type=tool. Tax Accountant loads from ~/ambient/essences/ with type=essence. Type filtering works. Crash fixes also applied: Claude timeout default, systemd graceful shutdown, persistent worker cleanup, import fix. Service restarted clean at 99.9MB.
Priority: 1
Created: 2026-03-23

## Objective
After the essences→tools folder rename, verify that all 4 tools (Daily Briefing, Life Librarian, Music Playlist, Work Log) load correctly and display properly on both web and Android. Fix any broken paths, missing manifests, or UI rendering issues.

## Checklist

### 1. Verify tools load from the correct directory
- `TOOLS_DIR` in config.py should point to `~/ambient/tools/`
- `ESSENCES_DIR` should point to `~/ambient/essences/` (true AI essences only)
- `essence_loader.py` should scan both directories
- All 4 tools should appear in `GET /api/essences` response with `type: "tool"`

### 2. Verify each tool's manifest.json
- `~/ambient/tools/daily_briefing/manifest.json` — has `type: "tool"`, `has_brain: false`
- `~/ambient/tools/life_librarian/manifest.json` — same
- `~/ambient/tools/music_playlist/manifest.json` — same
- `~/ambient/tools/work_log/manifest.json` — same

### 3. Web UI verification
- Open jane.html essence picker — tools should appear under "Tools" section
- Each tool should be clickable and functional
- Daily Briefing page loads at /briefing
- Life Librarian (vault) loads properly
- Music Playlist loads
- Work Log loads and shows at bottom
- Jane stays at top

### 4. Android verification
- HomeScreen.kt should show tools in a "Tools" section
- Tools should be tappable and navigate correctly
- If HomeScreen doesn't split into Tools/Essences sections yet, implement it

### 5. API verification
- `GET /api/essences` returns all tools + essences
- `GET /api/essences?type=tool` returns only 4 tools
- `GET /api/essences?type=essence` returns only tax_accountant_2025

### 6. Fix any broken references
- Check essence_scheduler.py reads from correct dir
- Check cron jobs reference correct paths
- Check context_builder.py scans both dirs for tool descriptions
- Restart jane-web.service after fixes

## Files Involved
- `jane/config.py` — TOOLS_DIR, ESSENCES_DIR
- `agent_skills/essence_loader.py` — must scan both dirs
- `jane_web/main.py` — essence/tool routes
- `vault_web/templates/jane.html` — essence picker UI
- `android/.../ui/home/HomeScreen.kt` — two-section layout
- `agent_skills/essence_scheduler.py` — cron scheduling for tools
- All 4 tool manifest.json files

## Notes
- The symlink `essences/ → tools/` may or may not still be in place — check and decide: keep symlink for backward compat or update all references to use TOOLS_DIR directly
- Jane is neither a tool nor an essence — always shows at top
- Work Log always shows at bottom
- After all fixes, restart jane-web.service and verify via curl
