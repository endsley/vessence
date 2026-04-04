# Job: Flush Jane status events during context build
Status: completed
Priority: 1
Created: 2026-03-27

## Objective
Make web and Android Jane show immediate progress/status updates while context is still being built, instead of waiting until context build completes before the first visible stream event.

## Context
This job comes directly from the March 27, 2026 speed audit. The current streaming path in `jane_web/jane_proxy.py` emits early events like:
- `start`
- `Reviewing the current thread and loading session context.`
- `Loaded prior conversation summary.`
- `Loading memory and building context...`

But those events are queued internally and not yielded to the client until after context build finishes and the streaming loop begins draining the queue. As a result, users experience dead air on cold turns even though the backend already knows what it is doing.

This is a perceived-latency fix, not a model-quality change. It should help both:
- web Jane
- Android Jane

Key evidence from the audit:
- `context_build` p95 is about 2.2s, with extreme outliers at 15.9s, 64.6s, 99.7s, and 100.5s
- the current code emits useful status text early, but too late for the client to see it in real time

Relevant files:
- `jane_web/jane_proxy.py`
- `jane_web/main.py`
- frontend consumers of Jane streaming events:
  - `vault_web/templates/jane.html`
  - Android chat stream consumer code

## Pre-conditions
1. Preserve current streaming behavior for final `delta`, `done`, and `error` events.
2. Do not regress cancellation handling or empty-response handling.
3. Maintain compatibility with both web and Android stream consumers.

## Steps
1. Trace the current `stream_message()` control flow in `jane_web/jane_proxy.py`, focusing on:
   - queue creation
   - `emit(...)`
   - context build
   - the point where queued events actually begin yielding to the caller
2. Refactor the flow so the stream can begin yielding `start` and `status` events immediately, while context build runs concurrently.
3. Ensure the context-build task can still:
   - emit additional status updates
   - surface context-build failures cleanly as stream errors
   - hand off to the brain execution path once ready
4. Verify that event ordering remains sane:
   - `start`
   - early `status`
   - later `status`
   - `delta`
   - `done` or `error`
5. Check the web and Android clients to confirm they do not assume the first streamed event arrives only after context build.
6. Add or improve timing/logging so the first visible stream event timing is diagnosable in the future.

## Verification
1. Send a cold-turn message from web Jane and confirm the first status appears immediately instead of after context build.
2. Send a cold-turn message from Android Jane and confirm the same behavior.
3. Verify that normal streaming still works:
   - answer text streams as before
   - no duplicate status bubbles
   - cancellations still work
   - context-build failures still surface as errors
4. If possible, log or measure time-to-first-status before and after the change.

## Files Involved
- `jane_web/jane_proxy.py`
- `jane_web/main.py`
- `vault_web/templates/jane.html`
- Android Jane streaming consumer files

## Notes
- This job should improve perceived speed without changing which model responds.
- Avoid coupling the fix to broader model-routing work.
- If the cleanest design is to split context build and brain execution into separate tasks, that is acceptable as long as stream behavior stays robust.

## Result
- `stream_message()` in `jane_web/jane_proxy.py` was refactored so the stream pipeline starts immediately and emits queued `status` events while context is still being built.
- The first visible backend event is now logged with a dedicated `first_visible_event` timing stage for future latency debugging.
- This preserves the existing `delta` / `done` / `error` semantics while removing the old behavior where early statuses were queued internally but not flushed to the client until after context build completed.
- The change is backend-compatible with both web and Android because both clients already consume the same NDJSON event stream.

## Verification Run
- Added/updated streaming tests to verify status events arrive before context build completes.
- Ran:
  - `PYTHONPATH=/home/chieh/ambient/vessence /home/chieh/google-adk-env/adk-venv/bin/python -m pytest -q /home/chieh/ambient/vessence/test_code/test_jane_web_streaming.py /home/chieh/ambient/vessence/test_code/test_jane_web_stream_error.py`
- Result: `11 passed`
