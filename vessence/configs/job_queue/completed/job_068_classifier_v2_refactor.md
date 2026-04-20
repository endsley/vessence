# Job: Two-Pass Gemma4 Classifier Refactor + SMS Send / End-Conversation Classes

Status: completed
Priority: 1
Model: opus
Created: 2026-04-11
Resume: session handoff mid-implementation

## Context — why this job exists

Chieh wants to add two new classifier intents (SEND_MESSAGE, END_CONVERSATION) to Jane's Gemma4 classifier, and while we were scoping it we decided to restructure the classifier into a cleaner two-pass architecture that was already partially planned.

**The core architecture:**
- **Stage 1 (Gemma4 classifier)**: pure intent classification. Gets FIFO short-term memory context (4 turns, capped at ~600 tokens). No response text — only classification + metadata.
- **Stage 2 (Gemma4 executor)**: dispatches based on Stage 1's classification. For simple intents (SEND_MESSAGE fast-path, END_CONVERSATION, SYNC_MESSAGES) it's pure Python, no LLM. For data-summarization intents (READ_MESSAGES, READ_EMAIL) it calls Gemma with task-specific context (the fetched data, not FIFO). For conversational intents (SELF_HANDLE, DELEGATE_OPUS ack) it calls Gemma with FIFO memory for topical continuity.
- **Stage 3 (Opus brain)**: only invoked when Stage 1 classifies as DELEGATE_OPUS or when a Stage 2 fast-path falls back (e.g., SMS recipient unresolvable, SMS body flagged incoherent).

**Key product decisions made during scoping:**

1. **SMS send fast-path**: if Gemma identifies the recipient AND the message looks clean (Gemma's own `COHERENT: yes` flag), server sends the SMS immediately and responds exactly `"msg sent"` — no draft/confirm round-trip. Overrides the `NEVER send without confirmation` rule in CLAUDE.md — that rule needs to be updated as part of this job.

2. **Semantic sanity gate**: rely on Gemma's `COHERENT` field, NOT Python heuristics (no confidence threshold check, no length bounds, no trailing-conjunction regex). Gemma is the LLM, let it do the semantic check. The rationale: heuristic gates on top of an LLM are duplicative and create false positives.

3. **Recipient resolution order**:
   a) `contact_aliases` table first (learned relational shortcuts like "wife" → Kathia's #)
   b) `contacts` table second (synced from Android phonebook)
   c) If both miss → delegate to Opus, which uses ChromaDB memory to figure out "wife = Kathia", finds Kathia's number via contact search, and writes the new alias row via a server-side `add_alias` call. Next time that relational name hits the fast path directly, no Opus needed.

4. **contact_aliases is a SEPARATE table** (not a column on `contacts`). Reason: the Android contacts sync is a full-replace (`DELETE FROM contacts`), so alias rows would get nuked on every phone startup. Separate table survives the sync.

5. **Draft state (for fallback path)** lives in a new server-side `sms_drafts` table keyed by `draft_id`, with a 5-minute TTL. Only created when Gemma's coherence gate fails or the recipient is ambiguous and we need the old draft→confirm flow. On the fast path, no draft is ever stored.

6. **END_CONVERSATION is a new class** with ~30 trigger phrases. Full list in the Stage 1 prompt at `intent_classifier/v1/gemma_stage1.py`. Context-gated: only fires when the prior assistant turn was a proposal/question/completed action (detected by classifier seeing recent_turns history). Handler returns fixed short ack (`"Ok."`) and emits `conversation_end: true` metadata.

7. **Client-side on END_CONVERSATION**: Android and web clients must STOP auto-reopening the STT mic after TTS, and switch back to "always listen / wake word" passive mode. Server signals this via a `conversation_end: true` field in the response JSON (NOT a CLIENT_TOOL marker — lifecycle is conceptually separate from phone actions).

8. **FIFO source**: `vault_web/recent_turns.py` — already exists, already populated by `conversation_manager.py:850`. Stage 1 pulls from `get_recent(session_id, n=4)` and caps the concatenated context at 2400 chars (~600 tokens). Drops oldest turns first if over budget.

9. **Don't-add list for END_CONVERSATION triggers** (too ambiguous — often mean "yes proceed"): `ok`, `okay`, `alright`, `got it`, `sounds good`, `cool`, `nice`, `great`, `perfect`, `fine`. These stay in DELEGATE_OPUS.

## Progress So Far (already committed, code-locked session)

Files created/modified in `/home/chieh/ambient/vessence/`:

### ✅ Completed

1. **`vault_web/database.py`** — Added two new tables:
   - `contact_aliases (id, alias UNIQUE, phone_number, display_name, created_at)` + index on `alias`
   - `sms_drafts (draft_id PK, session_id, phone_number, display_name, body, created_at)` + index on `(session_id, created_at DESC)`
   - Tables are created and verified working.

2. **`agent_skills/sms_helpers.py`** — NEW file with full helper API:
   - `_normalize_name(name)` — strips "my"/"the"/"to"/"for" prefixes, lowercases, collapses whitespace
   - `resolve_recipient(name)` — returns `{phone_number, display_name, source}` on single match, `None` on zero/ambiguous
   - `add_alias(alias, phone_number, display_name)` — INSERT OR REPLACE on alias key
   - `create_draft(session_id, phone_number, body, display_name)` — returns `draft_id`
   - `get_latest_draft(session_id)` — returns most recent non-expired draft, garbage-collects stale
   - `delete_draft(draft_id)` — manual cleanup
   - `cleanup_expired_drafts()` — batch TTL cleanup
   - `DRAFT_TTL_SECONDS = 300` (5 min)

3. **`intent_classifier/v1/gemma_stage1.py`** — NEW file, full Stage 1 classifier covering ALL classes:
   - Covers: SELF_HANDLE, MUSIC_PLAY, SHOPPING_LIST, READ_MESSAGES, READ_EMAIL, SYNC_MESSAGES, SEND_MESSAGE, END_CONVERSATION, DELEGATE_OPUS
   - Per-class metadata parsing (RECIPIENT/BODY/COHERENT for SMS, QUERY for music/email, ACTION for shopping, FILTER for read-messages)
   - Uses `recent_turns.get_recent(session_id, n=4)` for FIFO context
   - 2400-char budget cap (drops oldest turns first)
   - Returns `{classification, confidence, ...metadata}` dict
   - Timeout 4.0s, env var `JANE_STAGE1_TIMEOUT` override
   - `stage1_classify(message, session_id)` is the public async entry point

### ⏳ Remaining Tasks (in order)

#### Task A: Build `gemma_stage2.py` executor module
**File**: `intent_classifier/v1/gemma_stage2.py` (new)

Signature: `async def stage2_execute(classification: str, metadata: dict, task_context: str, session_id: str, message: str) -> dict`

Returns: `{response: str, delegate: bool, client_tools: list, conversation_end: bool, ...}`

Dispatch table:
- **SEND_MESSAGE**: call `sms_helpers.resolve_recipient(metadata["recipient"])`. If `metadata["coherent"]` is True AND a single recipient resolves → emit `[[CLIENT_TOOL:contacts.sms_send:{"phone_number":"...","body":"..."}]]` and return `{response: "msg sent"}`. If coherent=False → return `{delegate: True}` with a draft-confirm context block (Opus handles the draft). If recipient unresolved → return `{delegate: True}` with an `add_alias` instruction context block.

- **END_CONVERSATION**: return `{response: "Ok.", conversation_end: True}`. No LLM call.

- **SYNC_MESSAGES**: return `{response: "Syncing your messages...", client_tools: [{"name": "sync.force_sms", "args": {}}]}`. No LLM call.

- **READ_MESSAGES**: task_context contains the SMS data block. Call Gemma with a short "summarize these messages" prompt + the data. Return the LLM text.

- **READ_EMAIL**: same pattern, task_context is the email inbox block.

- **MUSIC_PLAY**: task_context contains the created playlist block. Call Gemma with a short "announce this playlist" prompt. Return `{response: LLM text, client_tools: [{"name": "music.play", "args": {"playlist_id": ...}}]}`.

- **SHOPPING_LIST**: task_context is the list-update result. Gemma generates a short confirmation.

- **SELF_HANDLE**: Gemma call with FIFO context (same as Stage 1's FIFO), short conversational response.

- **DELEGATE_OPUS**: Gemma call with FIFO context, generate a short delegation ack ("Looking into that..."). Return `{response: ack, delegate: True}`. Proxy then invokes Opus.

Use the same CLI subprocess path as Stage 1 for LLM calls (reuse code from `gemma_stage1.py`'s subprocess runner — might be worth extracting a shared helper into `intent_classifier/v1/_gemma_cli.py`).

#### Task B: Rewire `jane_web/jane_proxy.py` dispatch
**File**: `jane_web/jane_proxy.py`, lines roughly 1980-2200 (the `elif _classification` chain).

Current structure:
```python
_classification, _router_response = await classify_prompt(message, _router_history)
# keyword overrides
if _classification == "music_play": ...
elif _classification == "read_messages": ...
elif _classification == "sync_messages": ...
elif _classification == "read_email": ...
elif _classification == "shopping_list": ...
# etc.
```

New structure:
```python
from intent_classifier.v1.gemma_stage1 import stage1_classify
from intent_classifier.v1.gemma_stage2 import stage2_execute

stage1 = await stage1_classify(message, session_id)
task_context = await _build_task_context(stage1, session_id)  # NEW: fetches SMS/email/playlist
stage2 = await stage2_execute(stage1["classification"], stage1, task_context, session_id, message)

if stage2.get("conversation_end"):
    # short-circuit, skip brain, return immediately
    return _format_response(stage2["response"], conversation_end=True, client_tools=stage2.get("client_tools", []))

if stage2.get("delegate"):
    # forward to Opus (Stage 3) with the ack from Stage 2 as the delegate_ack
    _gemma_delegate_ack = stage2["response"]
    # ...existing Opus delegation path...

# Otherwise: Stage 2 handled it, return the response
return _format_response(stage2["response"], client_tools=stage2.get("client_tools", []))
```

Extract a new helper `_build_task_context(stage1, session_id)` that:
- If `READ_MESSAGES` → reads synced_messages DB (existing logic in lines 2036-2121)
- If `READ_EMAIL` → calls `agent_skills.email_tools.read_inbox` (existing in lines 2137-2200)
- If `MUSIC_PLAY` → calls `jane_web.main.create_music_playlist_from_query` (existing in lines 2014-2035)
- If `SEND_MESSAGE` / `END_CONVERSATION` / `SHOPPING_LIST` / `SYNC_MESSAGES` / `SELF_HANDLE` / `DELEGATE_OPUS` → returns empty string

**Use an env flag `JANE_USE_V2_PIPELINE=1` to gate the new path.** Keep the old `classify_prompt` elif chain intact behind the flag so Chieh can roll forward by setting the env var and revert instantly by unsetting it. DO NOT delete the old path in this job — that's a follow-up job after the new path is verified in production.

**Preserve the existing keyword overrides** (email/sms/sync keyword safety nets at lines ~1991-2005) — port them to check Stage 1's output and force-reclassify the same way.

#### Task C: Contact alias endpoint + Opus fallback context
**File**: `jane_web/main.py`

Add a new endpoint:
```python
@app.post("/api/contacts/alias")
async def add_contact_alias(request: Request, _=Depends(require_auth)):
    body = await request.json()
    ok = sms_helpers.add_alias(
        alias=body.get("alias", ""),
        phone_number=body.get("phone_number", ""),
        display_name=body.get("display_name"),
    )
    return {"ok": ok}
```

Then in Stage 2's `SEND_MESSAGE` path, when recipient is unresolved, the delegate context block should include:
```
[SMS SEND REQUEST — RECIPIENT UNRESOLVED]
The user wants to text "{recipient}" with message "{body}".
This name is not in contacts or aliases. Use your memory to figure out who this person is,
search contacts for their real name, then POST to /api/contacts/alias with {alias, phone_number, display_name}
so next time this name resolves automatically. After writing the alias, send the SMS via
[[CLIENT_TOOL:contacts.sms_send:{"phone_number":"...","body":"..."}]] and confirm with the user.
[END SMS SEND REQUEST]
```

#### Task D: CLAUDE.md update
**File**: `vessence/CLAUDE.md`, the "Text Message Protocols" section.

Current policy is "NEVER send without confirmation — always draft first." That's being partially overridden by the fast path. Update to:

```
### Sending Messages (v2 pipeline)

Fast path (Gemma's COHERENT=yes + recipient resolves unambiguously):
- Server sends the SMS immediately and responds "msg sent".
- No draft, no confirmation.
- This is safe because Gemma's coherence flag catches STT garbled/cut-off text.

Fallback path (COHERENT=no, or recipient ambiguous/unresolved):
- Opus handles it with the classic draft → confirm → send flow.
- draft_id lives in the server-side sms_drafts table (5 min TTL).
- NEVER send on the fallback path without explicit confirmation.

When Opus resolves an unknown relational name via memory (e.g. "my wife"→Kathia),
Opus MUST write a new contact_aliases row via POST /api/contacts/alias so future
requests hit the fast path without re-resolving.
```

#### Task E: Client-side terminal signal wiring
**Files**:
- `jane_web/jane_proxy.py` — when `stage2.conversation_end == True`, include `"conversation_end": true` in the response JSON.
- `vault_web/templates/jane.html` — find the post-TTS mic reopen (search for "audio ended" or similar event handlers). Gate it on `response.conversation_end`. If true, don't reopen active STT — switch to idle / wake-word state.
- `android/app/src/main/java/com/vessences/android/...` — find the STT reopen in the chat/voice handler. Same gate. Switch back to wake-word/always-listen passive mode.

**Open question for Chieh**: confirm that "always listen = wake-word passive mode, active convo temporarily overrides it" is the correct state machine. I asked but didn't get a direct yes/no before we paused.

#### Task F: Thin out / retire `gemma_router.py`
After the new path is verified live and `JANE_USE_V2_PIPELINE=1` becomes the default, in a **follow-up job** (not this one): grep for remaining imports of `classify_prompt` / `ROUTER_MODEL`, update them to point at `stage1_classify`, and delete `gemma_router.py`. Don't do this in the same job — keep the safety net until live verification is complete.

## Open Questions Still Waiting For Chieh

1. **Task context fetching location** — I proposed option A (fetch in `jane_proxy.py` between Stage 1 and Stage 2) vs option B (fetch inside Stage 2 itself). Recommended A. Not yet confirmed. → **Default to option A if Chieh hasn't answered by resume time.**

2. **Stage 2 LLM model** — Same Gemma model as Stage 1? I'm assuming yes. No pushback heard. → **Default to same model.**

3. **Env flag strategy** — I proposed `JANE_USE_V2_PIPELINE=1` as a kill switch. Not yet confirmed. → **Default to implementing the flag.**

4. **Service restart timing** — I proposed graceful restart at the end of the refactor. Not yet confirmed. → **Do graceful restart at end via `bash $VESSENCE_HOME/startup_code/graceful_restart.sh` unless told otherwise.**

5. **Always-listen state machine** — interpretation of "always listen back on for next conversation" — I asked but didn't get a direct answer. → **Default to "after END_CONVERSATION, client switches from active STT to wake-word passive mode" — the most natural reading.**

## Files Touched in This Session (for audit / rollback)

New files:
- `/home/chieh/ambient/vessence/agent_skills/sms_helpers.py`
- `/home/chieh/ambient/vessence/intent_classifier/v1/gemma_stage1.py`

Modified files:
- `/home/chieh/ambient/vessence/vault_web/database.py` (added 2 tables + indexes)

None of the changes are wired into `jane_proxy.py` yet, so `jane-web.service` is unaffected. Current live behavior is unchanged — the new code is dormant.

## Code Edit Lock

An agent named `jane-claude` (PID 3357305) held the lock at session pause time. **BEFORE RESUMING, check lock status** with `/home/chieh/google-adk-env/adk-venv/bin/python $VESSENCE_HOME/agent_skills/code_lock.py status`. If the lock is held by the prior PID and the PID is dead, clear it with `rm $VESSENCE_DATA_HOME/locks/code_edit.lock`. Then re-acquire before editing.

## How to Resume This Job

1. Read this file completely.
2. Check `configs/job_queue/` for this file (job_068). Read the three completed file-changes above (sms_helpers.py, gemma_stage1.py, database.py) to verify they landed as described.
3. Acquire the code lock as `jane-claude` or similar.
4. Start at **Task A (gemma_stage2.py)** and work through in order.
5. When all tasks complete, do a graceful restart: `bash $VESSENCE_HOME/startup_code/graceful_restart.sh` (announce it in bold first per CLAUDE.md).
6. Mark this job `Status: completed` and log via `work_log_tools.log_activity`.
7. Run the AI Review Panel before reporting done (`$VESSENCE_HOME/agent_skills/consult_panel.py`).

## Test Plan

After Tasks A-E are done and the service is restarted:

1. **Fast path test**: Chieh says "text my wife that I'll be home late". Expected: if "wife" alias exists → single round-trip, response "msg sent", SMS delivered to Kathia. If "wife" alias doesn't exist yet → fallthrough to Opus which resolves via memory, writes alias, sends message, confirms.

2. **Incoherent test**: Chieh says "text my wife purple elephant banana". Expected: COHERENT=no, fallback to Opus draft-confirm flow.

3. **End conversation test**: Chieh is mid-conversation with Jane, says "ok thanks". Expected: response "Ok.", `conversation_end: true` in JSON, client stops reopening mic, switches to wake-word mode.

4. **No-regression test**: existing classes still work — "play shakira", "read my texts", "check my email", "add milk to the list", "sync my messages", "hey", "fix the auth bug".

5. **Alias learning test**: set `contact_aliases` to empty, say "text my wife I miss you" — should fall through to Opus once, which writes the alias, and a subsequent "text my wife hi" should hit the fast path with no Opus round-trip.
