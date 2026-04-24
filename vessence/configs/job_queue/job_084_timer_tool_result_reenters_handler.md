# Job #84: Timer TOOL_RESULT Re-enters Handler as New Timer Request

Status: completed
Priority: medium
Created: 2026-04-23
Completed: 2026-04-23
Resolution: Option D (Android-side, one-line) — added `timer.set`,
`timer.cancel`, `timer.delete` to `FIRE_AND_FORGET` in
`android/.../ChatViewModel.kt`. Server-side defense-in-depth fixes
(Options A/B/C) deferred — revisit if a similar tool slips through.

## Problem

After Jane successfully fires a `timer.set` client tool, the Android phone posts
the tool result back to the server as the next user turn. The timer handler
interprets that result as a **brand-new timer request** and asks "Sure — how
long should the timer run?" — leaving a fresh pending slot the user never
intended.

### Reproduction (from `jane_android_3b191135`, 2026-04-23 13:35)

```
[13:35:19] YOU:   25 24 minutes
[13:35:19] JANE:  Got it, 24 minutes. What should I call this timer? Or say 'no label'.

[13:35:29] YOU:   No Label
[13:35:29] JANE:  Timer set for 24 minutes.

[13:35:30] YOU:   [TOOL_RESULT:{"tool":"timer.set","call_id":"eac890aa-...",
                   "status":"completed","message":"timer set for 1440000ms"}]
                   (tool results from previous request — please analyze and respond)
[13:35:30] JANE:  Sure — how long should the timer run?       ← BUG
```

User reported it as: "when I ask Jane to set a timer, and after asking me
about the label, you seem to forget to remove the 'prompt response expected'".

## Root Cause (traced through code)

1. `jane_v2/classes/timer/handler.py:_fire_set(..., from_followup=True)` writes
   a `pending_action` with `status: "resolved"`. `vault_web/recent_turns.py:
   _pending_is_active` correctly returns False for this, so
   `pending_action_resolver.resolve()` returns `None` on the next turn. ✅
   That part works — the pending slot is correctly released.

2. Phone posts `[TOOL_RESULT:{"tool":"timer.set",...}] (tool results from
   previous request — please analyze and respond)` as the next user message.

3. `stage1_classifier._strip_system_markers` strips the bracket for Stage 1
   (cleaned text is the parenthetical boilerplate), but
   **Stage 2 receives the raw prompt** — see
   `jane_web/jane_v2/pipeline.py:1319`
   (`stage2_dispatcher.dispatch(cls, prompt, ...)` — `prompt`, not `cleaned`).

4. Stage 1 still classifies as TIMER with High confidence (likely via ChromaDB
   semantic match on the "tool results" boilerplate, or via context hints).
   Pipeline dispatches to `timer/handler.handle(prompt, pending=None)`.

5. In `timer/handler.py:handle`:
   - `p_lower` contains `timer.set` → `wants_timer = True`.
   - `_parse_duration_ms("[TOOL_RESULT:...1440000ms]")` returns `0`. The
     `_NUM_UNIT_RE` regex doesn't match `1440000ms` because:
     * `m` matches but requires a `\b` word boundary (fails — next char `s`)
     * `s` alone has no preceding number at that position
   - Falls into the `if wants_timer or wants_create or ...` branch at
     `handler.py:462` → returns `_ask_duration({})` →
     **"Sure — how long should the timer run?"**

## Fix Options

Pick one — not all three.

### Option A (scoped, minimal): Bail in timer handler on tool-result echo

In `jane_v2/classes/timer/handler.py:handle`, at the top of the function
(before any parsing), return `None` if the raw prompt starts with
`[TOOL_RESULT:{"tool":"timer.`. A timer tool-result should never re-trigger
the timer handler. Keeps the blast radius tiny but is a patch, not a
root-cause fix.

### Option B (preferred — root cause): Strip system markers before Stage 2

In `jane_web/jane_v2/stage2_dispatcher.dispatch` (or at the pipeline call
site at `pipeline.py:1319` and `pipeline.py:1207`), apply
`stage1_classifier._strip_system_markers(prompt)` before handing to any
handler. Handlers should never see raw `[TOOL_RESULT:...]` / `[SMS SEND
REQUEST...]` / `[PHONE TOOL RESULTS...]` brackets — these pollute every
handler's keyword heuristics, not just timer's.

Audit other handlers for the same class of bug before shipping — at least
`send_message`, `send_email`, `todo_list`, and `read_calendar` do similar
substring matching on the raw prompt.

### Option C (wider change): Short-circuit pure-tool-result turns in pipeline

If the stripped prompt is empty or matches the `(tool results from previous
request — please analyze and respond)` boilerplate, route to "others" with
Low confidence so we skip Stage 2 entirely and let Stage 3 (or a no-op ack)
handle the turn. Broader fix but risks altering behavior for handlers that
legitimately want to see tool results (none today, but keep in mind).

## Acceptance Criteria

- [ ] After a timer fires, the next `[TOOL_RESULT:{"tool":"timer.set",...}]`
      turn does NOT trigger "Sure — how long should the timer run?" or any
      new pending_action.
- [ ] Same test for `timer.cancel`, `timer.list`, `timer.delete` tool
      results (should all be benign no-ops from Jane's side).
- [ ] If Option B is chosen, grep remaining Stage 2 handlers
      (`jane_v2/classes/*/handler.py`) for raw-prompt substring checks
      (`"timer" in p_lower`, `"message" in p_lower`, etc.) and verify none
      regress after marker stripping.
- [ ] Add a regression test in `test_code/` that feeds the timer handler a
      `[TOOL_RESULT:...]` prompt and asserts it does not return
      `_ask_duration` / `_ask_label`.

## Files Likely Touched

- `jane_web/jane_v2/stage2_dispatcher.py` (Option B)
- `jane_web/jane_v2/pipeline.py` (Option B or C, around lines 1207, 1319)
- `jane_web/jane_v2/classes/timer/handler.py` (Option A)
- `jane_web/jane_v2/stage1_classifier.py` — `_strip_system_markers` may
  need to become a shared util if Stage 2 starts using it
- `test_code/test_timer_tool_result_regression.py` (new)

## Related Context

- Handler resume logic and `_fire_set(from_followup=True)` are correct —
  don't rewrite them. The bug is downstream of resume, on the NEXT turn.
- `recent_turns._pending_is_active` correctly treats
  `status: "resolved"` as inactive — don't change that either.
- The duration regex at `timer/handler.py:_NUM_UNIT_RE` could also be
  hardened to not accept `1440000ms` buried in a JSON blob, but fixing the
  regex is treating a symptom; the real fix is not feeding tool-result
  JSON to the handler in the first place.
