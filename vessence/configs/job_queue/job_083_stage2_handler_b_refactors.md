# Job #83: Stage 2 Handler B-Refactors — Params-Driven Dispatch for 6 Remaining Classes

Status: completed
Priority: medium
Created: 2026-04-24
Completed: 2026-04-23

## Background

The v3 classifier already extracts a structured `params` object via per-class `PARAMS_SCHEMA` (see `intent_classifier/v3/classifier.py:_build_prompt`). Two classes use it end-to-end today:

- **clinic_schedules_info** — handler dispatches on `params["loader"]`, runs targeted SQL, lets Stage 2 LLM phrase the answer from a small fact slice.
- **weather** — handler dispatches on `params["topic"]` + `params["day"]`, slices the cache, lets Stage 2 LLM phrase.

Six other Stage-2-reply handlers still do their own regex/keyword intent detection in code. Migrating each to the params-driven "context provider" pattern eliminates the redundant parse, shrinks each handler by 30-60%, and keeps slot interpretation consistent with what Stage 1 already decided.

Schemas (the A half) are already declared and registered for ALL of these — confirmed via:
```
python -c "from jane_web.jane_v2 import classes as c; print({n: list((m.get('params_schema') or {}).keys()) for n,m in c.get_registry().items()})"
```

The remaining work is per-handler B (rewrite).

## Classes to Refactor (in suggested order, easiest → hardest)

### 1. shopping_list (177 lines)
- Schema keys: `action` (view|add|remove|clear|check), `items`
- Drop the local LLM intent parse; dispatch directly on `params["action"]`.
- Add a `params: dict|None=None` arg, pass through introspection from dispatcher.
- Sims: `/tmp/sim_shopping_b.py` covering all 5 actions + multi-item add.

### 2. music_play (148 lines)
- Schema keys: `kind` (song|artist|playlist|genre|mood|shuffle|resume), `query`
- Replace title/artist regex matching with `params["kind"]` switch.
- Resolver step: `query` against the song registry, with `kind` narrowing the search domain.
- Sims: each kind, plus ambiguous queries that should fall back to library search.

### 3. read_messages (225 lines)
- Schema keys: `filter_sender`, `unread_only`, `limit`
- Currently escalates after pulling messages; B = run targeted SQL based on params, hand a slim slice to Stage 2 LLM for the "important vs spam" classification.
- Privacy note: this class is already on the boundary — be careful that contact names don't leak to cloud LLMs in the slice. Consider `no_stage3` style protection.

### 4. todo_list (752 lines — biggest)
- Schema keys: `action` (read|add|remove), `category`, `item`
- Today's handler does: live Google Doc fetch, category alias resolution, add/remove via docs_tools, complex multi-turn category-prompt flow.
- B refactor should keep the multi-turn category-prompt flow but drive the "what action" branch off `params["action"]`.
- Highest-value class to refactor — biggest LOC win.

### 5. timer (485 lines, complex)
- Schema keys: `action` (set|cancel|list|count|delete), `duration_text`, `label`, `delete_target`
- STAGE2_FOLLOWUP multi-turn flow (asks for duration → asks for label → fires) MUST be preserved.
- B refactor: top-level dispatch on `params["action"]`. Keep the duration-parser since `duration_text` is raw NL. Keep the pivot-detection.
- Touches: pending_action, dispatcher's continuation_check, the resolve path.

### 6. send_message + send_email (343 + 348 lines, HIGHEST RISK)
- Schemas already declared with `recipient`/`to`, `body`, `confirm_signal`, `intent_kind`.
- These are real-world ACT verbs — getting it wrong sends a wrong text or wrong email.
- B refactor: handler validates `params`, resolves contact/address, fires CLIENT_TOOL marker for fast-path, escalates for ambiguous/complex.
- DO LAST. Run the full pipeline simulation suite (`/tmp/sim_clinic_*.py` style) plus a targeted send-flow regression test before declaring done.

## Acceptance Criteria

For each class:
- [ ] Handler signature accepts `params: dict|None=None` (kwarg).
- [ ] No regex/keyword intent detection that duplicates what's now in `PARAMS_SCHEMA`.
- [ ] At least one simulation script (`/tmp/sim_<class>_b.py`) covering all action enum values.
- [ ] No regression on existing transcripts (run `/tmp/sim_clinic_pivots.py` style chains touching the class).

For the whole job:
- [ ] All 6 classes' handlers depend on params, not on local prompt parsing.
- [ ] After job completion: restart server gracefully, verify no Android contract changes (no APK rebuild needed).

## Already Done This Session (2026-04-24)

- A — `PARAMS_SCHEMA` declared and registered for all 11 candidate classes.
- v2 supermajority lock removed from `intent_classifier/v3/classifier.py`.
- Stage 3 plumbing: `escalate_stream` now accepts `params=` and prepends an `[EXTRACTED PARAMS]` block via `_inject_extracted_params` in `jane_web/jane_v2/stage3_escalate.py`. v3 pipeline passes `state["params"]` through.
- weather B done — `jane_web/jane_v2/classes/weather/handler.py` rewritten as context-provider; sim at `/tmp/sim_weather_b.py` passes 9/9.
