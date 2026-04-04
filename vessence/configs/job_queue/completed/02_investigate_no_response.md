# Job: Investigate and fix "(no response)" messages in web Jane
Status: completed
Priority: 1
Created: 2026-03-27

## Objective
Web Jane frequently returns "(no response)" or empty responses to the user. Deep investigate the root causes and fix them.

## Context
The user has been seeing "(no response)" type messages from Jane on the web UI. This could stem from multiple failure modes in the pipeline:

1. **Standing brain process died or hung** — `jane/standing_brain.py` manages a long-lived CLI process. If it crashes, times out, or produces empty output, the response may come back empty.
2. **Brain adapter returned empty string** — `jane_web/jane_proxy.py` `_execute_brain_stream()` / `_execute_brain_sync()` may return `""` which gets passed through as-is.
3. **Stream terminated early** — The SSE stream in `jane_web/main.py` (event_stream generator around L1889) may hit a timeout, connection error, or exception that causes `done` to fire with no accumulated text.
4. **Frontend rendering** — `vault_web/templates/jane.html` `applyStreamEvent()` may receive a `done` event before any `delta` events, displaying an empty bubble.

Key files in the pipeline (from CODE_MAP_CORE.md):
- `jane_web/main.py` — streaming endpoint, L1888+
- `jane_web/jane_proxy.py` — `stream_message()` L696+, `send_message()` L559+
- `jane/standing_brain.py` — CLI process management
- `vault_web/templates/jane.html` — `applyStreamEvent()` L1158+

Timing log at: `$VESSENCE_DATA_HOME/logs/jane_request_timing.log`
Prompt dump at: `$VESSENCE_DATA_HOME/logs/jane_prompt_dump.jsonl`
Jane web log at: `$VESSENCE_DATA_HOME/logs/jane_web.log`

## Pre-conditions
None.

## Steps
1. Search `jane_web.log` for recent errors, timeouts, and empty responses — correlate timestamps with "(no response)" occurrences
2. Search `jane_request_timing.log` for `brain_execute_error` and `brain_execute_cancelled` entries (the audit showed 20 errors avg 106s, 28 cancellations avg 100s — these are likely the source)
3. Trace the code path for each failure mode:
   a. What happens when `_execute_brain_stream()` raises an exception? Does the frontend get an error event or just silence?
   b. What happens when the standing brain returns an empty string? Is there a guard?
   c. What happens when the stream times out (30min `asyncio.timeout` at L1897)?
   d. What happens on `ConnectionError` / `OSError` during streaming?
4. For each identified gap, add:
   - A user-visible error message instead of "(no response)"
   - Logging so future occurrences are diagnosable
5. Check if the standing brain auto-restarts after a crash — if not, add recovery logic
6. Check the frontend `applyStreamEvent()` — does it handle `done` with empty accumulated text gracefully?

## Verification
1. After fixes, trigger edge cases if possible (e.g., kill the standing brain mid-response, send a message that times out)
2. Verify the user sees a meaningful error message instead of "(no response)"
3. Check `jane_web.log` for new error entries with actionable context
4. Restart jane-web service and confirm normal operation

## Files Involved
- `jane_web/jane_proxy.py` — stream_message, send_message, brain execution
- `jane_web/main.py` — streaming endpoint, error handling
- `jane/standing_brain.py` — CLI process lifecycle
- `vault_web/templates/jane.html` — frontend event handling
- `$VESSENCE_DATA_HOME/logs/jane_web.log` — server logs
- `$VESSENCE_DATA_HOME/logs/jane_request_timing.log` — timing data

## Notes
- The timing audit showed 20 `brain_execute_error` (avg 106s) and 28 `brain_execute_cancelled` (avg 100s) — these are strong candidates for the "(no response)" issue.
- Prior conversation history mentions this has been an ongoing issue that was partially investigated but not fully resolved.

## Result
- Backend stream pipeline was refactored so context build now runs inside the pipeline task rather than blocking the stream setup path. This lets status/error events surface earlier and avoids the old "silent until later" behavior.
- The stream path now retains an explicit `final_response` in the pipeline task and continues to emit a user-visible error when the brain returns an empty string instead of allowing the UI to present a fake successful empty response.
- The Jane web frontend no longer falls back to `_(no response)_` for empty Jane responses. It now shows: `⚠️ Jane finished without returning text. Please try again.`
- Existing backend error handling for cancelled/interrupted streams remains intact, and tests now cover the empty-response path explicitly.

## Verification Run
- Ran:
  - `PYTHONPATH=/home/chieh/ambient/vessence /home/chieh/google-adk-env/adk-venv/bin/python -m pytest -q /home/chieh/ambient/vessence/test_code/test_jane_web_streaming.py /home/chieh/ambient/vessence/test_code/test_jane_web_stream_error.py`
- Result: `11 passed`
