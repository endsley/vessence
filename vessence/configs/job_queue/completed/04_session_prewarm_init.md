# Job: Session Pre-Warm — Auto-Initialize Jane's Brain on Session Start

Status: complete
Priority: 1
Created: 2026-03-22

## Objective
When a user opens Jane (web or Android), Jane should immediately initialize her Claude CLI session without waiting for the user's first message. The user sees a friendly wake-up message while initialization happens in the background.

## Context
Currently, the Claude CLI session (`persistent_claude.py`) doesn't start until the user sends their first message. The `prewarm_session()` in `jane_proxy.py` only preloads ChromaDB memory — it does NOT start the Claude CLI process. This means the first user message has significant extra latency (spawning CLI + loading CLAUDE.md + hooks + context build).

Key code:
- `jane/persistent_claude.py` — `ClaudePersistentManager`, `is_fresh()` check on first turn
- `jane_web/jane_proxy.py` — `prewarm_session()` (memory only), `_execute_brain_stream()` (where Claude CLI actually starts)
- `jane_web/main.py` — session bootstrap, already calls `prewarm_session()` on page load
- `vault_web/templates/jane.html` — frontend `init()` function

## Design

### User Experience
1. User opens Jane web (or Android app)
2. Immediately see Jane's message: **"Hey, give me a sec to wake my brain up with a cup of coffee (initializing my memory)"**
3. In the background, Jane's Claude CLI session starts with the system prompt + CLAUDE.md + hooks
4. Once initialization completes, the wake-up message updates or a new message appears: **"All set! What's on your mind?"** (or similar)
5. User's first actual message goes to an already-warm session — fast response

### Implementation

#### Backend: `/api/jane/init-session` endpoint
- Triggers the full Claude CLI session init (not just memory prewarm)
- Sends an initialization prompt like: "You are starting a new session. Read your configuration files and prepare for conversation. Respond with a single short greeting."
- Streams status events back to the frontend (so the user sees tool use like "Reading CLAUDE.md...")
- Returns the greeting response

#### Frontend (jane.html):
- In `init()`, after session ID is established:
  1. Push a Jane message: `{ role: 'jane', text: '', status: 'Waking up...', statusLog: [] }`
  2. Call `/api/jane/init-session` via fetch stream
  3. Feed status/delta events into the wake-up message
  4. Once done, the message shows the greeting and status collapses (using the new collapsible behavior)
- Skip this if the session already has history (returning user with active session)

#### Android:
- Same flow: on app launch or session start, call the init endpoint
- Show the wake-up message in the chat view
- Once ready, show the greeting

#### Persistent session awareness:
- If `session.is_fresh()` → do the full init
- If session already has a `claude_session_id` (resumed) → skip, already warm
- The init turn should count as turn 0 (setup), not turn 1 (user conversation)

## Files Involved
- `jane/persistent_claude.py` — needs an init/warmup method
- `jane_web/jane_proxy.py` — new init endpoint logic, extend prewarm
- `jane_web/main.py` — register the new endpoint
- `vault_web/templates/jane.html` — frontend init flow
- Android app chat activity — same init flow

## Notes
- The init prompt should be lightweight — just enough to trigger CLAUDE.md loading and hook execution
- Don't send the full system prompt twice — the init turn IS the first turn, subsequent messages should use `--resume`
- The wake-up message should use the same collapsible status log we just built
- Consider caching: if the user refreshes the page within a few minutes, don't re-init — reuse the existing warm session
- No waiting for user prompt — init fires immediately on session creation
