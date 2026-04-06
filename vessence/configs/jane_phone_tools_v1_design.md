# Jane Phone Tools v1 — Design Spec

**Status:** draft, pending review
**Author:** Jane (Claude Opus 4.6) at Chieh's direction
**Date:** 2026-04-05
**Target platform:** Android only (no web counterpart in v1)

---

## 1. Goal

Give Jane three new capabilities that run on Chieh's Android phone:

1. **Call a contact by name** — voice-triggered phone call with a 10-second verbal cancel window.
2. **Text a contact** — multi-turn back-and-forth SMS draft loop where Jane reads the message back, Chieh edits it verbally, and approves before sending.
3. **Read recent messages aloud** — Jane reads the latest messaging-category notifications (SMS, WhatsApp, Signal, iMessage relay, etc.) via on-device TTS.

All capabilities are phone-only in v1. The web Jane UI does not reflect them. There is no Android → server round-trip for any v1 feature — all state lives either on the device (operational state) or in Jane's conversation turn history (semantic state).

---

## 2. Architecture boundaries

| Layer | Role | Language |
|---|---|---|
| **Jane's mind** (Opus standing brain) | Decides *when* to invoke a tool, composes message bodies from indirect requests ("ask my wife when she's coming back" → "Hey, when are you coming back?"), runs the SMS draft state machine across turns | Prompt-instructed only, no code |
| **Server bridge** (`jane_web/jane_proxy.py`) | Extracts `[[CLIENT_TOOL:…]]` markers from Jane's streaming output, emits structured SSE events, strips markers from the user-visible stream, bypasses the Gemma initial-ack layer when an SMS draft is open | Python |
| **Wire protocol** | One new SSE event type `client_tool_call` carrying a structured JSON payload `{tool, args, call_id}` | JSON-over-NDJSON |
| **Android dispatcher** | Parses the structured event, dedupes by `call_id`, dispatches to the right handler | Kotlin |
| **Android handlers** | Execute the actual phone capability (contacts resolution, dial, SMS send, notification read, TTS) | Kotlin |
| **Notification listener service** | Runs continuously on Android, buffers recent messaging-category notifications in memory (parsed from `MessagingStyle`) | Kotlin |
| **MCP descriptor** | Declarative tool catalog (one JSON file) so Gemma's "what can you do with phone" shortcut works and Jane's mind can be told about the tools in a structured way | JSON |

---

## 3. MCP descriptor

**File:** `tools/phone/mcp.json` (new, following the schema used by `jane_web/gemma_router.py::_load_all_mcps()`).

```json
{
  "name": "phone",
  "description": "Jane's access to the user's phone capabilities: contacts, phone calls, SMS drafting and sending, reading recent messaging notifications. All actions run on the Android device and are gated by on-device confirmation. The server never holds contact data.",
  "platform": "android_only",
  "commands": [
    {
      "name": "contacts.call",
      "description": "Initiate a phone call to a contact, resolved locally by name. A 10-second verbal countdown gives the user a chance to cancel before the call is placed.",
      "args_schema": {
        "query": {"type": "string", "required": true, "description": "The contact's name as the user referred to them (e.g., 'spouse', 'mom', 'Dr. Chen'). Android resolves this locally."}
      },
      "emit_format": "[[CLIENT_TOOL:contacts.call:{\"query\":\"<name>\"}]]",
      "examples": [
        {"input": "call spouse", "emit": "[[CLIENT_TOOL:contacts.call:{\"query\":\"spouse\"}]]"},
        {"input": "dial my wife", "emit": "[[CLIENT_TOOL:contacts.call:{\"query\":\"spouse\"}]]", "note": "resolved via memory: wife → spouse"},
        {"input": "get mom on the phone", "emit": "[[CLIENT_TOOL:contacts.call:{\"query\":\"mom\"}]]"}
      ]
    },
    {
      "name": "contacts.sms_draft",
      "description": "Open a new SMS draft to a contact. Does NOT send. Android reads the body back and waits for approval / edit / cancel. Use for any texting intent: direct ('text X'), indirect ('ask X'), or relational ('my wife').",
      "args_schema": {
        "query": {"type": "string", "required": true},
        "body": {"type": "string", "required": true, "description": "Full message body composed by Jane. For indirect requests, Jane writes the natural text — the user gave intent, not words."}
      },
      "emit_format": "[[CLIENT_TOOL:contacts.sms_draft:{\"query\":\"<name>\",\"body\":\"<body>\"}]]",
      "examples": [
        {"input": "text spouse I'll be home in 20", "emit": "[[CLIENT_TOOL:contacts.sms_draft:{\"query\":\"spouse\",\"body\":\"I'll be home in 20\"}]]"},
        {"input": "ask my wife when she's coming back", "emit": "[[CLIENT_TOOL:contacts.sms_draft:{\"query\":\"spouse\",\"body\":\"Hey, when are you coming back?\"}]]"},
        {"input": "let mom know I landed safely", "emit": "[[CLIENT_TOOL:contacts.sms_draft:{\"query\":\"mom\",\"body\":\"Hi mom, I landed safely.\"}]]"},
        {"input": "tell dad happy birthday", "emit": "[[CLIENT_TOOL:contacts.sms_draft:{\"query\":\"dad\",\"body\":\"Happy birthday, dad!\"}]]"}
      ]
    },
    {
      "name": "contacts.sms_draft_update",
      "description": "Rewrite the currently open SMS draft. Always the FULL new body, never a diff. Triggered when the user responds with an edit instruction instead of approval or rejection.",
      "args_schema": {
        "body": {"type": "string", "required": true}
      },
      "emit_format": "[[CLIENT_TOOL:contacts.sms_draft_update:{\"body\":\"<body>\"}]]",
      "examples": [
        {"prior_draft_body": "be home in 20", "input": "make it 30", "emit": "[[CLIENT_TOOL:contacts.sms_draft_update:{\"body\":\"be home in 30\"}]]"},
        {"prior_draft_body": "Hey, when are you coming back?", "input": "add a please", "emit": "[[CLIENT_TOOL:contacts.sms_draft_update:{\"body\":\"Hey, when are you coming back? Please.\"}]]"}
      ]
    },
    {
      "name": "contacts.sms_send",
      "description": "Commit the currently open SMS draft. Android sends via SmsManager.",
      "args_schema": {},
      "emit_format": "[[CLIENT_TOOL:contacts.sms_send:{}]]",
      "examples": [
        {"input": "send it", "emit": "[[CLIENT_TOOL:contacts.sms_send:{}]]"},
        {"input": "perfect, send", "emit": "[[CLIENT_TOOL:contacts.sms_send:{}]]"},
        {"input": "that's good", "emit": "[[CLIENT_TOOL:contacts.sms_send:{}]]"}
      ]
    },
    {
      "name": "contacts.sms_cancel",
      "description": "Abandon the currently open SMS draft.",
      "args_schema": {},
      "emit_format": "[[CLIENT_TOOL:contacts.sms_cancel:{}]]",
      "examples": [
        {"input": "nevermind", "emit": "[[CLIENT_TOOL:contacts.sms_cancel:{}]]"},
        {"input": "cancel", "emit": "[[CLIENT_TOOL:contacts.sms_cancel:{}]]"},
        {"input": "actually call her instead", "emit_sequence": ["[[CLIENT_TOOL:contacts.sms_cancel:{}]]", "[[CLIENT_TOOL:contacts.call:{\"query\":\"spouse\"}]]"]}
      ]
    },
    {
      "name": "messages.read_recent",
      "description": "Read the last N messaging notifications aloud via on-device TTS. Uses NotificationListenerService — works for SMS, WhatsApp, Signal, iMessage relay, and any messaging app uniformly. Filters OTPs, banking alerts, and sensitive lock-screen content.",
      "args_schema": {
        "limit": {"type": "integer", "required": false, "default": 5, "max": 20}
      },
      "emit_format": "[[CLIENT_TOOL:messages.read_recent:{\"limit\":<n>}]]",
      "examples": [
        {"input": "read me my messages", "emit": "[[CLIENT_TOOL:messages.read_recent:{\"limit\":5}]]"},
        {"input": "did I get any new texts", "emit": "[[CLIENT_TOOL:messages.read_recent:{\"limit\":5}]]"},
        {"input": "read my last 10 messages", "emit": "[[CLIENT_TOOL:messages.read_recent:{\"limit\":10}]]"}
      ]
    }
  ],
  "policies": {
    "draft_lifetime_seconds": 120,
    "call_countdown_seconds": 10,
    "cancel_words": ["stop", "cancel", "no", "wait", "wait wait", "abort", "hold on", "nevermind"],
    "approval_words_examples": [
      "send", "send it", "send that", "send that one", "send away", "send it off",
      "yes", "yep", "yeah", "yup", "confirm", "confirmed",
      "go", "go ahead", "let's go", "do it", "ship it", "fire it off", "fire away",
      "hit send", "push it",
      "that's good", "that's perfect", "that's the one", "looks good", "sounds good",
      "sounds perfect", "perfect", "nailed it", "that works", "all good",
      "i'm good with that", "okay send", "alright send it"
    ]
  }
}
```

---

## 4. Server-side Python changes (`jane_web/jane_proxy.py`)

### 4.1 New class `ToolMarkerExtractor`

Per-request, stateful. Placed at module level below existing imports. Extends the existing `_accumulated_deltas` pattern at line 1187 (already used for `[/ACK]` detection), so no parallel buffer is introduced.

```python
class ToolMarkerExtractor:
    _OPEN = "[[CLIENT_TOOL:"
    _CLOSE = "]]"
    _MAX_HOLD = 2048  # safety cap

    def __init__(self) -> None:
        self._buffer: str = ""

    def feed(self, chunk: str) -> tuple[str, list[dict]]:
        """Consume delta chunk, return (safe_visible_text, complete_tool_calls)."""

    def flush(self) -> tuple[str, list[dict]]:
        """Called on stream end; reveals any residual buffer as visible text."""

    @classmethod
    def _parse_payload(cls, raw: str) -> dict | None:
        """Parse 'name:{json}' into {tool, args, call_id}. None on malformed."""

    @staticmethod
    def _longest_partial_opener_suffix(buf: str) -> int:
        """Length of the longest suffix of buf that is a prefix of _OPEN."""
```

**Parsing rules:**
- Tool name must match `^[a-z][a-z0-9_.]*$`. Malformed → drop the marker silently (visible text around it is still forwarded).
- Args must be a JSON object. Malformed JSON → drop silently.
- `call_id` is generated server-side as a UUID4; clients dedupe on it.

**Chunk boundary handling:**
- If the buffer ends with a strict prefix of `_OPEN` (e.g., "[[CLIENT"), hold that suffix back and flush the rest.
- If an opener is found but no closer yet, hold the entire opener-onwards in the buffer and flush only text before the opener.
- If buffer grows past `_MAX_HOLD` with an unclosed opener, treat as malformed — flush as visible, drop the partial marker. Prevents memory exhaustion on a runaway model.

### 4.2 New helper `_has_open_sms_draft(history, max_age_seconds=120)`

```python
def _has_open_sms_draft(history: list[dict], max_age_seconds: int = 120) -> bool:
    """Scan the LAST assistant turn in history. Return True if it contains
    contacts.sms_draft or contacts.sms_draft_update and no subsequent
    contacts.sms_send / contacts.sms_cancel within that same turn, and the
    turn is within max_age_seconds."""
```

Uses regex on `state.history[-1]["content"]`. No separate session table, no new state. The source of truth is that `final_response` (persisted to history) contains raw text *with* markers intact — the extractor strips only for client visibility.

### 4.3 Edit to `emit()` wrapper (lines 1199–1208)

```python
def emit(event_type: str, payload: str | None = None) -> None:
    nonlocal _ack_seen, _accumulated_deltas
    if event_type == "delta" and payload:
        _accumulated_deltas += payload                  # existing — for /ACK + history
        if not _ack_seen and "[/ACK]" in _accumulated_deltas:
            _ack_seen = True
        visible, tool_calls = _tool_extractor.feed(payload)
        for tc in tool_calls:
            _raw_emit("client_tool_call", json.dumps(tc, ensure_ascii=True))
        if visible:
            _raw_emit("delta", visible)
        return
    if event_type == "done":
        visible_tail, tail_calls = _tool_extractor.flush()
        for tc in tail_calls:
            _raw_emit("client_tool_call", json.dumps(tc, ensure_ascii=True))
        if visible_tail:
            _raw_emit("delta", visible_tail)
    _raw_emit(event_type, payload)
```

### 4.4 Edit near line 1214 — skip initial ack when draft is open

```python
_skip_initial_ack = _has_open_sms_draft(state.history)
if _skip_initial_ack:
    logger.info("[%s] SMS draft open — skipping initial ack, routing to mind",
                session_id[:12])

if not _skip_initial_ack:
    try:
        from jane_web.gemma_router import classify_prompt, ROUTER_MODEL
        ...  # existing router code unchanged
```

### 4.5 Per-request state near line 1187

```python
_accumulated_deltas = ""
_tool_extractor = ToolMarkerExtractor()  # NEW
```

**Total jane_proxy.py footprint:** ~90 lines added, 0 removed.

---

## 5. Standing-brain prompt addition

Added to whichever file currently holds Jane's main system prompt (TBD during phase 1 discovery — likely in `jane/` or injected via `context_builder.py`). ~180 lines. Covers:

1. Marker emit format.
2. `contacts.call` — when to emit, phrasings, response text guidance.
3. SMS draft protocol — the 4-marker state machine (draft → update → send/cancel).
4. How to recognize direct vs indirect vs relational texting intent.
5. How to compose bodies from indirect requests.
6. How to recognize approval / rejection / edit / topic-switch in turn N+1.
7. `messages.read_recent` — phrasings.
8. Safety rules:
   - Never emit a marker on ambiguity (ask instead).
   - Never include sensitive data in SMS body unless dictated verbatim.
   - Never cite marker syntax in user-visible prose or code blocks.
   - Only emit markers in the live assistant turn, not in quoted user content.

The full prompt text is in §3.1–3.9 of the previous design message and will be transcribed into the target file during implementation.

---

## 6. Android Kotlin file layout

All paths relative to `android/app/src/main/java/com/vessences/android/`.

### 6.1 New files (11)

| File | Role | LoC est. |
|---|---|---|
| `tools/ClientToolCall.kt` | `@Serializable` data class + `ToolActionStatus` sealed class | ~40 |
| `tools/ClientToolHandler.kt` | Interface contract | ~25 |
| `tools/ClientToolDispatcher.kt` | Singleton registry + `call_id` dedupe + coroutine scope | ~120 |
| `tools/ActionQueue.kt` | Mutex-serialized TTS + intent launcher | ~60 |
| `tools/ContactsCallHandler.kt` | 10s countdown + STT cancel listener + ACTION_CALL | ~130 |
| `tools/ContactsSmsHandler.kt` | All four SMS sub-tools, single shared pending slot | ~180 |
| `tools/MessagesReadRecentHandler.kt` | Buffer walker + OTP filter + TTS | ~80 |
| `tools/DraftPreviewState.kt` | Compose `StateFlow` for the on-screen draft bubble (STT-fallback tap) | ~25 |
| `contacts/ContactsResolver.kt` | Shared `ContactsContract` query, `Dispatchers.IO`-gated | ~90 |
| `notifications/VessenceNotificationListener.kt` | `NotificationListenerService` + `MessagingStyle` parser | ~90 |
| `notifications/RecentMessagesBuffer.kt` | Bounded in-memory ring buffer (20 entries) | ~30 |

**Total new LoC: ~870**

### 6.2 Edited files (3)

| File | Change | LoC |
|---|---|---|
| `ui/chat/ChatViewModel.kt` | One `when` arm: `"client_tool_call" -> ClientToolDispatcher.dispatchRaw(event.data, context)` | ~8 |
| `AndroidManifest.xml` | 3 `<uses-permission>` + `<service>` declaration | ~15 |
| First-launch permission flow file (TBD) | Request READ_CONTACTS, CALL_PHONE, SEND_SMS + notification-listener settings deep-link | ~40 |

### 6.3 Key signatures

```kotlin
// tools/ClientToolCall.kt
@Serializable
data class ClientToolCall(val tool: String, val args: JsonObject, val call_id: String)

sealed class ToolActionStatus {
    object Requested : ToolActionStatus()
    object Validated : ToolActionStatus()
    data class Running(val message: String) : ToolActionStatus()
    data class Completed(val message: String) : ToolActionStatus()
    data class Failed(val reason: String) : ToolActionStatus()
    object Cancelled : ToolActionStatus()
    data class NeedsUser(val prompt: String) : ToolActionStatus()
}

// tools/ClientToolHandler.kt
interface ClientToolHandler {
    val name: String
    suspend fun handle(call: ClientToolCall, ctx: Context, queue: ActionQueue): ToolActionStatus
}

// tools/ClientToolDispatcher.kt
object ClientToolDispatcher {
    fun register(handler: ClientToolHandler)
    fun dispatchRaw(rawJson: String, ctx: Context)
    fun dispatch(call: ClientToolCall, ctx: Context)
    val lastStatus: StateFlow<Pair<String, ToolActionStatus>?>
}

// tools/ActionQueue.kt
class ActionQueue {
    suspend fun speak(text: String)
    suspend fun startActivity(ctx: Context, intent: Intent)
    suspend fun fence()
}

// contacts/ContactsResolver.kt
object ContactsResolver {
    data class Contact(val contactId: Long, val displayName: String, val phoneNumber: String)
    suspend fun findCallable(ctx: Context, query: String): List<Contact>
    suspend fun resolveExact(ctx: Context, query: String): ResolveResult
    sealed class ResolveResult {
        data class Single(val contact: Contact) : ResolveResult()
        data class Multiple(val candidates: List<Contact>) : ResolveResult()
        object None : ResolveResult()
    }
}

// notifications/VessenceNotificationListener.kt
class VessenceNotificationListener : NotificationListenerService() {
    companion object { val connected: StateFlow<Boolean> }
    override fun onListenerConnected()
    override fun onListenerDisconnected()
    override fun onNotificationPosted(sbn: StatusBarNotification)
}

// notifications/RecentMessagesBuffer.kt
object RecentMessagesBuffer {
    data class Entry(val sender: String, val body: String, val timestamp: Long, val packageName: String)
    fun record(entry: Entry)
    fun snapshot(limit: Int): List<Entry>
    fun clear()
}
```

---

## 7. State machines

### 7.1 SMS draft loop (owned by Jane's mind)

```
        (no draft)
            │
  user: "text X ..."
            │
            ▼
   emit: sms_draft{X, body}
            │
            ▼
      ┌─ (draft open) ─┐
      │                │
  user turn            │ (2min expiry)
      │                │
   ┌──┴──┬──────┬──────┴──────┐
   ▼     ▼      ▼             ▼
 APPROVE EDIT  REJECT      TOPIC SWITCH
   │     │      │             │
 sms_send│    sms_cancel    sms_cancel
   │     │      │           + new tool
   │     │      │             │
   ▼     ▼      ▼             ▼
 (closed) │  (closed)    (closed + new intent)
          │
          ▼
      sms_draft_update{new body}
          │
          └── (still draft open, loop)
```

### 7.2 Call countdown (owned by Android handler)

```
   emit: contacts.call{query}
           │
           ▼
     resolve contact
       │        │        │
     single   multi    none
       │        │        │
       ▼        ▼        ▼
   countdown  picker    speak
     start   (future)   "not found"
       │
       ▼
   TTS: "Calling X in 10 seconds..."
   start STT cancel listener
       │
   tick every 2s (TTS: 8,6,4,2)
       │
   ┌───┴────┐
   ▼        ▼
 cancel   timeout
 heard     reached
   │        │
 abort    ACTION_CALL
 speak    dial
 "cancel"
```

---

## 8. Permissions (new)

| Permission | Used by | When requested |
|---|---|---|
| `READ_CONTACTS` | `ContactsResolver` | First launch (batched prompt) |
| `CALL_PHONE` | `ContactsCallHandler` | First launch |
| `SEND_SMS` | `ContactsSmsHandler` (commit path) | First launch |
| `BIND_NOTIFICATION_LISTENER_SERVICE` | `VessenceNotificationListener` | First launch (system settings deep link — can't be granted programmatically) |

First-launch UX: one explanation screen describing what Jane will do with each, then sequential native prompts for runtime permissions, then a system settings deep-link for notification listener access with an in-app toggle confirming when enabled.

---

## 9. Safety rails

- **Call countdown cancel window:** 10 seconds of verbal "stop" / "cancel" / "wait" / "wait wait" / "nevermind" / "no" / "hold on" / "abort" before the dial actually fires.
- **SMS approval required:** every draft goes through the read-back loop; no first-pass direct sends. Jane's mind is explicitly instructed never to emit `sms_send` without a prior `sms_draft` in the same turn sequence.
- **Draft auto-expiry:** 120 seconds of idle closes the draft; a subsequent "send it" becomes a no-op with an explanation TTS.
- **STT-fallback tap:** the on-screen draft preview bubble has a visible Send button so a broken STT doesn't trap an approved message.
- **OTP redaction:** `messages.read_recent` skips any notification whose body matches an OTP-shape regex (4-8 digit codes, "verification code", "passcode").
- **Lock-screen sensitive-content check:** when the phone is locked, only `Notification.VISIBILITY_PUBLIC` notifications are read.
- **Body length cap:** 300 chars per message when reading aloud.
- **No server-side contact data:** contact resolution happens entirely on-device; the server never sees names or numbers.
- **No network upload of notification content:** the buffer is in-memory only, cleared on process kill.
- **Marker origin authentication:** `ToolMarkerExtractor` only scans the live assistant delta stream. User echoes, quoted text, and code-block content (detected by fenced triple-backticks) are not scanned.
- **`call_id` dedupe on SSE reconnect:** the Android dispatcher dedupes on `call_id` within a 60-second window to prevent replay from triggering a second dial or second send.

---

## 10. Out of scope for v1 (deferred)

- Direct hands-free SMS auto-send without verbal confirm (v1 always loops).
- Proactive reading of incoming messages (v1 is user-pull only via `messages.read_recent`).
- Jane summarizing or triaging messages (v1 reads raw).
- Memory-aware contact disambiguation ("you usually text spouse H, not spouse R").
- On-device Compose picker for ambiguous contact names (v1 asks the user to be more specific verbally).
- AccessibilityService / UI Automator based automation of third-party messaging apps (WhatsApp, Signal, Slack).
- Android → server round-trip tool-result reporting.
- Migrating the existing `[MUSIC_PLAY:uuid]` music marker onto the new `client_tool_call` channel (music stays on its existing bracket-token pattern).
- Web Jane UI counterpart.

---

## 11. Known open questions

1. **MCP file location.** `tools/phone/mcp.json` vs `essences/phone/mcp.json`. Need to check existing MCPs to see which directory they live under.
2. **Standing-brain prompt location.** Need to trace how the Opus CLI gets its system prompt — likely via `jane/context_builder.py` or a `CLAUDE.md` in the brain's working directory. Part of phase 1 discovery.
3. **TTS entry point.** `ActionQueue.speak()` must route to the same TTS engine that `ChatViewModel` already uses (Kokoro or whatever). Need to locate the entry point.
4. **STT reuse for cancel-word listening.** Can the countdown listener tap into the existing wake-word STT pipeline, or does it spin up a fresh `SpeechRecognizer`? Shared is preferred.
5. **Permission gate file.** Where does the first-launch permission flow currently live? Need to locate to extend without duplication.

---

## 12. Implementation phases

**Phase 1 — server + MCP + prompt (no Android changes)**
1. Locate standing-brain system prompt file.
2. Add `tools/phone/mcp.json`.
3. Add `ToolMarkerExtractor` + `_has_open_sms_draft` + emit() edits + initial-ack skip to `jane_proxy.py`.
4. Append tool-tools prompt block to the standing-brain prompt.
5. Restart jane-web, verify no regression on existing prompts.
6. Manual test: send a synthetic prompt to Jane and observe `client_tool_call` SSE events in the network stream.
7. Report.

**Phase 2 — Android scaffolding**
1. Add `AndroidManifest.xml` permissions + service declaration.
2. Add `ClientToolCall.kt`, `ClientToolHandler.kt`, `ClientToolDispatcher.kt`, `ActionQueue.kt`.
3. Wire `ChatViewModel.kt` with the new `when` arm.
4. Extend first-launch permission flow.
5. Build APK, verify compile.
6. Report.

**Phase 3 — handlers**
1. `ContactsResolver.kt`.
2. `ContactsCallHandler.kt` + countdown state machine.
3. `ContactsSmsHandler.kt` + 4-sub-command draft state machine.
4. `DraftPreviewState.kt` + chat UI bubble.
5. Build APK, smoke test each handler with a mock tool call.
6. Report.

**Phase 4 — notification listener + read_recent**
1. `VessenceNotificationListener.kt`.
2. `RecentMessagesBuffer.kt`.
3. `MessagesReadRecentHandler.kt` + OTP filter + lock-screen check.
4. Permission deep-link UX.
5. Build APK, test with real notifications.
6. Report.

**Phase 5 — version bump + deploy**
1. Bump Android version via `bump_android_version.py`.
2. Deploy APK.
3. Restart jane-web.
4. Update `configs/Jane_architecture.md` with the new tool suite.
5. End-to-end manual test on your phone.

---

## 12a. Revisions from panel review (2026-04-05)

After Gemini and Codex review, ten locked-in design changes override the original spec. These are authoritative:

### R1. ToolMarkerExtractor — real streaming state machine, not regex

The extractor must be a proper state machine that handles:
- Tool name scanning: `[a-z][a-z0-9_.]*` until first `:` after opener.
- JSON payload scanning: brace-depth counter + string-state (inside double-quoted string, tracking `\\` escapes). Only close the marker when brace depth returns to 0 AND we are outside a string AND the literal `]]` follows immediately.
- Code fence state persisted across chunks: inside a ```` ``` ```` block (with language tag support), no marker scanning at all.
- Fail-open on: unclosed marker exceeding `_MAX_HOLD` (2048 chars), malformed tool name, malformed JSON. In all three cases the marker is treated as visible text, not executed.

### R2. Android → server tool result feedback channel

Implemented as a magic prefix on the *next* user turn. Android inserts one or more `[TOOL_RESULT:{json}]` markers at the start of the next outgoing user message. `jane_proxy.py`:
- Extracts markers from the head of the user turn before showing the user bubble in the UI.
- Passes the parsed results to Jane's mind as part of her context for the next turn (either injected into her system prompt as "Recent tool results:" or prepended to the user turn content in her view only).
- No new endpoint, no new protocol — reuses existing user-turn pipeline.

New helper in `jane_proxy.py`:
```python
def _extract_tool_results(user_message: str) -> tuple[str, list[dict]]:
    """Strip leading [TOOL_RESULT:{json}] markers; return (clean_text, results)."""
```

Android side: when any handler terminates with `Completed`, `Failed`, `Cancelled`, or `NeedsUser`, it writes a `ToolResult` entry to a module-level `PendingToolResultBuffer`. The chat composer's outgoing-message builder drains this buffer into the prefix before sending.

### R3. `draft_id` and `op_id` on every mutable tool

- `contacts.sms_draft` args now include `draft_id: <uuid4>` (generated by Jane's mind).
- `contacts.sms_draft_update`, `contacts.sms_send`, `contacts.sms_cancel` all include `draft_id` and must match the currently-held slot in `ContactsSmsHandler`. Mismatch → silent drop + `Failed("stale draft_id")` reported back via R2.
- `contacts.call` includes `op_id: <uuid4>` so a subsequent cancel (if we add one later) can target the right countdown.

Jane's mind prompt is updated to always echo the `draft_id` it saw in its own previous marker when emitting update/send/cancel.

### R4. `_has_open_sms_draft` scans backwards across multiple turns

```python
def _has_open_sms_draft(history: list[dict], max_age_seconds: int = 120) -> str | None:
    """Scan backwards through the last ~6 assistant turns. Return the latest
    still-open draft_id, or None. A draft is 'open' if:
      - an sms_draft or sms_draft_update marker with that draft_id was emitted
      - no subsequent sms_send or sms_cancel with the same draft_id exists
        in any later turn
      - the emitting turn is within max_age_seconds
    """
```

Instead of a boolean, returns the draft_id so the server can log which draft is active and skip initial ack only for that specific context.

### R5. Flipped phase order — Android ships first, server last

1. **Phase 1** — Android scaffolding: manifest permissions, dispatcher interface, action queue, feature flag (default OFF). APK builds and runs with zero user-visible change. No tool emissions.
2. **Phase 2** — Android handlers: all three tool handlers + contacts resolver + draft preview state. Still flag-gated OFF.
3. **Phase 3** — Notification listener + read_recent handler. Still flag-gated OFF.
4. **Phase 4** — Server: extractor + feedback channel + draft-scan helper + prompt block + MCP file. Server side is ready, but without flag-on Android cannot receive tool calls.
5. **Phase 5** — Flip the feature flag, version bump, deploy APK, restart jane-web, end-to-end test on Chieh's phone.

This ordering guarantees no "silent Jane" window where the server emits strip-from-UI markers that no handler receives.

### R6. ActionQueue priority channel

The single `mutex` becomes two channels:
- `chatTtsMutex` — guards chat-stream TTS playback (existing behavior).
- `toolActionMutex` — guards tool-related TTS + external intents.

Tool speech *interrupts* chat TTS when `toolActionMutex` is acquired:
```kotlin
suspend fun speakTool(text: String) {
    toolActionMutex.withLock {
        JaneTtsBridge.interruptAndSpeak(text)  // stops any in-flight chat TTS first
    }
}
```

Chat TTS cannot interrupt tool TTS. Countdown TTS is always tool-priority.

### R7. Wider OTP regex in messages.read_recent

```kotlin
private val OTP_REGEX = Regex(
    """(?:verification|OTP|code|passcode|one[- ]time|2fa|two[- ]factor|security[- ]code)""" +
    """[^\w\n]{0,20}[A-Z0-9][- ]?[A-Z0-9]{3,8}""" +
    """|\b[A-Z]-\d{4,8}\b""" +         // G-123456 style
    """|\b\d{6}\b""" +                  // plain 6-digit
    """|\b\d{4}\b(?=.*code)""",         // 4-digit codes with context
    RegexOption.IGNORE_CASE,
)
```

### R8. Null/empty-body guard in MessagesReadRecentHandler

```kotlin
val body = entry.body.trim()
if (body.isBlank() ||
    body.equals("new message", ignoreCase = true) ||
    body.equals("1 new message", ignoreCase = true) ||
    body.matches(Regex("""\d+ new messages?""", RegexOption.IGNORE_CASE))
) continue  // skip redacted / placeholder notifications
```

### R9. Persistent call_id dedupe via SharedPreferences

`ClientToolDispatcher` persists recent `call_id`s to a dedicated SharedPreferences file (`jane_tool_dedupe.xml`) with a 5-minute TTL. On app start, stale entries are pruned. On each dispatch, the set is checked before any handler invocation.

### R10. Ambiguous-contact flow uses the feedback channel

When `ContactsResolver.resolveExact` returns `Multiple`:
1. Handler enumerates candidates via TTS: "I found two spouses — spouse Hernandez and spouse Martinez. Which one?"
2. Handler emits a `ToolResult` to `PendingToolResultBuffer` with `status: "needs_user"`, `tool: "contacts.call"`, `reason: "ambiguous", candidates: [...]`.
3. On Chieh's next turn, Jane's mind sees the result in her context and can ask a specific clarifying question or re-emit the marker with the disambiguated name.

---

## 13. Non-goals for this spec

This document does not cover:
- Proactive messaging architecture (server → Android push; deferred per long-term memory).
- Cross-device sync of messages (phone-only).
- The Gemma initial-ack short-circuit for phone commands (every phone command goes through Jane's mind in v1; a later optimization could let Gemma short-circuit simple "call X" directly).
- Multi-language support for cancel/approval words.

---
