# Job: Adaptive Parallelization — Load-Aware Task Throttling

Status: complete
Completed: 2026-03-23
Notes: Created system_load.py with psutil-based CPU/memory monitoring + time-of-day awareness (night=aggressive, day=conservative). Integrated should_defer() into prompt_queue_runner.py. Configurable via env vars (JANE_MAX_PARALLEL, thresholds). psutil installed.
Priority: 1
Created: 2026-03-23

## Objective
Build a system load monitor that Jane checks before spawning parallel agents/subprocesses. If the system is under heavy load, use fewer workers to keep jane-web and the Android app responsive.

## Problem
When Jane runs multiple background agents in parallel (e.g., 4 job queue items simultaneously), CPU and memory spike, making the web UI and Android app sluggish or unresponsive.

## Design

### 1. System Load Monitor (`agent_skills/system_load.py`)
```python
def get_system_load() -> dict:
    """Returns current CPU, memory, and load average."""
    # cpu_percent, memory_percent, load_avg_1min, load_avg_5min

def recommended_parallelism() -> int:
    """Returns how many parallel agents/subprocesses are safe to run."""
    # Based on: CPU cores, current load, available memory
    # Examples:
    #   Load < 30% CPU, > 4GB free → 4 parallel
    #   Load 30-60% CPU → 2 parallel
    #   Load > 60% CPU or < 2GB free → 1 (sequential)

def should_defer() -> bool:
    """Returns True if the system is too loaded to start new work."""
    # Used by cron jobs to skip runs when system is stressed
```

### 2. Integration Points
- Jane CLI: check `recommended_parallelism()` before launching background agents
- Prompt queue runner: check before starting next prompt
- Briefing fetcher: check before spawning parallel topic fetches
- Any cron job: check `should_defer()` at start

### 3. Configuration
- `JANE_MAX_PARALLEL` env var (hard cap, default: 4)
- `JANE_LOAD_THRESHOLD_CPU` env var (default: 60%)
- `JANE_LOAD_THRESHOLD_MEM_GB` env var (default: 2.0 GB free minimum)

## Files Involved
- New: `agent_skills/system_load.py`
- Update: `agent_skills/prompt_queue_runner.py` — check before running
- Update: `agent_skills/essence_scheduler.py` — check before scheduling
- Update: cron job scripts — add `should_defer()` check

## Notes
- Use `psutil` for cross-platform CPU/memory monitoring
- Log decisions: "Reducing parallelism to 2 (CPU at 72%)" so we can tune thresholds
- Don't block — just reduce concurrency. Work still gets done, just slower.
