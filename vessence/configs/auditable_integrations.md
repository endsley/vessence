# Auditable Integration Contracts

The nightly code auditor reads modules in isolation, so it doesn't catch
**cross-stack contract bugs** — payloads that pass single-module unit
tests but break the system because two layers expect different shapes.

These bugs have all been seen in production:
- Pipeline emits `client_tools` field on `done` event, but Android only
  listens for `client_tool_call` events → tool never fires
- Stage 2 returns `text=""` with a tool call, Android renders empty
  bubble that looks stuck on "Classifying…"
- Tool returns `ToolActionStatus.Completed`, Android auto-replays the
  result as a new chat turn, server tells user the same thing twice

This file lists invariants the auditor MUST verify whenever it touches
a module that participates in one of these contracts.

---

## Contract 1: Stage 2 handler → Android client tool dispatch

**Producer:** `jane_web/jane_v2/classes/<name>/handler.py`
**Consumer:** `android/app/src/main/java/com/vessences/android/tools/ClientToolDispatcher.kt`

**Invariants:**
- If the handler's `result["client_tools"]` is non-empty, the pipeline
  MUST emit one `client_tool_call` NDJSON event per tool — not just
  attach them to the `done` event. Android's `NdjsonParser` reads
  events line-by-line and only fires the dispatcher on the
  `client_tool_call` event type.
- The `data` field of `client_tool_call` MUST be a JSON **string**, not
  a nested object. Android's `NdjsonParser` calls `asString` on it.
  Nested object → `asString` returns null → silent drop.
- Every tool name emitted MUST exist as a registered handler in
  `ClientToolDispatcher.kt` (or as a registered alias). If not, Android
  reports `Failed("unsupported on this client")` and the SMS/action
  silently fails.

**How to test:**
- For each handler, simulate a successful `handle()` return and verify
  the streaming output contains `{"type":"client_tool_call", ...}` for
  every entry in `client_tools`.
- Compare the set of `tool` names the pipeline can emit vs. the set
  registered in `ClientToolDispatcher.kt` — they should match.

---

## Contract 2: Empty-text + tool call must not look stuck

**Producer:** any Stage 2 handler that returns `{"text": "", "client_tools": [...]}`
**Consumer:** Android chat bubble renderer

**Invariant:** If `text` is empty and there's no follow-up text, the chat
bubble looks stuck on "Classifying…". Either:
- Return short fallback text (e.g. `"Let me check your phone's clock."`)
- OR ensure the tool call results in immediate audible/visible feedback
  AND the Android client suppresses the empty bubble

**How to test:**
- For each handler, if `text` field can be empty, verify either a
  fallback text exists OR the registered Android handler produces
  observable output (TTS speak, intent launch, etc).

---

## Contract 3: Fire-and-forget tools don't trigger auto-follow-up

**Producer:** Stage 2 handler emitting a tool call
**Consumer:** `ChatViewModel.kt` → `FIRE_AND_FORGET` set

**Bug pattern:** Android executes a tool, captures its `Completed(message)`
status, then auto-sends a follow-up message containing
`[TOOL_RESULT:{json}]` so Jane can analyze the tool's output.
For action tools (send SMS, sync messages, speak time), there's nothing
to analyze — the action is complete. Auto-follow-up causes Jane to
respond redundantly (e.g. tells the time twice, says "msg sent" twice).

**Invariant:** Every action tool (no data return value Jane needs to
reason about) MUST be in the `FIRE_AND_FORGET` set in
`ChatViewModel.kt`.

**Currently in FIRE_AND_FORGET:**
- `contacts.sms_send_direct`
- `contacts.sms_send`
- `contacts.sms_draft`
- `contacts.sms_cancel`
- `sync.force_sms`
- `device.speak_time`

**Currently NOT in FIRE_AND_FORGET (data fetchers, follow-up needed):**
- `messages.fetch_unread` (returns SMS data for Jane to summarize)
- `email.fetch_unread` (similar)

**How to test:**
- For each tool name a handler can emit, classify it as
  `action` (fire-and-forget) vs `data_fetch` (returns data for analysis).
  Verify the `action` set matches `FIRE_AND_FORGET` in `ChatViewModel.kt`.

---

## Contract 4: Stream event types Android understands

**Producer:** `jane_web/jane_v2/pipeline.py` and `jane_web/jane_proxy.py`
**Consumer:** `ChatViewModel.kt` → `event.type` switch

**Allowed event types (must match the Kotlin switch statement):**
- `status` — interim progress text
- `start` — Stage 3 began
- `model` — which model is responding
- `ack` — quick acknowledgment text (spoken via TTS)
- `thought` — chain-of-thought summary
- `tool_use` — tool invocation log line
- `delta` — incremental response text
- `client_tool_call` — fire a phone-side tool
- `tool_result` — server-side tool result
- `done` — final response, terminates the stream
- `error` / `provider_error` — error states
- `heartbeat` — keepalive (no UI effect)
- `conversation_end` — server signals to stop auto-listening

**Invariant:** No event type emitted by the pipeline that isn't in this
list. New event types require updating the Kotlin switch first.

**How to test:**
- Static scan: grep all `_ndjson("…", …)` calls in pipeline.py /
  jane_proxy.py, collect the event types, verify each is in the Kotlin
  switch.

---

## Contract 5: Stage routing decisions

**Producer:** `jane_web/jane_v2/stage1_classifier.py`
**Consumer:** `jane_web/jane_v2/pipeline.py`

**Invariants:**
- Returned class names MUST exist as keys in the pipeline's class
  registry (see `jane_web/jane_v2/classes/__init__.py`). A class name
  that's not in the registry causes Stage 2 to silently fall through
  to Stage 3.
- The "others" class MUST always have confidence "Low" — it's the
  catch-all fallback. Returning "others:High" is a logical
  contradiction and causes the pipeline to dispatch a non-existent
  handler.
- Destructive classes (`end conversation`) MUST require strict
  confidence (≥ 0.80, not just "High") because they short-circuit
  with no LLM second opinion.

**How to test:**
- For every value in `_CLASS_MAP`, verify a corresponding class pack
  directory exists.
- Generate 50 ambiguous prompts; verify "end conversation" doesn't
  fire on any of them.
- Verify "others" never returns confidence other than "Low".

---

## How the auditor uses this file

When the nightly code auditor's target module appears in the **Producer**
column of any contract, the test-generation prompt MUST include the
invariants from that contract. The auditor reads this file at runtime
and prepends the matching contracts to the test prompt, so Opus knows
to write integration-aware tests in addition to unit tests.

If a new cross-stack contract is discovered (a bug that single-module
testing missed), add it here so future audits catch the same class of
issue.
