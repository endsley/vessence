# Job: Detect CLI errors from stderr and enable runtime provider switching
Status: completed
Priority: 1
Created: 2026-03-27

## Objective
When the active LLM provider hits a rate limit, billing error, or other API failure, surface a clear error message to the user AND offer a one-click option to switch to a different provider — killing the current CLI and starting the new one without restarting the container.

## Context
The standing brain (`jane/standing_brain.py`) spawns the CLI with `stderr=asyncio.subprocess.PIPE` (line 198) but never reads stderr. When a provider hits rate limits:
- The CLI prints the error to stderr
- stdout produces nothing
- The brain waits, times out, and the user sees "(no response)" or the UI hangs

All three providers (Claude, Gemini, OpenAI) have the same problem.

## Design

### Part 1: Stderr monitoring
- In `standing_brain.py`, start a background task that continuously reads stderr from the CLI process
- Parse stderr for known error patterns:
  - Claude: `rate_limit`, `overloaded`, `billing`, `insufficient_quota`, `credit`
  - Gemini: `quota`, `rate limit`, `429`, `billing`, `RESOURCE_EXHAUSTED`
  - OpenAI: `rate_limit`, `insufficient_quota`, `billing`, `429`
- When a rate limit/billing error is detected:
  - Log it clearly
  - Emit a new SSE event type `"provider_error"` with the error details
  - Include available alternative providers in the event payload

### Part 2: Frontend provider switch UI
- In `vault_web/templates/jane.html`, handle the `"provider_error"` event type in `applyStreamEvent()`
- Display a clear error message: "Claude hit its rate limit. You can switch to another provider:"
- Show buttons for available alternatives (e.g., "Switch to Gemini", "Switch to OpenAI")
- Each button calls a new API endpoint

### Part 3: Runtime provider switch API
- New endpoint: `POST /api/jane/switch-provider` with body `{"provider": "gemini"}`
- Backend handler in `jane_web/main.py`:
  1. Validate the requested provider
  2. Call `StandingBrainManager.switch_provider(new_provider)`:
     a. Kill the current CLI process
     b. Check if the new CLI is installed (e.g., `which gemini` / `which claude`)
     c. If not installed, run `install_brain.sh` with the new brain name
     d. Update `JANE_BRAIN` env var in the running process
     e. Spawn the new CLI process
     f. Update the .env file so the switch persists across restarts
  3. Return success/failure to the frontend
- Frontend updates the model indicator and resumes normal chat

### Part 4: Multi-CLI pre-installation (optional optimization)
- Modify `install_brain.sh` to accept an `--also` flag that pre-installs a secondary CLI
- Or: install all three CLIs at build time (increases image size but enables instant switching)
- For MVP: install on-demand when switching (slower first switch, but no image bloat)

## Pre-conditions
- Standing brain process management works (already does)
- Node.js is installed in the Docker container (already is, from install_brain.sh)

## Steps
1. Add stderr reader background task to `standing_brain.py`
2. Define error pattern matching for all three providers
3. Add `"provider_error"` event emission in `jane_proxy.py`
4. Add `POST /api/jane/switch-provider` endpoint in `jane_web/main.py`
5. Add `switch_provider()` method to `StandingBrainManager`
6. Update `applyStreamEvent()` in `jane.html` to handle `"provider_error"` with switch buttons
7. Update .env on switch so it persists
8. Test: simulate a rate limit error and verify the switch flow

## Verification
1. Trigger a rate limit (or mock one by writing a known error string to a test stderr pipe)
2. Confirm the user sees a clear error message with switch buttons
3. Click "Switch to Gemini" — confirm Claude CLI is killed, Gemini CLI starts, next message goes through Gemini
4. Confirm .env is updated with the new provider
5. Restart the container — confirm it comes up with the switched provider

## Files Involved
- `jane/standing_brain.py` — stderr reader, switch_provider(), kill/spawn
- `jane_web/main.py` — new /api/jane/switch-provider endpoint
- `jane_web/jane_proxy.py` — provider_error event emission
- `vault_web/templates/jane.html` — provider_error UI with switch buttons
- `docker/jane/install_brain.sh` — may need on-demand install support

## Notes
- The switch should be fast — kill old CLI, spawn new one. No container restart.
- If the new provider also fails (e.g., no API key configured), show a clear error rather than silently failing.
- The model indicator in the UI header should update to reflect the new provider.
- This also partially addresses the "(no response)" investigation (job #02) since rate limit errors were a major cause.
- **OAuth after switch**: When a newly installed CLI needs authentication, the switch API should return `{"ok": true, "needs_auth": true, "auth_url": "https://...", "provider": "gemini"}`. The frontend shows the auth URL as a clickable link the user can open to sign in. Reuse the same OAuth proxy flow from onboarding (`POST /api/cli-login`). Poll for completion, then resume chat on the new provider.
