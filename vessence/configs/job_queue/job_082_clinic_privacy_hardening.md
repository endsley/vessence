# Job #82: Clinic Privacy Hardening — Keep Patient Data Off Cloud LLMs

Status: completed
Priority: high
Created: 2026-04-21
Completed: 2026-04-21

## Problem

Clinic patient data (names, health concerns, recommendations, visit summaries) must never leave the local process. Three leak paths exist today; only one is coincidentally blocked.

**Leak paths:**
1. **Stage 3 escalation** — If the classifier routes a clinic query to Stage 3 (low confidence, force_stage3, etc.), the full prompt including schedule.db data goes to Claude/cloud.
2. **Haiku thematic writeback** — `conv_manager.update_thematic_memory()` sends a turn to Haiku (cloud) to summarize. Currently skipped for Stage 2 via short-circuit at `jane_proxy.py:~1390`, but the skip is coincidence (tied to `is_stage3` check), not an explicit privacy rule.
3. **FIFO replay into Stage 3** — `vault_web.recent_turns` stores verbatim prior turns. If a follow-up non-clinic question escalates to Stage 3, the rolling transcript handed to Claude contains prior clinic turns with patient names. **This is the observed leak Chieh flagged.**

## Root Cause

No class-level privacy declaration. Every class is treated as public by default; the current Stage 2/Stage 3 split is about confidence and templating, not data sensitivity.

## Proposed Solution

### 1. Per-class privacy + routing flags in metadata

Add two fields to `metadata.py` in each class folder:

```python
no_stage3 = True          # never escalate this class to cloud LLM
privacy = "local_only"    # content must not leave the local process in any form
```

Defaults (when unset): `no_stage3 = False`, `privacy = None` (public). Apply both flags to `clinic_schedules_info/metadata.py`. Future clinic classes inherit the pattern.

### 2. Stage 2 is the terminus for `no_stage3` classes

Clinic classes must answer *inside* Stage 2. No Stage 3 fallback, no post-Stage-2 escalation to any cloud model.

In `jane_web/jane_v2/pipeline.py`:
- At every escalation decision point (force_stage3 abandon path ~line 1190, low-conf escalation ~line 1237, Stage 2 dispatch ~line 1276): if the classified class has `no_stage3 = True`, suppress escalation entirely. The Stage 2 handler's return value is the user-facing response.
- If the handler can't confidently answer, it returns a polite deflection (e.g., "I'm not sure about that one — can you rephrase?") rather than escalating.

**Local LLM usage stays inside the handler, not after it.** If the handler needs reasoning (e.g., resolving "patient number two" against a recent list), it calls `_call_local_llm(prompt_text)` internally — the `classes/get_time/handler.py:119` pattern. The handler still owns the final response. qwen2.5:7b via Ollama never runs "after Stage 2"; it's a tool the handler can invoke during its own work.

This puts more weight on handler quality (the turn 5463 bug becomes critical — there's no second chance), which is why the ordinal-resolution fix is in scope for this job.

### 3. FIFO write-time redaction (the observed leak)

In the FIFO write site (`jane_proxy.py:~1398-1403` where `vault_web.recent_turns` is updated):
- If the class's `privacy == "local_only"`:
  - Entry becomes `{role: <role>, content: "[private turn — class: <class_name>]", cls: <class_name>, privacy: "local_only"}`
  - Claude still sees the turn existed (preserves conversational coherence — he can respond "I can't see clinic details from here" if asked), but content is gone.
- Else: normal full-content entry.

The ledger (`VAULT_HOME/conversation_history_ledger.db`) keeps the **full** turn — it's on-disk, never leaves the box, and `show_transcript.py` needs it for debugging.

**Split of responsibilities:**
- Ledger = on-disk audit truth, full content.
- FIFO = in-memory working context, pre-redacted for privacy classes.

### 4. Harden the Haiku-skip with an explicit privacy check

Replace the current `if not is_stage3: return` short-circuit at `jane_proxy.py:~1390` with an explicit privacy gate:

```python
if cls_meta.get("privacy") == "local_only":
    _log_stage(session_id, "persistence_privacy_skip_haiku", ...)
    return
if not is_stage3:
    _log_stage(session_id, "persistence_stage2_skip_theme_summary", ...)
    return
```

So the privacy skip is intentional and survives any future change to the Stage 2/3 persistence path.

### 5. Fix Stage 2 "patient number N" resolution bug (turn 5463)

`clinic_schedules_info/handler.py:_patient_detail()` literal-substituted `"patient number two"` into a "no records for X" template instead of resolving the ordinal against the presented list. Fix: when the handler has just returned a patient list in the prior assistant turn, parse ordinals ("patient 2", "the second one", "patient number two") against that list before falling through to name lookup.

Scope this as part of this job since it's in the same handler and surfaced during the same discovery session.

## Files to Modify

- `jane_web/jane_v2/classes/clinic_schedules_info/metadata.py` — add `no_stage3 = True`, `privacy = "local_only"`
- `jane_web/jane_v2/pipeline.py` — honor `no_stage3` at escalation points, route to local LLM fallback
- `jane_web/jane_proxy.py` — FIFO write-time redaction, explicit Haiku privacy gate
- `jane_web/jane_v2/classes/clinic_schedules_info/handler.py` — fix ordinal resolution in `_patient_detail()`
- `memory/v1/conversation_manager.py` — accept + store `cls` on ledger turns (column add on `turns`)
- `configs/Jane_architecture.md` — document the `no_stage3` + `privacy` metadata flags
- `configs/memory_manage_architecture.md` — document ledger-vs-FIFO privacy split

## Acceptance Criteria

1. Clinic query in web UI → Stage 2 handler answers directly, never escalates. Verify by checking `jane_prompt_dump.jsonl` and Claude API logs show no clinic prompt.
2. Clinic query → pivot to non-clinic Stage 3 question → dump the assembled Stage 3 prompt; grep for patient names from `schedule.db` returns zero hits. Only `[private turn — class: clinic schedules info]` appears.
3. Clinic turn is present in `VAULT_HOME/conversation_history_ledger.db` full-text (ledger still works).
4. `show_transcript.py --platform android -n 3` still shows clinic content in the clear (ledger-sourced, local).
5. Follow-up "patient number two" after a patient-list response returns that patient's details, not the garbled template.
6. No Haiku summary call fires for any clinic turn (check `haiku_summaries.jsonl` stops growing on clinic turns).

## Decisions (confirmed / open)

1. ~~Other classes marked `local_only`?~~ → **Only `clinic_schedules_info`.** Everything else stays public. Confirmed 2026-04-21.
2. ~~If Ollama is down during a clinic query?~~ → **Don't respond.** Handler returns a "not available" message; no fallback to pure SQL. Confirmed 2026-04-21.
3. ~~Backfill `cls` column on existing ledger rows?~~ → **Going forward only.** No backfill — historical rows are already on disk and the ledger is local-only. Confirmed 2026-04-21.

## Completion Notes (2026-04-21)

**Landed changes:**
- `agent_skills/private_handler_utils.py` — `is_no_stage3`, `privacy_for`, `safe_deflection`, `SAFE_CLINIC_DEFLECTION`. Tolerant of space- and underscore-separated class forms.
- `jane_web/jane_v2/classes/clinic_schedules_info/metadata.py` — `no_stage3=True`, `privacy="local_only"`.
- `jane_web/jane_v2/pipeline.py` — `_persist_turn_to_fifo` redacts user/assistant/summary + strips entities/tool_results/evidence for local_only; `handle_chat` + `handle_chat_stream` no_stage3 guards; ledger mirror for private Stage 2 successes and deflections.
- `jane_web/jane_v3/pipeline.py` — `_classify_and_maybe_handle` safety net (crash, invalid shape, force_stage3, wrong_class all return safe deflection for no_stage3 classes); `_persist_turn_to_ledger` forwards `cls`.
- `jane_web/jane_proxy.py` — `_persist_turns_async` accepts `cls`, explicit Haiku/summary privacy gate independent of stage; all four call sites pass `cls`.
- `memory/v1/conversation_manager.py` — `cls` column on `turns` (CREATE + ALTER TABLE migration); `add_message`/`add_messages`/`_log_to_ledger` propagate.
- `jane_web/jane_v2/classes/clinic_schedules_info/handler.py` — ordinal resolution (`"patient number two"`, `"two"`, `"the second"`) + session-local pending-selection cache (PII never enters FIFO, but follow-up still resolves).
- `configs/Jane_architecture.md` §16.1 and `configs/memory_manage_architecture.md` §3.1/3.1a — documented the flags and the ledger-vs-FIFO split.

**Bugs AI review panel caught and I fixed:**
- *Functional regression (Gemini)*: FIFO redaction stripped `patient_list` from `pending_action.data`, breaking "patient 2" follow-ups for clinic. Fix: in-process session-keyed cache in the handler (`_PENDING_SELECTION_CACHE`) holds the list locally; resume logic falls back to cache when FIFO copy is empty.
- *Bare-word ordinals (Gemini)*: `_extract_selection_id` only handled digits alone. User saying "two" fell through. Fix: `_ID_PURE_WORD_RE` — strict full-match anchor so only standalone word-numbers are picked up.
- *Ledger gap in v2 (Gemini)*: v2 Stage 2 path didn't call `_persist_turn_to_ledger`. Fix: v2 `handle_chat` + `handle_chat_stream` mirror the v3 ledger write for `no_stage3` classes (narrow scope — preserves the privacy-class ledger invariant without changing behavior for public v2 classes).

**Checked but did not modify:**
- `_log_start` in `jane_proxy.py` writes `message_chars=N` only (no message content) — safe.
- `_dump_prompt` writes full message but runs only in Stage 3 paths, which clinic is now blocked from.
- Codex review timed out; Gemini review succeeded.
