# Job: Cron Load Guard — All Cron Jobs Check CPU Before Running

Status: complete
Completed: 2026-03-23
Notes: Built wait_until_safe() in system_load.py (waits up to N minutes, checking every 60s). Wired into all 10 cron scripts: nightly_audit, janitor_memory, janitor_system, ambient_heartbeat, ambient_task_research, audit_auto_fixer, essence_scheduler, prompt_queue_runner, run_briefing, regenerate_jane_context. Also updated prompt_queue_runner to use wait_until_safe instead of should_defer (wait+retry instead of skip).
Priority: 1
Created: 2026-03-23

## Objective
Every cron job should call `should_defer()` before doing any real work. If the system is too busy, wait and retry instead of piling on.

## Design

### Shared Wrapper Function
Add to `agent_skills/system_load.py`:
```python
def wait_until_safe(max_wait_minutes=30, check_interval_seconds=60):
    """Block until system load is acceptable, or give up after max_wait_minutes."""
    for _ in range(max_wait_minutes * 60 // check_interval_seconds):
        if not should_defer():
            return True  # safe to proceed
        time.sleep(check_interval_seconds)
    return False  # still busy after max wait
```

### Integration
Add this check to the top of every cron script's `main()`:
```python
from agent_skills.system_load import wait_until_safe
if not wait_until_safe(max_wait_minutes=15):
    logger.info("System still busy after 15 min — skipping this run.")
    return
```

### Cron Scripts to Update
- `agent_skills/nightly_audit.py`
- `agent_skills/janitor_memory.py`
- `agent_skills/janitor_system.py`
- `agent_skills/ambient_heartbeat.py`
- `agent_skills/ambient_task_research.py`
- `agent_skills/audit_auto_fixer.py`
- `agent_skills/prompt_queue_runner.py` (already has should_defer, add wait_until_safe)
- `agent_skills/essence_scheduler.py`
- `startup_code/regenerate_jane_context.py`
- `startup_code/usb_sync.py`
- Any essence cron scripts (e.g., `daily_briefing/functions/run_briefing.py`)

### Behavior
- Cron triggers at scheduled time
- Script calls `wait_until_safe(max_wait_minutes=15)`
- If CPU <80% and memory >1GB → runs immediately
- If busy → waits 60 seconds, checks again
- Retries for up to 15 minutes
- If still busy after 15 min → skips this run (next cron cycle will try again)
- Logs every wait: "System busy (CPU 85%), waiting 60s..."

## Files Involved
- Update: `agent_skills/system_load.py` — add `wait_until_safe()`
- Update: all cron scripts listed above — add load check at entry

## Notes
- The wait time should be configurable per script (heavy jobs like janitor can wait longer)
- Don't wait indefinitely — always have a max_wait to prevent cron job stacking
- Log when a job is skipped due to load so we can see patterns in the audit logs
