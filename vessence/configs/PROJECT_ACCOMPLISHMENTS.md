### 2026-07-15: Multi-Codex Scoped Coordination Board

- **Concurrent work board:** added `agent_skills/code_coordination.py`, a SQLite WAL task/message/lease board where agents claim only intended files or directory trees instead of locking an entire repository.
- **Atomic collision prevention:** overlapping claims are rejected with owner details, while non-overlapping work can proceed concurrently without a configured agent-count ceiling; old global locks remain honored during migration.
- **Codex awareness:** added the `jane-coordination` MCP server and lifecycle hooks that inject live board context, heartbeat active claims after tool use, and release lingering claims when the main session stops.
- **Safe global operations:** retained `code_edit_lock` only for repository-wide operations; exclusive acquisition now waits for active scoped claims, and its state appears on the shared board.
- **Hardened lifecycle:** task reposts replace old claims, finish/stale paths stamp claim releases, board text is bounded untrusted data, user instruction files are preserved, and four-hour stale leases safely cover three-hour work sessions.
- **Instructions and tests:** updated Jane/Codex/refactoring automation instructions and added focused coverage for concurrent 25-agent operation, conflicts, lifecycle cleanup, legacy-lock interoperability, context injection, and installer idempotence.

### 2026-07-10: Anthropic / Claude Receipt Downloader

- **New Anthropic receipt skill:** added `agent_skills/anthropic_receipts.py`, a Playwright-based downloader for Claude billing receipts.
- **Receipt extraction:** the skill opens Claude Settings > Billing, extracts invoice controls / Stripe invoice links, filters by count or date range, saves selected invoices as PDFs, and writes a `manifest.json`.
- **Login blocker documented:** created `$VESSENCE_DATA_HOME/data/browser_profiles/anthropic_claude/`, but the first login capture was blocked by Claude/Google automation detection before cookies were saved. The skill now reports that blocker explicitly and avoids endless retries.
- **Docs/tests:** registered the skill in `SKILLS_REGISTRY.md` and `Jane_architecture.md`; added focused parser/selection/blocker tests in `tests/test_anthropic_receipts.py`.

### 2026-07-10: OpenAI / ChatGPT Receipt Downloader

- **New OpenAI receipt skill:** added `agent_skills/openai_receipts.py`, a Playwright-based downloader for ChatGPT billing receipts.
- **Login profile:** captured reusable ChatGPT auth state in `$VESSENCE_DATA_HOME/data/browser_profiles/openai_chatgpt/` via Google sign-in and 2-step verification.
- **Receipt extraction:** the skill opens ChatGPT Settings > Billing, expands Billing history, extracts Stripe invoice links, filters by count or date range, saves invoices as PDFs, and writes a `manifest.json`.
- **Docs/tests:** registered the skill in `SKILLS_REGISTRY.md` and `Jane_architecture.md`; added focused parser/selection tests in `tests/test_openai_receipts.py`.

### 2026-06-30: RA Remission Research Cron

- **New RA research loop:** added `agent_skills/ra_research_cron.py`, a 2-hour cron researcher for Kathia's rheumatoid arthritis remission/asymptomatic-state goal.
- **Evidence caching:** every processed source is saved under `$VAULT_HOME/research/rheumatoid_arthritis_remission/papers/`; per-source summaries are cached in `summaries/`; raw run artifacts are cached under `$VESSENCE_DATA_HOME/research/rheumatoid_arthritis_remission/cache/`.
- **Smart synthesis:** each run invokes Codex as the high-judgment synthesis pass, rereads the compressed context and cached summaries, restates the mission, updates `context/compressed_context.md`, `discoveries.md`, `ra_remission_recommendation_scheme.md`, and the explicit action plan at `recommendations/recommendation_plan.md`.
- **Actionable recommendations:** the action plan converts cached research into at-home actions, tracking steps, tests/labs/imaging to discuss, food/diet options, lifestyle changes, medical strategy questions, and emerging technology/neuromodulation leads such as vagus-nerve stimulation.
- **Report cadence:** the first email report goes from `julioprocess@gmail.com` to Chieh after 4 runs; later reports send every 72 hours. The job uses `flock`, `timeout`, `nice`, and `ionice` to avoid overlap and reduce system impact.
- **Safety boundary:** the research dossier is explicit that medication/supplement/treatment changes require Kathia's rheumatologist.

### 2026-05-26: Standalone Codex Chroma Memory Bootstrap

- **Codex memory installer:** added `startup_code/install_codex_memory.py`, an idempotent setup script that writes the Codex `UserPromptSubmit` hook, persistent Jane memory instructions, and `jane-memory` MCP registration into `~/.codex/config.toml`.
- **First-run setup wiring:** `startup_code/first_run_setup.py` now runs the installer automatically when Codex CLI is available, so new Codex boots retrieve Jane's Chroma memories without manual config.
- **Docs:** updated Codex/Jane memory instructions in `AGENTS.md`, `README.md`, `configs/Jane_architecture.md`, and `configs/SKILLS_REGISTRY.md`.

### 2026-04-27: v3 pipeline respects resolver cancel/followup

- **Fixed v3 pending-action handling** (`jane_web/jane_v3/pipeline.py`): v3 previously only honored resolver `stage3_followup`. Resolver `cancel` and `followup` for `STAGE2_FOLLOWUP` slots were ignored, so a bare `No` after a clinic follow-up could get reclassified back into the clinic handler and repeat the same information instead of ending the conversation.
- **New behavior:** resolver `cancel` now short-circuits to `Ok.` with `conversation_end=True` and writes a cancelled pending marker; resolver `followup` now redispatches the owning Stage 2 handler directly with its `pending_data` and FIFO context, bypassing reclassification.
- **Regression tests:** added `test_code/test_v3_pending_resolution.py` covering both `cancel` and `followup`.

### 2026-04-27: Clinic schedule ordinal/day lookup fix

- **Fixed clinic Stage 2 misread for ordinal patient queries with a weekday** (`jane_web/jane_v2/classes/clinic_schedules_info/{metadata,handler}.py`): the prompt *"Can you tell me about the first patient this Tuesday in the clinic"* was routing to the clinic class but then answering incorrectly with *"There are no patients scheduled for this Tuesday"* even though Tuesday had 8 active patients in `schedule.db`. Two concrete causes were fixed:
- **Params normalization** in the handler: if the classifier emits `patient_index` or `patient_name`, the handler now normalizes the loader to `patient_detail` before building facts, even if qwen mistakenly labeled it `next_patient` or another generic loader.
- **Requested-day support for patient detail**: ordinal lookups now respect `params["day"]` instead of always reading `meta["today"]`. Named lookups also search the requested day first before falling back to the whole week.
- **Schema clarification**: clinic `PARAMS_SCHEMA` now explicitly tells qwen that phrases like *"first patient this Tuesday"* must map to `patient_detail`, not `next_patient`.
- **Verification**: new regression test `test_code/test_clinic_stage2_param_normalization.py` passes, `_build_facts(...)` now returns Tuesday's first patient (`Kamal Ahmed (matha)` at `8:00am` for week starting `2026-04-27`), and the Stage 2 phraser now replies: *"The first patient this Tuesday in the clinic is Kamal Ahmed, scheduled for 8:00am."*

### 2026-04-24: TELL_JOKE + DO_MATH Stage 2 handlers (v3 pipeline)

- **TELL_JOKE class** (`intent_classifier/v2/classes/tell_joke.py` + `jane_web/jane_v2/classes/tell_joke/`): explicit "tell me a joke" / "make me laugh" / "got any jokes" requests now route to a Stage 2 handler that asks qwen2.5:7b (temp 0.9, num_predict 100) for a single short clean joke. FIFO context lets "another joke" pivot. THOUGHT/REPLY tag parser hardened so a missing `REPLY:` tag doesn't cause TTS to read out the `THOUGHT:` prefix (Gemini review catch).
- **DO_MATH class** (`intent_classifier/v2/classes/do_math.py` + `jane_web/jane_v2/classes/do_math/`): arithmetic prompts ("17 times 23", "25 divided by 5", "15 percent of 80", "square root of 144") route to a Stage 2 handler that uses qwen2.5:7b ONLY to translate the spoken phrase into a single Python expression, then evaluates with a restricted `ast` walker. Allowed: numeric literals, binary ops (+ - * / // % **), unary ±, and a tiny safe call set (sqrt, pow, abs, round, floor, ceil). No names, no attribute access, no kwargs. Hardened per Gemini review: exponent cap `_MAX_EXPONENT=1000` to block DoS via `9**9999`, `TypeError` added to caught exceptions (sqrt(1,2) etc.), small-number formatting falls back to `:.6g` so 1/30000 doesn't render as "0".
- **Why the math split**: Qwen audit 2026-04-24 — Qwen got 10/10 simple arithmetic right but failed on multi-digit products (234×567 → 132066 vs actual 132678; 1234×5678 → 7006656 vs actual 7006652). Python is the source of truth for arithmetic; Qwen is the parser only.
- **Counter-pull exemplars added** to absorb adversarial false positives:
  - `send_message.py` / `send_email.py`: proxy-send phrasings ("tell Lee a joke", "email Bob a joke for his birthday", "send mom a funny meme")
  - `delegate_opus.py`: meta/figurative/rhetorical "joke"+"funny" ("what is a joke", "this meeting is a joke", "that's hilarious", "are you joking"), plus meta/venting/narrative about math ("I'm bad at math", "math is hard", "help me with my math homework", "how do I do long division")
  - `end_conversation.py`: targeted declines ("don't tell me a joke", "no jokes please", "stop with the jokes")
- **Adversarial tests pass**: TELL_JOKE 0/30 false positives (down from 19), DO_MATH 0/30 false positives (down from 5).
- **AI review**: Gemini caught the DoS/TypeError/precision issues in DO_MATH and the THOUGHT-leak in TELL_JOKE; all four were fixed before reporting done. Codex timed out at 120s.

### 2026-04-24: Multi-turn handler patterns + Stage 3 privacy gate (v3 pipeline)

- **Shared infra** (`agent_skills/end_phrase.py`, `confirmation.py`, `private_handler_utils.pending_continuation`/`end_conversation`): single source of truth for end-phrase detection, yes/no parsing, STAGE2_FOLLOWUP construction, and conversation-end signaling so handlers stop reinventing it.
- **Repeating-read pattern** wired into `todo_list` (after reading a category, ask "want another?" — pivot/garbage escalates to Stage 3 with privacy gate) and `weather` (same, with day continuation).
- **Confirm-or-revise pattern** wired into `send_message`: when qwen flags `COHERENT=no` with a resolved recipient, the handler builds the draft and asks "Should I send it?" instead of escalating. Resume order: `is_yes`→send + `conversation_end`; `is_no`→ask for revised body; `cancel`/`nevermind`→`end_conversation`. The fast-path (COHERENT=yes) is preserved unchanged. Critical ordering note in `agent_skills/confirmation.py`: in confirm-or-revise contexts, check `is_yes`/`is_no` BEFORE `end_phrase.is_end` because bare "no" answers a confirm prompt as "revise", not "abort".
- **One-shot action pattern** for `timer`: after firing the CLIENT_TOOL marker, emit `conversation_end=True` so the voice loop returns to wake-word mode.
- **Stage 3 privacy gate** (`jane_web/jane_v3/pipeline.py:_stage3_privacy_check`): chroma top-5 check against the raw prompt before any Opus escalation. Refuses with `PRIVACY_REFUSAL_TEXT` when EITHER (a) the closest in-range neighbor (distance ≤ 0.40) is from a `privacy="local_only"` class OR (b) ≥3 of 5 in-range neighbors are private. Defense-in-depth on top of the per-handler `is_no_stage3` check; catches prompts that bypass Stage 2 entirely (e.g. classified as `others`, low confidence).
- **Android end-of-conversation audio cue**: `ChatViewModel.endVoiceConversation()` plays `TONE_PROP_ACK` (short two-pip via `ToneGenerator`) before tearing down STT, giving an unambiguous "we're done" signal distinct from any "start of listening" tone.
- **Verification**: `/tmp/v3_simulate_multi_turn.py` (6 scenarios across todo / weather / timer / privacy / pivot / end-mid-flow) and `/tmp/v3_unit_sms_confirm.py` (6 SMS confirm-or-revise unit cases) pass.

### 2026-04-24: read_calendar Stage 2 routing rule + repeating-read pattern

- **Stage-2-vs-Stage-3 routing rule** (`jane_web/jane_v2/classes/read_calendar/handler.py`): only prompts that explicitly name a specific day or week (today, tonight, tomorrow, this week, next week, weekday names) stay in Stage 2. Vague queries ("what's coming up", "anything important") return `None` to escalate. Previously the handler defaulted to "today" for any unmatched range, silently swallowing vague queries.
- **Repeating-read pattern**: after answering one day, the handler asks "Would you like to know about another day?" with a `STAGE2_FOLLOWUP` pending. Loop continues for every reply that names a day; ends on `is_no` / `end_phrase.is_end` (→ `end_conversation`); pivot/garbage escalates to Stage 3. Bare "yes" parks on `awaiting_day_choice` and asks "Which day?". Resume priority — `_resolve_range` checked BEFORE `is_yes` so "yes, tomorrow" fetches tomorrow directly instead of falling into the day-choice branch. The old event-detail drilldown was removed; detail follow-ups now go through Stage 3.
- **Weekday support fix in `agent_skills/calendar_tools.resolve_range`**: weekday names (monday..sunday) now resolve to the upcoming occurrence (today if today matches, else next 1-6 days). Previously they fell through to the `ValueError` branch and silently returned today's events — so "what's on Friday" answered with today's calendar.
- **Verification**: `/tmp/v3_unit_calendar_resume.py` (12 cases covering routing, resume state machine, "yes, tomorrow" priority, end signals) and simulator scenarios G (today/tomorrow/friday/no loop) and H (vague → Stage 3) pass. AI panel review caught both bugs above; fixed before reporting.

### 2026-04-24: Stage 1 PARAMS_SCHEMA Migration + v2 Lock Removal + Stage 3 Params Plumbing

Extended the per-class `PARAMS_SCHEMA` pattern (previously only on `clinic_schedules_info`) across all 11 candidate classes so Stage 1 qwen emits structured params for every meaningful intent: `weather`, `timer`, `todo_list`, `shopping_list`, `read_calendar`, `read_messages`, `read_email`, `send_email`, `send_message`, `music_play`, `web_automation`. Handler opt-in remains introspection-based — classes with a `params` kwarg receive the extracted dict; classes without it behave as before.

**v2 supermajority lock removed.** `intent_classifier/v3/classifier.py` previously had a hard override: when chroma voted ≥4/5 with distance ≤0.12, the embedding winner beat qwen's verdict. The lock was a legacy patch from when qwen confused clinic with personal calendar; with per-class params extraction + vague/STT-unclear detection + the near-identical callout now advisory, the lock contradicted the v3 principle of "qwen decides, chroma is evidence". Also masked STT-cutoff classifications — e.g., `"what's the weather in"` was prevented from routing to `unclear`. `STAGE2_V2_LOCK_VOTES` / `STAGE2_V2_LOCK_DIST` constants dropped; override block deleted.

**Stage 3 params injection.** Extracted params now flow into Stage 3 (Opus) prompts via a new `_inject_extracted_params` helper in `jane_web/jane_v2/stage3_escalate.py` that prepends `[EXTRACTED PARAMS]` lines to the user turn. `escalate_stream` gained a `params: dict|None` kwarg; v3 `pipeline.py` passes `state["params"]`. Escalating classes (`web_automation`, `read_email`, `read_calendar`, and `send_*`/`read_messages` when they escalate) no longer force Opus to re-parse slot values Stage 1 already extracted.

**weather handler B refactor.** `weather/handler.py` rewritten as a params-driven context provider: `params["topic"]` (current|forecast|precipitation|wind|air_quality|pollen|overview) + `params["day"]` select a small fact slice from the cache; the full cache no longer gets dumped into the LLM context. Non-Medford `params["location"]` short-circuits to escalation. Sim at `/tmp/sim_weather_b.py` passes 9/9 (overview, current, tomorrow's rain, weekend forecast, air quality, wind, Friday forecast, Boston escalation, "why is AQ bad" research escalation).

**Remaining work — Job #83.** B-refactors queued for the other 6 Stage-2-reply handlers: `shopping_list`, `music_play`, `read_messages`, `todo_list`, `timer`, `send_message`+`send_email`. Ordered easiest→hardest; `send_*` last because they're real-world action verbs where a wrong `recipient`/`body` sends a wrong message. Schemas (A half) are ready for all 6 — only handler dispatch needs rewriting.

**Files:** `intent_classifier/v3/classifier.py`, `jane_web/jane_v2/stage3_escalate.py`, `jane_web/jane_v3/pipeline.py`, `jane_web/jane_v2/classes/{weather,timer,todo_list,shopping_list,read_calendar,read_messages,read_email,send_email,send_message,music_play,web_automation}/metadata.py`, `jane_web/jane_v2/classes/weather/handler.py`, `configs/job_queue/job_083_stage2_handler_b_refactors.md`.

### 2026-04-21: Clinic Privacy Hardening (Job #82)

Clinic schedule data (patient names, health concerns, visit summaries from `$VESSENCE_DATA_HOME/schedule.db`) must never leave the local process. Three leak paths closed: Stage 3 escalation (classifier could route clinic to cloud Opus), Haiku thematic writeback (cloud summarizer on every turn), and FIFO replay (a non-clinic follow-up escalating to Stage 3 replayed prior clinic turns verbatim — the observed leak).

**Approach — per-class privacy declarations.** Two metadata flags now drive policy:
- `no_stage3 = True`: Stage 2 handler IS the final answer-giver. Pipeline guards at every escalation point (v2 `handle_chat`, v2 `handle_chat_stream`, v3 `_classify_and_maybe_handle`) substitute a class-agnostic `SAFE_CLINIC_DEFLECTION` ("I'm not sure about that one — can you rephrase?") on handler crash, invalid shape, explicit escalation request, or wrong-class flag.
- `privacy = "local_only"`: `_persist_turn_to_fifo` redacts `user_text`/`assistant_text`/`summary` to `[private turn — class: <name>]`, strips `entities`/`tool_results`/`evidence`, keeps `pending_action` bookkeeping fields only. `_persist_turns_async` in `jane_proxy.py` has an explicit privacy gate (independent of stage) that skips Haiku thematic memory + qwen session summary for local-only turns — a deliberate rule, not a Stage-2 coincidence.

**Ledger split.** The SQLite ledger at `$VAULT_HOME/conversation_history_ledger.db` retains full clinic content (on-disk, never cloud-facing) and now carries a `cls` column per turn (CREATE + ALTER TABLE migration; legacy rows keep NULL `cls`). `show_transcript.py` and crash recovery stay functional; only the FIFO → cloud prompt path is scrubbed.

**Files:** `agent_skills/private_handler_utils.py` (new), `jane_web/jane_v2/classes/clinic_schedules_info/{metadata,handler}.py`, `jane_web/jane_v2/pipeline.py`, `jane_web/jane_v3/pipeline.py`, `jane_web/jane_proxy.py`, `memory/v1/conversation_manager.py`, `configs/Jane_architecture.md` §16.1, `configs/memory_manage_architecture.md` §3.1a.

**Side-quest bug fix in the same handler (turn 5463):** `_extract_selection_id` handled digits but not word-number ordinals, so "patient number two" fell through to a SQL LIKE on the full phrase and returned a garbled "I don't have detail records for okay can you tell me more patient number two". Added `_ID_WORD_PREFIXED_RE` (one–twelve, first–twelfth, with/without "the") plus `_ID_PURE_WORD_RE` for bare-word replies ("two.", "the second.").

**AI review panel (Gemini) caught three real issues, all fixed before marking done:**
1. *Functional regression.* FIFO redaction stripped `patient_list` from `pending_action.data` — breaking the "patient 2" follow-up entirely for clinic. The list IS the PII, so storing it in the FIFO defeats the purpose; storing it nowhere breaks the feature. Resolution: in-process session-keyed cache inside the handler (`_PENDING_SELECTION_CACHE`) keeps the list local; resume logic falls back to the cache when FIFO's copy is empty. Module-level dict, TTL'd with the existing `_expires_at`, opportunistic GC on insert.
2. *Bare-word ordinal gap.* Fixed as described above.
3. *v2 ledger gap.* v2 Stage 2 success paths only wrote to FIFO, never to the ledger. Contradicted the "ledger retains full clinic turns" invariant when `JANE_USE_V3_PIPELINE` is unset. Fix: mirror v3's `_persist_turn_to_ledger` call in v2 `handle_chat` + `handle_chat_stream` + both deflection paths, narrowly scoped to `is_no_stage3(cls)` so non-private v2 behavior is unchanged.

Codex timed out during the review; the other reviewer confirmed privacy invariants hold.

### 2026-04-16: Local-LLM Thrashing Fix, Thread-Leak Fix, Verify-First Hardening

Investigation-driven session. Three major issues diagnosed and fixed; one still open.

**1. Ollama cold-start thrashing — ROOT-CAUSED and FIXED.**
- **Symptom:** Android Jane "how's it going" taking 7.2s instead of ~540ms; Stage 2 gate occasionally stalling at 12s.
- **Root cause:** Ollama runs a separate runner per `(model, num_ctx)`. Multiple production callers were hitting `qwen2.5:7b` with divergent `num_ctx` — `gemma_router.py` hardcoded 32768, Stage 2 used 1024, and several callers (`agent_skills/llm_summarize.py`, `agent_skills/gemma_summarize.py`, `agent_skills/pipeline_audit_100.py`, `intent_classifier/v1/gemma_stage1.py`, `jane_web/main.py` prewarm, and critically `/home/chieh/ambient/skills/daily_briefing/functions/news_fetcher.py`) passed no `num_ctx` at all, inheriting Ollama's default (model's `n_ctx_train` = 32768 for qwen2.5). Every cross-caller transition triggered a full runner reload (~1.6–14s).
- **Fix:** `LOCAL_LLM_NUM_CTX` in `jane_web/jane_v2/models.py` is now the single source of truth (bumped 1024 → 8192; 2048 first, then 8192 on request for head-room). Every production caller imports and passes it explicitly. Registered in `preference_registry.json` as `unified_local_llm_num_ctx`.
- **Files touched:** `models.py`, `gemma_router.py`, `gemma_stage1.py`, `gemma_stage2.py`, `main.py` (prewarm), `pipeline_audit_100.py`, `llm_summarize.py`, `gemma_summarize.py`, `news_fetcher.py` (in `/home/chieh/ambient/skills/daily_briefing/functions/`).

**2. Jane-web dead-thread leak — ROOT-CAUSED and FIXED.**
- **Symptom:** `jane_web` uvicorn processes accumulating ~150 threads each; multiple live servers running at once after each graceful restart.
- **Root cause chain:** (a) `jane_web/main.py` had a module-level `_clear_port_if_occupied(8081)` that fired at every import — including the port-8084 ping-pong server spawned by `graceful_restart.sh`, which unconditionally SIGKILL'd whatever was on 8081; (b) systemd unit had `Restart=on-failure`, so the SIGKILL (`status=9/KILL`) triggered an auto-respawn on 8081; (c) the respawned server had nothing routing to it but kept 150 threads alive. Every graceful restart stacked another orphan.
- **Fix:** removed the hardcoded port-clearing hook from `main.py`; changed `Restart=on-failure` → `Restart=no` in `jane-web.service`; added a hard-invariant Step 0.6 in `graceful_restart.sh` that enumerates all `uvicorn jane_web` processes, keeps only the one the proxy currently routes to, and kills everything else before starting the ping-pong. Killed the current orphan (PID 357087) live — freed 153 threads.

**3. Web/Android verify-first hardening (Option C) — APPLIED.**
- **Background:** Codex added verify-first to Stage 3 earlier. Review uncovered gaps: the `STRONGER_VERIFY_INSTRUCTION` was *appended* to the user turn (easy to ignore vs. top-of-message), and there were no concrete tool-call examples. CLI Jane blocks at the `Stop` hook; Web Jane only nudged via prompt.
- **Fix:** Rewrote `STRONGER_VERIFY_INSTRUCTION` and `MEMORY_VERIFY_INSTRUCTION` in `jane_web/verify_first_policy.py` as `<verify_first priority="critical">` / `<memory_verify priority="critical">` XML blocks with 3 concrete tool-call examples each (`Grep(pattern=..., type="py")`, `Read("/abs/path")`, `Bash("tail -50 /logs/...")`, `Bash("python query_live_memory.py ...")`) and an anti-gaming guard: "a one-token tool call just to clear this block is not acceptable." Added `_copy_body_with_prepended_message` helper in `jane_web/jane_v2/pipeline.py` and switched `_apply_evidence_policy` to prepend the block + inline `[REQUIRED CHROMA MEMORY EVIDENCE]` at the TOP of the user turn. Codex's retry mechanism is still advisory (post-hoc audit); true parity with CLI's blocking behavior would require a buffered retry that costs streaming UX — deferred.

**4. Memory subsystem tightening.**
- `recent_turns` FIFO cap 10 → 20 (`vault_web/recent_turns.py`, preference `recent_turns_fifo_size_20`).
- Added in-process 60s TTL cache inside `memory/v1/memory_retrieval.py::build_memory_sections` so pipeline Stage 3 + `jane_proxy` context builder stop double-querying Chroma for the same turn.
- Added cross-turn chunk dedup in `jane_v2/pipeline.py::_apply_evidence_policy` via `session_memory_dedup.dedup` (reuses the CLI's `/tmp/jane_mem_seen_<sid>.txt` store). Evidence block now records `memory_chars_after_dedup` for audit.
- Fixed stale memory-evidence marker in `.claude/hooks/verify_first_hook.py` — `handle_user_prompt_submit` now unlinks `/tmp/claude-memory-evidence/<sid>.json` at turn start so a prior turn's "True" can't satisfy this turn's check.

**5. todo_list Stage 3 protocol expanded.**
- `jane_web/jane_v2/classes/todo_list/protocol.md` rewritten from 8 lines → 79 lines. Now documents cache path, category aliases (urgent, kathia, home, etc.), friendly spoken-form transforms ("Do it Immediately" → "your urgent list"), excluded categories (ambient project goals / legacy Jane header), broader-question handling, and stale `STAGE2_FOLLOWUP` semantics.

**6. New stage-breakdown benchmark.**
- `test_code/benchmark_stage_breakdown.py` isolates each pipeline stage: Stage 1 embed, Stage 2 gate (both bypass and full-LLM paths), Stage 2 handler (pure-Python vs LLM-backed), Stage 3 end-to-end. Results: Stage 1 ~22 ms, Stage 2 gate bypass ~0 ms, full gate LLM ~460 ms, pure-Python handler ~0.3 ms, LLM handler ~540 ms, Stage 3 ~12 s.

**Known issues surfaced but NOT fixed this session:**
- **Cron `$VESSENCE_HOME` expansion is broken.** Every cron using `$VESSENCE_HOME` stopped logging after 2026-04-03 (essence_scheduler, usb_sync, etc.). The USB backup cron fires every night per journalctl but the path `$VESSENCE_HOME/startup_code/usb_sync.py` expands to empty, so the script never actually runs. Last successful USB sync was **2026-04-15 11:41 (manual trigger)**, not a nightly. Fix needed: add `VESSENCE_HOME=/home/chieh/ambient/vessence` header to the crontab, or hardcode absolute paths.
- **`\btrace\b` false positive in verify-first regex.** The CLI `Stop` hook matches any occurrence of "Trace" or "trace" (even in system-emitted task-notifications), blocking conversational replies. Narrow to `\btrace\s+(?:the\s+)?(?:code|function|call|path|execution)\b` or similar, and skip `<task-notification>`/`<system-reminder>` wrapped content entirely.
- **Stage 3 `ToolUseCounter`** may not be receiving `tool_use` events from `stage3_escalate.escalate_stream` (it emits `delta`s). Needs verification before the audit log's `flagged=True` signal can be trusted.

---

### 2026-04-02: Android Wake Word, Process Management & UX Polish
- **Wake word detection working on Android:** OpenWakeWord with `hey_jarvis_v0.1.onnx` model, achieving 0.98+ detection scores. (`hey_jane` model broken, needs retraining.)
- **Always-listening service lifecycle:** `AlwaysListeningService` now stops cleanly on detection (releases mic), `ChatInputRow` launches system STT (same path as mic button). Proper stop/restart lifecycle prevents mic contention.
- **Process watchdog cron job:** `process_watchdog.py` runs every 5 min — kills zombie Docker containers, idle Gradle/Kotlin daemons (>10 min), and memory hogs.
- **TTS Docker resource limits:** Limited to 1 concurrent container with memory and CPU caps.
- **Gradle/Kotlin daemon auto-kill:** Daemons killed after 10 min idle to reclaim memory.
- **DiagnosticReporter for Android:** `DiagnosticReporter.kt` sends device diagnostics to `/api/device-diagnostics` endpoint for remote debugging.
- **Quick ack system:** ~200 responses across 12 categories in `_pick_ack()` in `jane_proxy.py`. Categorized messages skip ack (Opus answers directly); uncategorized get Opus-generated ack.
- **End-phrase detection:** Voice conversations detect end phrases to cleanly close the conversation loop.
- **Daily briefing idle check fixed:** Now uses `idle_state.json` instead of log file mtime. Briefing wrapped with `timeout 30m`.
- **Android UI cleanup:** Removed white bar, hamburger button, prompt queue UI. Added new session confirmation dialog.
- **Version bumped to 0.1.x series.**
- **Build script verification:** APK build now verifies version matches `version.json`.

### 2026-03-29: Codex-Specific Jane Web Streaming Path
- **New provider isolation:** Codex no longer shares Claude's persistent streaming implementation in Jane web. Claude remains on `persistent_claude.py`; Codex now has its own `persistent_codex.py`.
- **Codex transport:** Jane web now uses `codex exec --json` for first turn and `codex exec resume --json` for follow-up turns, keyed by Codex `thread_id`.
- **Normalized frontend effect:** Claude, Gemini, and Codex now use different internal CLI protocols but are documented as converging onto the same Jane web client event model: `status`, `delta`, `done`, `error`.
- **Richer Codex item mapping:** Codex non-final agent messages now surface as `thought`, command execution start/completion maps to `tool_use` / `tool_result`, and only the final assistant message is emitted as `delta`.
- **Safety constraint preserved:** Codex streaming changes were isolated so Claude's existing `stream-json` parser and routing path were not modified.

### 2026-03-23: Overnight Job Queue Completion (11 jobs)
- **Tunnel HTTP/2:** Switched Cloudflare tunnel from QUIC to HTTP/2 — eliminates stream resets on Android SSE
- **TTS Spoken Summary:** `<spoken>` block in Jane's responses — TTS reads conversational summary, display shows full text
- **Intent Classifier:** Gemma3:4b classifies messages (greeting/simple/medium/hard), sends instant ack, routes to optimal model (gemma/haiku/sonnet/opus)
- **Classifier Model Routing:** Classifier's model recommendation wired into brain call — haiku for simple, sonnet for medium, opus for hard
- **Sonnet for Web Chat:** Web/Android defaults to Sonnet 4.6 (3x faster than Opus) via WEB_CHAT_MODEL env var
- **Response Speed Optimization:** Context builder caching (5min TTL), pre-warm verification, memory daemon confirmed, lighter casual context
- **Memory Prefetch:** Pre-fetches memory context on page load (2s idle), cached 60s — memory ready before user types
- **Edge-Cache Static Assets:** Cache-Control middleware on both web servers — static 1 day, briefing images 1h, API no-store
- **Connection Pooling:** Explicit ConnectionPool(5, 5min) on Android OkHttpClient
- **Deep Stability Audit:** 28 fixes across 16 files — memory caps on all caches, zombie prevention, atomic writes, file locking, log rotation, task tracking
- **Tax Accountant Essence:** First true AI essence build (6 phases) — in progress

### 2026-03-23: Crash Investigation + Fixes
- **Root cause:** Claude CLI subprocesses accumulating without cleanup (11.8GB peak, 47 processes SIGKILL'd)
- **Fixes:** Process tracking per session, stale session reaper (30min), shutdown handler, systemd SIGINT/TimeoutStopSec=30
- **Additional:** Claude timeout default 180→600s, stream reset handling on Android, SSE keepalive 30→15s

### 2026-03-23: System Load Management
- **system_load.py:** CPU/memory monitor with recommended_parallelism() and should_defer()
- **Claude Code hook:** PreToolUse check before every Bash/Agent call (cached 10s)
- **wait_until_safe():** All 10 cron scripts wait+retry instead of skip when system busy
- **Thresholds:** Day 60%/Night 80% CPU, 4min retry interval

### 2026-03-23: Daily Briefing Enhancements
- "Heard it" dismiss button (web + Android + API)
- Hourly refresh (was 8h), idle-only
- LLM dedup before adding articles (deepseek-r1:32b)
- Keyword expansion (LLM enriches search terms, 7-day cache)
- 8 new topics (RA, Local News, NEU, BMNR, Ethereum, Health Tracking, ML, Bike Paths)
- Summarization switched to deepseek-r1:32b (local, via env var)

### 2026-03-23: Original Job Queue (16 jobs completed)
- Docker E2E test script, vault performance (5 improvements), tools vs essences refactor, web prompt queue UI verification, zero-downtime deploy, briefing audio cache verification
- 15 audit fixes (6 bugs + 10 doc drift + improvements), audit auto-fixer built + cron added

### 2026-03-22: Daily Briefing Essence — Full Build
- **Default essence** shipping with Vessence — personalized Google News-style news aggregation
- **Backend:** news_fetcher.py (Google News RSS + newspaper3k + BeautifulSoup scraping), article_indexer.py (ChromaDB), run_briefing.py (cron runner), 7 REST API endpoints
- **Web UI:** briefing.html (549 lines) — responsive card grid, topic filter pills, search, expand for full summary, TTS read-aloud, topic management modal, "Read All" FAB
- **Android UI:** BriefingScreen.kt + BriefingViewModel.kt + BriefingModels.kt — native Compose card grid, topic chips, TTS, article detail bottom sheet
- **Cron:** 8 AM + 6 PM daily fetch, logged to briefing.log
- **Data:** articles cached as JSON + images downloaded locally, indexed in per-essence ChromaDB, summaries via Haiku CLI

### 2026-03-22: Android App v0.0.18-0.0.20 — Chat UX Overhaul
- **v0.0.18:** Message queuing (send while Jane responds), ESC cancel button, New Chat button, platform awareness, TTS toggle, live broadcast banner
- **v0.0.19:** Queue progress as single updating bubble (not spam), announcement poller
- **v0.0.20:** Daily Briefing native UI integrated

### 2026-03-22: Live Broadcast System
- **broadcast.py** — per-user pub/sub with Haiku-summarized progress updates every 8s
- **SSE endpoint** GET /api/jane/live — clients subscribe to real-time Jane activity
- **Web + Android** — purple banner shows when Jane is working on another session

### 2026-03-22: Discord Disconnected
- All 4 notification scripts redirected to work log (prompt_queue_runner, ambient_heartbeat, nightly_audit, ambient_task_research)
- Systemd services stopped and disabled
- Bot watchdog cron disabled
- Infrastructure preserved for potential reconnection

### 2026-03-21: Android App v0.0.14 — VerifyError Fix
- **Root cause:** `ChatScreen.kt` (664 lines) caused `java.lang.VerifyError` on Android 13 because the Compose compiler generated a method exceeding the DEX verifier's 256-register limit (v299 > 255).
- **Fix:** Broke `ChatScreen.kt` into 4 files: `ChatScreen.kt` (337 lines, largest composable 135 lines), `ChatInputRow.kt` (290 lines), `AttachmentSheet.kt` (176 lines), `ChatMessageList.kt` (59 lines). No behavioral changes.
- **Version:** versionCode 17, versionName 0.0.14. Updated jane_web and vault_web ANDROID_VERSION.
- **Policy:** Discord kept as fallback communication channel until Android app is stable.

### 2026-03-21: Vault Web Merged into Jane Web
- **Single web server:** Jane web (port 8081) now serves all vault web (port 8080) functionality. Added `/vault`, `/chat`, `/downloads/*`, `/essences`, and all `/api/essences/*` routes to jane_web/main.py.
- **Essence picker:** Added a dropdown to the Jane chat header that shows available essences (fetched from `/api/essences`), plus quick links to Vault (files) and Jane (chat). Subtle grid icon with arrow, opens a floating panel with essence list and green dot for loaded essences.
- **Shared templates:** Jane web already used vault_web's templates and static assets. Updated app.html navigation to link back to Jane at `/` instead of the old `/jane` route.
- **Tunnel note:** vault.vessences.com needs Cloudflare tunnel redirect to jane.vessences.com. vault_web/ kept intact for backwards compatibility.

### 2026-03-15: Jane Wrapper Hardening & Noise Suppression
- **Compaction Loop Fix:** Resolved an infinite loop where the wrapper would trigger event compaction too frequently during large memory syncs.
- **Global UI Suppression:** Implemented `UI_SUPPRESSION: true` in `settings.json` to silence ADK startup noise and tool-call verbosity across all interfaces.
- **Screen Reader Mode:** Integrated `--screen-reader` flag into `jane_session_wrapper.py` to strip complex ANSI layouts and provide a high-fidelity, text-only stream for long-running CLI sessions.

### 2026-03-15: Jane Pro-Wrapper & High-Fidelity Ledger
- **Architecture Overhaul:** Transitioned `jane_session_wrapper.py` to an `asyncio`-based, PTY-enabled (Pseudo-Terminal) architecture with non-blocking reads and 1.5s idle-timeout turn detection.
- **Robustness Hardening:** Implemented ANSI escape code stripping, disabled PTY echo via `termios`, and offloaded all blocking ChromaDB/LiteLLM calls to background thread executors. User input is sent to Gemini immediately before sync, ensuring zero-latency interaction.
- **Sequential History Ledger:** Added a SQLite-based "Flight Recorder" (`conversation_history_ledger.db`) that records every turn with token counts and latency for auditing and crash recovery.
- **Live Telemetry:** Added `/debug` command and real-time context pressure tracking (TTFB, tokens, and duration) to the CLI.
- **Alias Optimization:** Updated `.bashrc` to separate the robust `jane` personality from the raw `gemini` plumbing tool.

This document logs verified and operational accomplishments for our projects. I must read this file at the start of every session to maintain an accurate overview of what has been achieved.

---

## Verified & Operational Accomplishments

1.  **Emergency Fallback System:** Cascade chain (Gemini 3 Flash → DeepSeek Chat → OpenAI GPT-4o → Local Qwen). 100% lockout-proof.
2.  **Comprehensive Diagnostic System:** `amber_health_check.py` and `AMBER_TROUBLESHOOTING.md` for instant reporting.
3.  **"Soul" USB Backup Rotation:** 10-day rotating backup of logic, memories, and configs. Daily 2:00 AM cron job.
4.  **Memory Librarian:** Gemma (`gemma3:4b`) sifts and summarizes raw vectors locally to reduce noise and Gemini costs, while Qwen is reserved for heavier background research/archival work.
5.  **Amber Vault Browser Website (2026-03-17):** Full Google Drive-style web app at `vault_web/`. FastAPI backend, Alpine.js + Tailwind frontend. Features: OTP auth via Discord, file browser with thumbnails, Amber chat with file context, inline media/PDF viewers, music player with playlists, share link generation. Served on port 8080 with Cloudflare Quick Tunnel for public HTTPS access. Both services auto-start on boot via systemd user services.
6.  **Vessence Phase 1 — Docker Public Release (2026-03-17, completed):** Full containerisation and public release prep. (a) Dockerfiles for 4 services: amber (ADK), vault (FastAPI), jane (all 3 CLIs baked in: Gemini CLI + Claude Code + OpenAI CLI), onboarding (setup wizard). (b) `docker-compose.yml` with Traefik reverse proxy serving `vault.localhost` and `jane.localhost`. (c) Onboarding web UI at port 3000: welcome → system check (RAM/disk/internet/ChromaDB) → setup form with inline API key validation and Test buttons → radio-button brain selection (Gemini/Claude/OpenAI; selecting Claude or OpenAI reveals the corresponding API key field) → identity interview (generates `user_profile.md`) → success screen that auto-opens 2 browser tabs. (d) First-time welcome overlays on vault and jane UIs (shown once, dismissed to localStorage). (e) Path sanitization: 60+ Python files updated to use `$AMBIENT_HOME` env var instead of hardcoded `/home/chieh/` paths. (f) Personal name sanitization: all hardcoded personal name references replaced with `os.environ.get('USER_NAME', 'the user')` across all agent prompts, system messages, memory scripts, and auth flows — fully portable for any user. (g) `jane_proxy.py` rewritten to route to all 3 CLIs based on `JANE_BRAIN` env var; brain label shown live in Jane's header. (h) GitHub Actions CI/CD building all 4 images on push to main with semver + sha tags for linux/amd64 + linux/arm64. (i) `.env.example` with fully annotated placeholders. (j) Cloudflare quick-tunnel fallback in docker-compose (`--profile cloudflare`). (k) USB backup switched from zip rotation to incremental rsync (`usb_sync.py`): `current/` mirror + weekly hard-link snapshots, 30-day retention; all old backup_20260315/17 folders purged; first sync: 1,432 files, snapshot 2026-03-17.

### 2026-03-26: Brain-Agnostic Onboarding Manifest
- Created ~/ambient/JANE_BOOTSTRAP.md as the definitive "handbook" for the Jane persona.
- Consolidated identity, relationship context (user, spouse, daughter), engineering protocols, and system architecture into a single high-signal document.
- Added environment and dependency verification checklists to ensure new AI instances (Gemini, Claude, OpenAI) can verify the Vessence stack.
