# Job: Response Speed Optimization — Reduce Time to First Token

Status: complete
Completed: 2026-03-24 00:24 UTC
Notes: Fixed async context_builder caching (personal_facts + task_state now cached 5min). Bumped all cache TTLs to 300s. Pre-warm, status streaming, memory daemon, lighter casual context all confirmed already working.
Priority: 1
Model: sonnet
Created: 2026-03-23

## Objective
Reduce the time between user sending a message on web/Android and seeing the first response text. Current: 7-18 seconds. Target: under 3 seconds for simple messages.

## Changes

### 1. Cache context builder output (5-min TTL)
User profile, personality, essence tools description don't change between messages. Cache them.
- In `jane/context_builder.py`, cache the static sections (base prompt, user background, essence personality, tool descriptions) with a 5-minute TTL
- Only re-query ChromaDB memory on each request (the part that actually changes)
- Cache key: user_id or session_id
- Invalidate on: essence load/unload, profile update

**Expected savings: 2-4 seconds per message**

### 2. Pre-warm Claude session on page/app load
When user opens web Jane or Android app, silently start the Claude CLI session before they type anything.
- Web: fire pre-warm on page load via `/api/jane/prewarm` (already exists — verify it's being called)
- Android: fire pre-warm in `ChatViewModel.init` (already calls `initSession` — verify it creates the CLI process)
- Ensure the persistent Claude manager keeps the process alive between messages

**Expected savings: 1-2 seconds on first message**

### 3. Stream status updates immediately
Don't wait for the brain to produce text before showing activity.
- As soon as the request hits the server, emit a status event: "Building context..."
- After context build: "Querying memory..."
- After memory: "Thinking..."
- These appear as live status text in the chat UI (already have the broadcast infrastructure)
- User sees activity within 200ms of sending

**Expected savings: 0 seconds actual, but eliminates perceived dead time**

### 4. Ensure memory daemon is always running
The fast path in context_builder queries `http://127.0.0.1:8083/query` (memory daemon). If it's down, falls back to direct ChromaDB (slower).
- Check if memory daemon has a systemd service
- If not, create one so it's always running
- Add health check in jane-web startup to verify daemon is reachable
- If daemon is down, log a warning but don't crash

**Expected savings: 1-2 seconds when daemon is up vs down**

### 5. Lighter context for casual messages
The classifier already produces profiles (casual_followup, factual_personal, project_work, file_lookup). Use them more aggressively.
- `casual_followup`: skip task state, research brief, file context, essence tools. Just user profile + recent memory.
- `factual_personal`: skip task state, research brief, file context. Just user profile + memory.
- Only `project_work` and `file_lookup` get the full context.
- This reduces the system prompt size → fewer input tokens → faster brain response

**Expected savings: 1-3 seconds for casual messages (less context = faster inference)**

## Implementation Notes
- All changes are server-side — no Android/web code changes needed (except verifying pre-warm)
- Test each optimization independently to measure actual savings
- Add timing logs to measure before/after: context_build_ms, memory_query_ms, brain_first_token_ms
- Don't break the full-context path for project_work — that still needs everything

## Files Involved
- `jane/context_builder.py` — caching, lighter profiles
- `jane_web/jane_proxy.py` — stream status updates, pre-warm verification
- `jane_web/main.py` — memory daemon health check on startup
- Memory daemon service file (check if exists, create if not)

## Verification
After implementing, time the full round-trip for these test messages:
1. "hey" → should respond in <1s (once intent classifier is also built)
2. "what's in my job queue?" → should show first text in <3s
3. "refactor the auth system" → should show "Thinking..." in <1s, first real text in <5s
