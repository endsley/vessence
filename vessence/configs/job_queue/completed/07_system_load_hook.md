# Job: Claude Code System Load Hook — Auto-Check Before Spawning Work

Status: complete
Completed: 2026-03-23
Notes: Added --oneline mode with 10s file cache to system_load.py (0.07s cached calls). Created check_system_load.sh wrapper. Added PreToolUse hook for Bash|Agent in ~/.claude/settings.json. Hook fires before every Bash/Agent call showing CPU/memory/parallelism recommendation.
Priority: 1
Created: 2026-03-23

## Objective
Add a Claude Code hook that runs `system_load.py` before every Bash or Agent tool call. The hook output is injected into Jane's context, so she can't ignore high load — she'll see "CPU: 85%, defer: True" and adjust accordingly.

## Design

### Hook Script
Create a lightweight shell script that runs `system_load.py` and outputs a one-line summary:
```bash
#!/bin/bash
/home/chieh/google-adk-env/adk-venv/bin/python /home/chieh/ambient/vessence/agent_skills/system_load.py --oneline 2>/dev/null
```

### system_load.py --oneline Mode
Add a `--oneline` flag that outputs a compact single line:
```
[LOAD] CPU: 45% | Mem: 16.5GB free | Parallel: 2 | Defer: No | Period: day
```
Or if overloaded:
```
[LOAD WARNING] CPU: 82% | Mem: 3.1GB free | Parallel: 1 | Defer: YES | Period: day — reduce concurrency
```

### Claude Code Hook Configuration
Add to `~/.claude/settings.json` or `~/.claude/projects/-home-chieh/settings.json`:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Agent",
        "hook": "/home/chieh/ambient/vessence/startup_code/check_system_load.sh",
        "timeout": 3000
      }
    ]
  }
}
```

### Behavior
- Runs before every Bash command or Agent spawn (~1s overhead via psutil)
- Jane sees the load in her context and adjusts:
  - `Defer: No` → proceed normally
  - `Defer: YES` → Jane should run sequentially, not parallel
  - `Parallel: 1` → only one subprocess at a time
- The hook does NOT block execution — it's informational. Jane makes the decision.

## Files Involved
- Update: `agent_skills/system_load.py` — add `--oneline` flag
- New: `startup_code/check_system_load.sh` — hook wrapper script
- Update: `~/.claude/settings.json` or project settings — add PreToolUse hook

## Notes
- Hook must be fast (<2s) — psutil CPU check takes ~1s (it samples over an interval)
- Consider caching: if last check was <10s ago, return cached result (avoid checking CPU on every tool call)
- Only fires for Bash and Agent tools — Read, Write, Grep, etc. don't need load checks
- This is a local-only setting — doesn't affect the Docker/public package
