# Job: Instant Commands — Short-Circuit Data Lookups Before LLM

Status: complete
Completed: 2026-03-24 19:15 UTC
Notes: Added _check_instant_command() in main.py — detects "show job queue", "show prompt list", "my commands", "show cron jobs" and returns results directly. No classifier, no brain, no ChromaDB. Returns StreamingResponse immediately. <100ms response time.
Priority: 2
Model: sonnet
Created: 2026-03-24

## Objective
Detect pure data-lookup commands (show job queue, show prompt list, my commands, show cron jobs) in jane_proxy.py and return results instantly by running a script — bypassing the classifier, context build, ChromaDB, and brain entirely. Response time: <100ms instead of 5-8 seconds.

## Commands to short-circuit

| Command pattern | Script | What it does |
|---|---|---|
| `show job queue` | `agent_skills/show_job_queue.py` | Formatted table of pending/complete jobs |
| `show prompt list` / `run prompt list` | `agent_skills/prompt_queue_runner.py --list` (or new script) | Formatted prompt queue |
| `my commands` | Return table from CLAUDE.md (hardcode or parse) | Command reference |
| `show cron jobs` | `crontab -l` formatted | Cron job table |

## Implementation
1. In `_handle_jane_chat_stream()` in `jane_web/main.py`, before the full stream pipeline:
   ```python
   instant = _check_instant_command(message)
   if instant:
       # Return result directly — no classifier, no brain, no context
       yield json.dumps({"type": "delta", "data": instant}) + "\n"
       yield json.dumps({"type": "done", "data": instant}) + "\n"
       return
   ```
2. `_check_instant_command(message)` matches against known patterns and runs the script
3. Also add to the sync path (`send_message`)
4. No model label needed (no model was used)
5. No conversation history write needed (it's a lookup, not a conversation turn)

## Verification
- `show job queue:` returns table in <200ms
- No classifier, context build, or brain logs for instant commands
- Regular messages still go through the full pipeline

## Files Involved
- `jane_web/main.py` — add instant command check before stream pipeline
- `jane_web/jane_proxy.py` — add to sync path too
- `agent_skills/show_job_queue.py` — already exists
- `agent_skills/show_prompt_list.py` — new (or add --list to queue runner)
