# Job: Prompt Queue Runner — Use Persistent Session Instead of Subprocess

Status: complete
Completed: 2026-03-24 14:15 UTC
Notes: Rewrote run_prompt() to call internal web API (http://localhost:8081/api/jane/chat/stream) instead of spawning subprocess. Added localhost auth bypass in _handle_jane_chat_stream() and require_auth(). Queue uses dedicated session_id "prompt_queue_session" for context continuity. Tested: internal API accepts requests, classifier routes correctly, streaming response works. Lock file already existed. Removed automation_runner import from queue path.
Priority: 1
Model: opus
Created: 2026-03-24

## Objective
Rewrite the prompt queue runner to inject prompts into the already-running persistent Claude session via the internal web API, instead of spawning a new Claude CLI subprocess per prompt. This eliminates cold start cost (~30s), timeout issues, and context loss.

## Current Architecture (broken)
```
Cron (every 5 min) → prompt_queue_runner.py
  → automation_runner.py → brain_adapters.py
  → subprocess.run(["claude", "-p", prompt], timeout=180)
  → cold start: loads CLAUDE.md, hooks, context from scratch
  → frequently times out at 180s on complex prompts
  → no conversation history between prompts
```

## New Architecture
```
Cron (every 5 min) → prompt_queue_runner.py
  → picks next pending prompt
  → POST http://localhost:8081/api/jane/chat (internal API)
  → uses existing persistent Claude session (--resume)
  → full context, memory, conversation history available
  → no timeout (persistent session handles its own lifecycle)
  → waits for response, logs result, marks complete
```

## Steps
1. Rewrite `prompt_queue_runner.py` to:
   - Read next pending prompt from queue
   - POST to `http://localhost:8081/api/jane/chat` with `{"message": prompt_text, "session_id": "prompt_queue", "platform": "queue"}`
   - Use a dedicated session ID (`prompt_queue`) so queue prompts share context with each other but don't pollute user sessions
   - Read the streaming response (SSE) and collect the full response text
   - Log the result and mark the prompt as complete/failed
   - Add a lock file to prevent concurrent runs (cron fires every 5 min)
2. Add auth bypass for internal requests (localhost only) or use a service token
3. Remove `automation_runner.py` and `brain_adapters.py` from the queue path (they become dead code for queue use)
4. Handle edge cases:
   - Jane web is down → skip this cycle, retry next cron
   - Response is empty → mark as failed with reason
   - Lock file is stale (>2 hours) → break lock and proceed
5. Test with a simple prompt ("what time is it") and a complex one ("audit the codebase")

## Verification
- Queue runner calls internal API instead of spawning subprocess
- No more 180s timeout errors in logs
- Prompts complete successfully with full context
- Lock file prevents double-runs
- Queue runner gracefully handles jane-web being down

## Files Involved
- `agent_skills/prompt_queue_runner.py` — main rewrite
- `jane_web/main.py` — may need internal auth bypass for localhost
- `jane/brain_adapters.py` — no longer used by queue (keep for fallback)
- `jane/automation_runner.py` — no longer used by queue

## Notes
- The dedicated `prompt_queue` session ID means queue prompts build context over time — each prompt benefits from the previous ones
- The intent classifier still runs, so simple queue prompts get routed to haiku (cheap) and complex ones to opus
- If persistent session rotates (70% context), the summary handoff preserves context
- This also means queue prompts can reference previous queue results naturally ("continue the audit from earlier")
