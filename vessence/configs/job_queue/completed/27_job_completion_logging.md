# Job: Work Log Policy — Only Completions + Crash Alerts

Status: completed
Priority: 2
Model: sonnet
Created: 2026-03-24

## Objective
Define and enforce what gets posted to the Work Log. Remove chat logging, briefing fetches, and notification spam. Only log meaningful events.

## What posts to Work Log (final policy)

| Event | Category | Already done? |
|---|---|---|
| Prompt queue completion | prompt_completed | Yes (keep) |
| Job queue completion | job_completed | No — implement |
| Crash/outage alerts | crash_alert | No — implement |
| Android release builds | release | Yes (keep) |

## Changes already made (this session)
- Removed: `_log_chat_to_work_log()` calls from jane_proxy.py (chat messages)
- Removed: briefing fetch log from main.py
- Removed: notification redirect in prompt_queue_runner send_discord()
- Kept: prompt completion logging (line 405)
- Kept: release/upload logging (lines 729, 1349)

## Still needed

### 1. Job queue completion logging
- Add a CLAUDE.md rule or helper: when marking a job complete, call `log_activity()`
- Format: "Job #N completed: [title]. [notes]"
- Category: "job_completed"

### 2. Crash alert logging
- In standing_brain.py: when a brain dies or hits MAX_FAILURES, log to work log
- In jane_proxy.py: when brain_execute fails with an error, log to work log
- In main.py: when startup fails or service crashes, log to work log
- Format: "CRASH: [component] — [error message]"
- Category: "crash_alert"

## Verification
- Chat messages do NOT appear in work log
- Briefing fetches do NOT appear in work log
- Job completions DO appear
- Crash/restart events DO appear
- Work log page shows clean, meaningful entries only

## Files Involved
- `jane_web/jane_proxy.py` — chat logging removed (done)
- `jane_web/main.py` — briefing log removed (done)
- `agent_skills/prompt_queue_runner.py` — notification redirect removed (done)
- `jane/standing_brain.py` — add crash alert logging
- `CLAUDE.md` — add job completion logging rule
