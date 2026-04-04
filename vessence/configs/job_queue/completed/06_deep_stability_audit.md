# Job: Deep Stability Audit — Find and Fix All Crash-Prone Code

Status: complete
Completed: 2026-03-24 00:55 UTC
Notes: 28 fixes across 16 files. Memory caps on all caches, zombie prevention, atomic writes, file locking, log rotation, task tracking. Service verified healthy.
Priority: 1
Model: opus
Created: 2026-03-23

## Objective
Systematically audit the entire codebase for patterns that could cause crashes, memory leaks, resource exhaustion, or service unavailability. For each issue found, implement a proper long-term fix — not a patch or band-aid.

## Audit Scope

### 1. Subprocess Lifecycle
- Search all Python files for `subprocess.Popen`, `subprocess.run`, `asyncio.create_subprocess_exec`, `os.system`
- For each: verify the process is always killed on error/timeout/cancellation
- Check: is stdout/stderr always read (preventing pipe deadlock)?
- Check: is there a timeout on every subprocess call?
- Fix: add proper cleanup in finally blocks, not just except blocks

### 2. Async Resource Leaks
- Search for `aiohttp.ClientSession`, `httpx.AsyncClient`, file handles opened in async context
- Verify all are closed in `finally` or used with `async with`
- Check for fire-and-forget coroutines (`asyncio.create_task` without tracking)
- Fix: track all background tasks, cancel on shutdown

### 3. Memory Growth Patterns
- Search for unbounded lists, dicts, or caches that grow without limit
- Check: `_sessions`, `_active_procs`, conversation histories, in-memory caches
- Check: ChromaDB client connections — are they being opened and never closed?
- Check: large string accumulation in streaming responses
- Fix: add size limits, TTLs, or periodic cleanup to all in-memory stores

### 4. File Handle Leaks
- Search for `open()` calls without `with` context manager
- Search for response objects not closed (requests, aiohttp)
- Check: log file handles — are they opened once or per-write?
- Fix: convert to context managers

### 5. Error Handling Gaps
- Search for bare `except:` or `except Exception:` that swallow errors silently
- Check: are critical failures logged before being swallowed?
- Check: do retries have backoff and max attempts (not infinite loops)?
- Check: is there any recursion that could stack overflow?
- Fix: add logging to all catch blocks, add circuit breakers to retry loops

### 6. Thread/Process Safety
- Check: are shared mutable objects (dicts, lists) accessed from multiple threads/coroutines without locks?
- Check: `_sessions` dict in persistent managers — is the lock always held during reads AND writes?
- Check: file writes from concurrent cron jobs — any race conditions?
- Fix: add locks where needed, use atomic file operations

### 7. External Service Dependencies
- Check: what happens when Ollama is down? ChromaDB unreachable? Cloudflare tunnel drops?
- For each external dependency: is there a timeout? A fallback? Graceful degradation?
- Check: does jane-web crash if Ollama is down, or does it degrade?
- Fix: add circuit breakers and health checks for each dependency

### 8. Disk Space / Log Growth
- Check: are there any log files or data stores that grow without limit?
- Check: essence_data (articles, audio, images) — any cleanup?
- Check: ChromaDB disk usage — does it grow indefinitely?
- Check: /tmp files created by subprocesses — are they cleaned up?
- Fix: add rotation, TTL-based cleanup, or size caps

### 9. Import and Startup Failures
- Check: can jane-web start cleanly if any optional dependency is missing?
- Check: are all imports guarded for optional packages (ollama, pynput, etc.)?
- Check: what happens if .env is missing or malformed?
- Fix: graceful degradation on missing dependencies

### 10. Signal Handling
- Check: does the application handle SIGTERM, SIGINT, SIGHUP properly?
- Check: are background threads/processes cleaned up on signal?
- Check: can the service restart cleanly without leaving orphans?
- Fix: register signal handlers, ensure clean shutdown path

## Approach
1. For each category above, grep/scan the actual code
2. Document every issue found with file:line reference
3. For each issue, implement the LONG-TERM fix (not a workaround)
4. After all fixes, restart jane-web and verify clean startup
5. Run a stress test: rapid message sending, concurrent sessions, service restart mid-request

## Output
- List of all issues found and fixed
- Any issues that couldn't be fixed with explanation
- Recommended monitoring/alerting for future detection

## Files to Audit
- `jane_web/main.py`, `jane_web/jane_proxy.py`, `jane_web/broadcast.py`
- `jane/persistent_claude.py`, `jane/persistent_gemini.py`
- `jane/brain_adapters.py`, `jane/context_builder.py`
- `jane/automation_runner.py`
- `agent_skills/prompt_queue_runner.py`, `agent_skills/essence_scheduler.py`
- `agent_skills/conversation_manager.py`
- `agent_skills/search_memory.py`
- `amber/tools/*.py`
- All cron scripts in `agent_skills/` and `startup_code/`

## Notes
- Do NOT just add try/except wrappers — fix the root cause
- Every fix should prevent the class of bug, not just the specific instance
- If a pattern is repeated (e.g., unguarded subprocess in 5 places), fix ALL instances
- Run this during nighttime for thoroughness — it's read-heavy, not compute-heavy
- After fixing, the nightly audit should find zero new issues on the next run
