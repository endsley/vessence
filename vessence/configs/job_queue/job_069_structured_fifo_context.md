# Job: Structured FIFO Context for Jane's 3-Stage Pipeline

Status: completed
Priority: 1
Model: opus
Created: 2026-04-15

## Objective
Upgrade Jane's recent-turn FIFO from prose-only summaries to structured context records with a prose summary, so Stage 1, Stage 2, and Stage 3 can reliably handle context-dependent prompts like "yes", "send it", "cancel that", "what about tomorrow", and "tell him that".

## Context
Jane's current v2 pipeline is a 3-stage prompt handler:

1. **Stage 1**: `jane_web/jane_v2/stage1_classifier.py` strips tool/system markers and calls `intent_classifier.v2.classifier.stage1_classify(cleaned)`.
2. **Stage 2**: `jane_web/jane_v2/stage2_dispatcher.py` dispatches to class handlers. It receives recent FIFO context from `jane_web/jane_v2/recent_context.py`.
3. **Stage 3**: `jane_web/jane_v2/stage3_escalate.py` delegates to the v1 brain when Stage 1 is low-confidence, Stage 2 declines, or the class is `others`.

The current Stage 1 classifier is prompt-only:

- `intent_classifier/v2/classifier.py` embeds only the current `message`.
- `stage1_classify(message, session_id="")` has a `session_id` argument, but it is currently unused.
- The classifier is ChromaDB top-5 nearest-neighbor voting over examples in `intent_classifier/v2/classes/*.py`.
- Current safeguards are confidence/margin/distance gates and Stage 2/Stage 3 fallback, not true context-aware classification.

The current FIFO path is prose-summary oriented:

- `jane_web/jane_v2/pipeline.py::_persist_stage2_to_fifo()` writes a compact prose summary through `vault_web.recent_turns.add()`.
- `jane_web/jane_v2/recent_context.py::get_recent_context()` reads those summaries and joins them into an LLM-readable context block.
- Stage 2 handlers that accept `context=` can use this prose block. For example:
  - `jane_web/jane_v2/classes/send_message/handler.py` uses context for pronouns and unspecified recipient/body.
  - `jane_web/jane_v2/classes/greeting/handler.py` uses context to avoid greeting false positives.
- This helps after Stage 1, but Stage 1 still cannot route contextual short prompts correctly.

Chieh's design direction from the planning session:

- Store **structured data plus prose** in FIFO.
- Do not force models/classifiers to infer known state from prose.
- Structured context should improve Stage 1 routing, Stage 2 validation, and Stage 3 continuity.
- Keep prose because Opus/Stage 3 benefits from natural context.
- Render structured records differently per consumer instead of dumping raw JSON everywhere.

## Desired Architecture
Each recent FIFO turn should store both machine-readable fields and a concise human-readable summary.

Example record:

```json
{
  "schema_version": 1,
  "turn_id": "2026-04-15T12:31:02Z",
  "session_id": "abc",
  "created_at": "2026-04-15T12:31:02Z",
  "user_text": "tell Kathia I love her",
  "assistant_text": "Send 'I love you' to Kathia?",
  "summary": "Chieh asked Jane to text Kathia. Jane drafted 'I love you' and is waiting for confirmation.",
  "stage": "stage2",
  "intent": "SEND_MESSAGE",
  "confidence": "High",
  "entities": {
    "recipient": "Kathia",
    "message_body": "I love you"
  },
  "pending_action": {
    "type": "SEND_MESSAGE_CONFIRMATION",
    "status": "awaiting_user",
    "expires_at": "2026-04-15T12:36:02Z"
  },
  "tool_results": [],
  "safety": {
    "side_effectful": true,
    "requires_confirmation": true
  }
}
```

Consumer behavior:

- **Stage 1** should receive a compact structured state packet before classification:
  - active/pending action
  - last intent
  - recent entities
  - concise recent summary
- **Stage 2** should receive structured records or a rendered task-context block:
  - entities
  - tool results
  - pending action
  - recent summary
- **Stage 3** should receive prose plus rendered structured state:
  - not raw noisy JSON by default
  - compact block such as: `Current state: awaiting confirmation to send SMS to Kathia: "I love you". User may confirm, revise, or cancel.`

The critical routing principle:

```text
If explicit session state already says Jane is awaiting confirmation or correction,
handle that state before treating the prompt as a standalone fresh intent.
```

## Scope
Implement structured FIFO support without breaking existing prose-only callers.

Do this incrementally:

1. Add structured record support to the FIFO layer.
2. Preserve existing `get_recent()` behavior for compatibility.
3. Add new structured read/render helpers.
4. Update v2 pipeline writes to include structured data where available.
5. Add a pre-Stage-1 state resolver for pending actions.
6. Pass compact structured context into Stage 1 and Stage 2.
7. Render structured context for Stage 3.

## Files To Inspect
- `vault_web/recent_turns.py` — current FIFO storage API and summary format.
- `agent_skills/conversation_manager.py` — currently writes recent turns around line ~850 per older notes.
- `jane_web/jane_v2/pipeline.py` — `_persist_stage2_to_fifo()`, `_classify_and_try_stage2()`, Stage 3 escalation context injection.
- `jane_web/jane_v2/recent_context.py` — current prose context renderer.
- `jane_web/jane_v2/stage1_classifier.py` — wrapper around prompt-only classifier.
- `intent_classifier/v2/classifier.py` — current Chroma k-NN classifier; `stage1_classify(message, session_id="")` currently ignores `session_id`.
- `jane_web/jane_v2/stage2_dispatcher.py` — universal gate and handler dispatch with `context=`.
- `jane_web/jane_v2/classes/send_message/handler.py` — important context-dependent handler.
- `intent_classifier/v2/classes/send_message.py` — includes continuation examples like "yes send it" and "go ahead and send it".
- `intent_classifier/v2/classes/end_conversation.py` — ambiguous cancel/stop examples.
- `jane_web/jane_v2/stage3_escalate.py` — Stage 3 handoff.

## Implementation Steps

1. **Respect the code edit lock**
   - Before editing source code, acquire the mandatory lock:
     ```python
     from agent_skills.code_lock import code_edit_lock

     with code_edit_lock("jane-codex"):
         # edit files
     ```
   - If the lock is held, wait. Do not bypass it.

2. **Audit current FIFO storage**
   - Read `vault_web/recent_turns.py`.
   - Identify whether records are SQLite rows, plain strings, JSON strings, or another format.
   - Preserve the existing public `add()` and `get_recent()` behavior so old callers still work.

3. **Define a structured FIFO schema**
   - Add a schema version.
   - Required fields:
     - `schema_version`
     - `turn_id`
     - `session_id`
     - `created_at`
     - `user_text`
     - `assistant_text`
     - `summary`
     - `stage`
     - `intent`
   - Optional fields:
     - `confidence`
     - `entities`
     - `pending_action`
     - `tool_results`
     - `safety`
     - `metadata`
   - Keep records compact. This is hot-path context, not archival memory.

4. **Add structured FIFO APIs**
   - Suggested APIs in `vault_web/recent_turns.py`:
     ```python
     def add_structured(session_id: str, record: dict) -> None: ...
     def get_recent_structured(session_id: str, n: int = 10) -> list[dict]: ...
     def get_active_state(session_id: str) -> dict: ...
     ```
   - `get_active_state()` should compute the most recent unresolved `pending_action`, last intent, recent entities, and recent summaries.
   - Expire pending actions using their `expires_at` when present.
   - If old rows are prose-only, return them as records with `summary` populated and minimal metadata.

5. **Add context renderers**
   - Extend or replace `jane_web/jane_v2/recent_context.py` with helpers like:
     ```python
     def get_stage1_context_packet(session_id: str | None) -> dict: ...
     def render_stage2_context(session_id: str | None, max_turns: int = 3) -> str: ...
     def render_stage3_context(session_id: str | None, max_turns: int = 10) -> str: ...
     ```
   - Stage 1 packet should be structured and short.
   - Stage 2 render should include relevant entities/tool results/pending action.
   - Stage 3 render should be concise prose plus current structured state.

6. **Add a pre-Stage-1 state resolver**
   - Before normal Stage 1 classification in `pipeline._classify_and_try_stage2()`, check active state.
   - If there is a pending action, route short continuations deterministically where safe:
     - confirmation: `yes`, `yeah`, `go ahead`, `send it`, `do it`
     - cancellation: `no`, `cancel`, `never mind`, `don't`, `stop`
     - revision: prompts starting with `actually`, `change it to`, `make it`, etc. should usually Stage 3 unless a safe resolver exists.
   - For side-effectful actions, only execute if the pending action has all required slots and the user clearly confirms.
   - Otherwise fall through to normal Stage 1 or Stage 3.

7. **Make Stage 1 context-aware**
   - Update `stage1_classifier.classify()` to accept `session_id: str | None = None`.
   - Update call sites in `pipeline.py` to pass the session id.
   - For the current Chroma classifier, avoid embedding huge context blindly.
   - Recommended first implementation:
     - Use active state as deterministic pre-routing.
     - For normal classification, append a tiny context prefix only when it is clearly helpful:
       ```text
       Last intent: WEATHER
       Pending action: none
       Recent topic: forecast
       User: what about tomorrow?
       ```
     - Or keep Chroma prompt-only for now and rely on pre-routing plus Stage 2/Stage 3. Document the chosen tradeoff.

8. **Update Stage 2 writes**
   - Replace or extend `_persist_stage2_to_fifo()` in `pipeline.py`.
   - Persist structured fields when Stage 2 succeeds:
     - `intent`: `state["cls"]` or raw classifier class if available.
     - `confidence`: `state["conf"]`.
     - `stage`: `stage2`.
     - `entities`: handler-provided structured metadata if available.
     - `tool_results` / `client_tools` when emitted.
     - `pending_action` when a handler asks a follow-up or awaits confirmation.
   - If handler results do not currently expose entities/pending actions, add optional fields to the handler result contract without breaking existing handlers.

9. **Update Stage 3 writes**
   - Ensure Stage 3-completed turns also write structured FIFO records.
   - At minimum store:
     - `stage: stage3`
     - `intent: state["cls"]` or `others`
     - `summary`
     - `user_text`
     - `assistant_text`
   - If Stage 3 sends tool calls or creates a pending action, capture those if available.

10. **Render structured context into Stage 3**
    - Before Stage 3 escalation, include a compact rendered context block when useful.
    - Avoid raw verbose JSON.
    - Example:
      ```text
      [CURRENT CONVERSATION STATE]
      - Last intent: SEND_MESSAGE.
      - Pending action: awaiting confirmation to send SMS to Kathia.
      - Draft message: "I love you".
      - User may confirm, revise, or cancel.
      [END CURRENT CONVERSATION STATE]
      ```

11. **Add tests**
    - Unit tests for structured FIFO compatibility:
      - old prose-only records still returned by `get_recent()`
      - structured records round-trip
      - expired pending actions ignored
      - active state picks newest unresolved pending action
    - Pipeline tests or targeted scripts for:
      - pending SMS + `yes` routes to confirmation resolver
      - pending SMS + `cancel that` cancels
      - weather topic + `what about tomorrow` routes correctly or escalates with context
      - no active state + `yes` does not execute side effects

12. **Do not restart the server automatically**
    - Per runtime rules, do not restart `jane-web.service` unless Chieh explicitly asks or there are 10+ file changes.
    - Build-only tasks never trigger restart.

## Verification

Run focused checks first:

```bash
cd /home/chieh/ambient/vessence
/home/chieh/google-adk-env/adk-venv/bin/python -m pytest test_code -k "recent_turns or fifo or stage1 or stage2"
```

If no matching tests exist, add focused tests and run them directly.

Manual behavioral checks should cover:

1. Fresh prompt still routes normally:
   ```text
   "what's the weather"
   ```

2. Contextless short prompt does not trigger side effects:
   ```text
   "yes"
   ```

3. Pending SMS confirmation works:
   ```text
   User: tell Kathia I love her
   Jane: Send "I love you" to Kathia?
   User: yes
   Expected: resolver understands confirmation from structured state.
   ```

4. Pending SMS cancellation works:
   ```text
   User: cancel that
   Expected: pending action canceled, no SMS sent.
   ```

5. Topic continuation improves:
   ```text
   User: what's the weather today?
   Jane: ...
   User: what about tomorrow?
   Expected: weather continuation is handled or escalated with clear structured context.
   ```

6. Stage 3 receives readable state context, not noisy raw JSON.

## Files Involved

Likely modified:

- `vault_web/recent_turns.py`
- `jane_web/jane_v2/recent_context.py`
- `jane_web/jane_v2/pipeline.py`
- `jane_web/jane_v2/stage1_classifier.py`
- `jane_web/jane_v2/stage2_dispatcher.py`
- Selected Stage 2 handlers that can emit structured metadata:
  - `jane_web/jane_v2/classes/send_message/handler.py`
  - potentially `weather`, `music play`, `get_time`, `shopping_list`, `read_messages`, `read_email`

Maybe modified:

- `intent_classifier/v2/classifier.py`
- `jane_web/jane_v2/stage3_escalate.py`
- tests under `test_code/`

Must inspect before editing:

- `agent_skills/conversation_manager.py`
- any existing tests around `vault_web.recent_turns`

## Notes And Gotchas

- Do not make Stage 1 infer critical state from prose if the state is already known.
- Do not blindly concatenate large JSON into Chroma embedding input; that may make nearest-neighbor routing worse.
- Keep `get_recent()` backward compatible because other code may expect a list of summary strings.
- Structured FIFO should be additive and migration-safe.
- Pending side-effectful actions need explicit confirmation and expiration.
- For ambiguous revisions like "actually make it nicer", Stage 3 is safer unless there is a narrow deterministic resolver.
- Existing Stage 1 examples include continuation-like phrases for `SEND_MESSAGE`, but that is not a substitute for structured session state.
- The current conservative fallback behavior is safer than aggressive context routing. Preserve safety: if state is unclear, escalate.
