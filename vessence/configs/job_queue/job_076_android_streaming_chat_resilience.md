---
Title: Android streaming-chat resilience (retry + idempotency + network-awareness)
Priority: 1
Status: pending
Created: 2026-04-19
Supersedes: job_073_chat_error_networkexception.md, job_075_chat_error_transientservererror.md
Reviewed-by: gemini (2026-04-19) — see "Review fixes applied" below
---

## Problem

Two separate Android error-hook jobs describe the same underlying gap in the
streaming chat client: `ChatRepository.streamChat` has no retry, no
idempotency, no network-state awareness, and the only recovery path is a
fragile UI-layer string match that tells the user to repeat themselves.

- **Job 073** (2026-04-19 13:11 UTC):
  `NetworkException: Unable to resolve host "jane.vessences.com"` during a
  real outage while `jane-web` was down. User got a raw error toast.
- **Job 075** (2026-04-19 16:02 UTC):
  `TransientServerError: Jane is restarting, please try again in a moment`
  during a graceful restart. User heard "I'm back, let me try that again"
  but had to speak the turn again — no auto-replay.

Both surface in `ChatRepository.streamChat()` (see file paths below). A
unified retry + idempotency layer closes both.

## Current code (read before editing)

- `android/app/src/main/java/com/vessences/android/data/repository/ChatRepository.kt:95-132`
  - `streamChat()` — raw OkHttp POST. Throws `NetworkException` on IOException
    (line 114), `TransientServerError` on 502/503/504 (line 126). No retry.
- `android/app/src/main/java/com/vessences/android/data/model/AppExceptions.kt:11,16`
  - Exception classes that need to be reorganized.
- `android/app/src/main/java/com/vessences/android/ui/chat/ChatViewModel.kt:522,908-950`
  - Caller; string-matches "restarting"/"unavailable"/"busy" in the error
    event's `data` field; waits 30s then speaks "I'm back" without replaying
    the turn.
- `jane_web/main.py` — server entry; confirm whether `GET /healthz` already
  exists (referenced in the graceful_restart script's warm-up step).
- `jane_web/jane_proxy.py` and `jane_web/jane_v3/pipeline.py` — server dispatch
  sites where idempotency dedupe must be injected (before the LLM call, not
  after).

## Design

Based on production patterns from Signal-Android, Now-in-Android,
openai-kotlin (Aallam), and ai-chat-android (skydoves). See "Research
summary" at bottom.

### 1. Idempotency layer — PERSISTENT dedupe (fixed per review)

- `ChatViewModel` generates `turnId = UUID.randomUUID()` once per user voice
  turn (before the first `streamChat()` call). Same value reused across
  retries of the SAME turn.
- Client sends it as `X-Request-ID: <uuid>` header.
- Server-side dedupe table lives in **`$VAULT_HOME/conversation_history_ledger.db`**
  (the same SQLite file already used for the transcript ledger). New table:

  ```sql
  CREATE TABLE IF NOT EXISTS turn_dedupe (
      turn_id       TEXT PRIMARY KEY,
      session_id    TEXT,
      status        TEXT CHECK(status IN ('pending','completed','failed')),
      response_json TEXT,                      -- final NDJSON concatenated
      created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
      completed_at  DATETIME
  );
  CREATE INDEX idx_turn_dedupe_created ON turn_dedupe(created_at);
  ```

- Dedupe window: **300s (5 min)**. Row older than that is treated as absent.
- Flow on `POST /api/jane/chat/stream` with `X-Request-ID`:
  - No row: INSERT `{turn_id, status='pending'}`, run normally, on done UPDATE
    `status='completed', response_json=<stream dump>`.
  - Row status='pending' (in-flight retry): stream back from the in-memory
    broadcaster (existing `StreamBroadcaster` in `jane_web/broadcast.py` —
    one broadcaster per turn_id; if not found, wait up to 5s then treat as
    completed).
  - Row status='completed': replay the cached `response_json` as an NDJSON
    stream without invoking the brain.
  - Row status='failed': allow re-dispatch (treat as new turn).
- Janitor: nightly prune of rows older than 24 h.

**Why persistent (not in-memory):** The primary trigger for retries is a
server restart, which wipes an in-memory cache. An in-memory dedupe actually
INCREASES double-send risk during restarts (gemini review flag).

### 2. Retry with backoff (client)

- Wrap the `streamChat()` Flow with `.retryWhen { cause, attempt -> ... }`.
  Max **2 retries** (3 total attempts).
- Backoff: 500 ms → 2000 ms, +20 % jitter.
- **Retry conditions (AND-gated):**
  - `cause is TransientError` (see taxonomy below)
  - AND `!hasEmittedAnyEvent` (see §4)
  - AND one of:
    - `cause is NetworkException` and `NetworkMonitor.isOnline` just flipped
      false → true since the call started; OR
    - `cause is TransientServerError` and `GET /healthz` returns 200 within
      2 s.

### 3. Network-state awareness

- New class `NetworkMonitor` in `android/.../util/NetworkMonitor.kt`, modeled
  on Now-in-Android's `ConnectivityManagerNetworkMonitor.kt`.
  - `isOnline: StateFlow<Boolean>` fed by `ConnectivityManager.NetworkCallback`.
- On entering `streamChat()`:
  - If offline: throw `OfflineError` immediately; ChatViewModel shows canned
    TTS "You're offline — I'll try once we're back", suspends the send,
    collects `NetworkMonitor.isOnline.filter { it }.first()`, then retries
    exactly once.
- On `UnknownHostException` mid-call (gemini fix):
  - If `NetworkMonitor` observed a network-type transition during the call
    (e.g. MOBILE → WIFI), treat as transient and retry.
  - Otherwise: surface as `FatalError` (DNS is persistently broken). Don't
    eat 30 s of voice wait on a device in airplane mode.

### 4. Safe-retry gate (voice-turn hazard)

- Track `hasEmittedAnyEvent: Boolean` in the Flow collector — flips true on
  ANY of: `delta`, `client_tool_call`, `model`, `done` events.
- **Only retry if `!hasEmittedAnyEvent`.** (gemini review: original draft
  said "zero assistant bytes" but the server may emit a `client_tool_call`
  before any text — SMS already sent.)
- Once any event has been collected, treat the turn as committed. Show
  what we have, surface error; do NOT retry.

### 5. Server-side dedupe states (gemini refinement)

Dedupe is not just "seen / not seen" but a 3-state machine:
- `pending` → new retry joins the existing `StreamBroadcaster` for this
  turn_id; both clients receive the same stream. If no broadcaster exists
  (process restart mid-turn), mark row as `failed` and permit re-dispatch.
- `completed` → replay cached `response_json` as NDJSON, no brain call.
- `failed` → treat as new turn.

### 6. Exception taxonomy (replace `AppExceptions.kt`)

- `TransientError(cause: Throwable?)` — retry-safe:
  - HTTP 408, 425, 429, 500, 502, 503, 504
  - `SocketTimeoutException`, `ConnectException`
  - `UnknownHostException` IF a network-type transition occurred
- `FatalError(message: String)` — do-not-retry:
  - HTTP 400, 401, 403, 404, 409, 422
  - JSON parse errors, unexpected protocol
  - `UnknownHostException` with no network transition
- `OfflineError` — wait-for-network:
  - Raised when `NetworkMonitor.isOnline` is false at call time.

`ChatViewModel` error handler switches on class instead of string-matching.

### 7. OkHttp lifecycle (gemini review)

- Hold the `okhttp3.Call` reference in the Flow's coroutine scope.
- On `viewModelScope` cancellation or retry-initiated abort, explicitly call
  `call.cancel()` before opening the next one. Prevents socket leak across
  retries during real restarts.

### 8. Health endpoint

- Verify `GET /healthz` exists in `jane_web/main.py`. The graceful_restart
  script already polls it, so it likely does — but the response format may
  not match what the client expects.
- Desired shape: `{"status": "warm" | "cold", "brain_model": "<string>"}`.
  If missing, add it (one-liner FastAPI route).

## Verification

1. **Unit (Android)** — in `android/app/src/test/java/.../ChatRepositoryTest.kt`:
   - Mock OkHttp returns 502 twice then 200 → assert 3 POSTs, same
     `X-Request-ID` on each.
   - Mock `UnknownHostException` with no network transition → no retry,
     `FatalError` raised.
   - Mock `UnknownHostException` after `NetworkMonitor` flips → 1 retry.
   - Mock stream emits `client_tool_call` then IOException →
     NO retry (gate fires on first event).

2. **Integration (server)** — `jane_web/tests/test_turn_dedupe.py`:
   - POST same `X-Request-ID` twice in <5 min while first is in-flight →
     second receives the same NDJSON stream, no double LLM dispatch.
   - POST same `X-Request-ID` twice after first completed → second replays
     cached response.
   - POST same `X-Request-ID` after 300 s → treated as new.

3. **Manual** (requires Android build + installed APK):
   - Issue a voice turn, then immediately run
     `bash $VESSENCE_HOME/startup_code/graceful_restart.sh` during the
     user-is-speaking window. Assert: user gets Jane's reply without being
     asked to repeat.
   - Voice "tell Sarah I'm on my way" during the same restart. Assert Sarah
     receives **exactly one** SMS (check Android SMS log + server logs for
     duplicate `sms.send` tool calls).
   - Toggle airplane mode mid-turn. Assert: canned "you're offline" plays,
     app doesn't hang; turning airplane mode off triggers one replay.

## Files to edit (checklist for next session)

- [ ] `android/.../data/repository/ChatRepository.kt` — wrap Flow, add Call lifecycle.
- [ ] `android/.../data/model/AppExceptions.kt` — new taxonomy.
- [ ] `android/.../util/NetworkMonitor.kt` — NEW file.
- [ ] `android/.../ui/chat/ChatViewModel.kt:522,908-950` — stop string matching; switch on exception class; generate `turnId` once per user turn.
- [ ] `jane_web/jane_proxy.py` or a new `jane_web/turn_dedupe.py` — SQLite dedupe before brain dispatch.
- [ ] `jane_web/main.py` — verify/add `GET /healthz`; accept `X-Request-ID` header.
- [ ] `jane_web/broadcast.py` — check StreamBroadcaster can be keyed by `turn_id` for join-in-flight.
- [ ] `jane_web/tests/test_turn_dedupe.py` — NEW tests.
- [ ] `android/.../test/ChatRepositoryTest.kt` — NEW unit tests.
- [ ] `agent_skills/janitor_memory.py` or `janitor_system.py` — prune dedupe table older than 24 h.
- [ ] Bump Android version via `startup_code/bump_android_version.py`.

## Review fixes applied (from Gemini panel, 2026-04-19)

1. Dedupe cache must be **persistent** (SQLite), not in-memory — restart wipes
   in-memory and causes the exact double-send this spec aims to prevent.
2. Retry gate is "**no events collected**", not "no assistant bytes" — a
   `client_tool_call` event can fire an SMS before any text.
3. `UnknownHostException` is **not** always transient — retry only on network
   transition; otherwise surface as FatalError.
4. Dedupe window increased from 60 s → **300 s** to cover slow LLM turns +
   client-side 30 s recovery delay.
5. Added 3-state dedupe (`pending` / `completed` / `failed`) and a
   join-in-flight mechanism so two concurrent retries don't both invoke the
   brain.
6. Explicit OkHttp `Call.cancel()` in retry path to avoid socket leak.

## Research summary (for cold-start context)

Referenced patterns (OSS production codebases):
- **Signal-Android** (`core-util-jvm/.../WebSocketHealthMonitor`, `NetworkConstraint`): exception taxonomy, 3-attempt budget, health probe.
- **Now-in-Android** (`core/network/.../ConnectivityManagerNetworkMonitor.kt`): `NetworkCallback` + `StateFlow<Boolean>` pattern.
- **openai-kotlin** (Aallam): `.retryWhen { cause, attempt -> ... }` in `StreamingRequests.kt`, backoff constants.
- **ai-chat-android** (skydoves): health-probe-before-retry, Flow teardown.
- **Stripe API docs**: `Idempotency-Key` semantics, 24 h window; we adopt 5 min (voice turns are short-lived).

Key "don't bother" signals:
- OkHttp's built-in `retryOnConnectionFailure(true)` is TCP-level only; doesn't cover HTTP 5xx. Needed in addition, not in place of, Flow-level retry.
- Heavy libraries (Resilience4j, kotlin-retry) are overkill for a single endpoint.
- Circuit breaker is overkill for one dependency — a bounded retry budget is sufficient.

## Out of scope

- Stream-resumption after partial NDJSON (too complex; accept loss of partial output, surface error).
- Full circuit breaker.
- Background queuing of failed turns across app-kill.
