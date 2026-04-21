---
Title: Multi-user account isolation - users, memory, vaults, capabilities
Priority: 1
Status: pending
Created: 2026-04-20
Source: user_request
---

## Goal

Add real multi-user support to Jane.vessence.com so an admin can create a new
user from the UI. Each account must be distinguished by login email and must
have isolated memory, vault storage, conversation state, and capabilities.

The target user folder layout is:

```
$VESSENCE_DATA_HOME/users/<sanitized_email>/
  config.json
  memory/vector_db/        # private ChromaDB collection: user_memories
  vault/                   # private vault root for this account
```

`<sanitized_email>` should be derived from the account email, such as
`person_at_example_com`. `config.json` must keep the raw email for login/admin
display.

## Why This Matters

Chieh's information and another user's information must never mix. This is
more than separate chat history:

- Personal facts must not retrieve from Chieh's ChromaDB for another user.
- File browsing must not expose Chieh's vault to another user.
- Conversation state and recent-turn FIFO must not cross users even if clients
  reuse generic IDs like `jane_android`.
- Tool/capability access must be scoped per account.
- Initial user seeds should create a usable first memory without copying
  Chieh's private context.

## Current WIP State

This session started a prototype but did not complete or deploy it. Review the
working tree before continuing.

Touched files include:

- `agent_skills/user_manager.py`
- `memory/v1/memory_retrieval.py`
- `context_builder/v1/context_builder.py`
- `jane_web/jane_proxy.py`
- `jane_web/main.py`
- `jane_web/jane_v2/pipeline.py`
- `vault_web/files.py`
- `vault_web/templates/app.html`
- `configs/Jane_architecture.md`
- `configs/SKILLS_REGISTRY.md`
- `configs/memory_manage_architecture.md`

Prototype pieces already added:

- `user_manager.py` normalizes emails into user folder IDs.
- User creation creates `config.json`, `memory/vector_db/`, and `vault/`.
- User creation seeds private Chroma `user_memories`.
- `memory_retrieval.build_memory_sections()` accepts `user_memory_path`.
- `context_builder` can load managed user context and skip global personal
  facts for managed users.
- `jane_proxy` threads `user_id` into context build, prewarm, and prefetch.
- `jane_v2.pipeline` started scoping canonical session IDs for managed users.
- `/api/admin/users` GET/POST was started in `jane_web/main.py`.
- Settings UI started a Users section in `vault_web/templates/app.html`.
- `vault_web/files.py` started accepting an optional vault root in path helpers.

Verification already run:

- `python -m py_compile` passed for the edited Python files at that point.
- A direct managed-user Chroma seed/retrieval test passed using a temporary
  account `codex-managed-user-test@example.com`; the temp user folder was
  removed afterward.
- The AI review panel was attempted through `consult_panel.py`, but no peer
  model responded.

## Required Architecture

### 1. User Folder and Config

User creation must write:

```json
{
  "user_id": "person_at_example_com",
  "email": "person@example.com",
  "display_name": "Person",
  "personality": "default",
  "memory_namespace": "person_at_example_com",
  "memory_chromadb_path": "$VESSENCE_DATA_HOME/users/person_at_example_com/memory/vector_db",
  "vault_root_path": "$VESSENCE_DATA_HOME/users/person_at_example_com/vault",
  "capabilities": ["chat", "memory"],
  "managed": true,
  "created_at": "...",
  "seeded_at": "...",
  "seeded_memory_count": 3
}
```

Do not store new users under opaque IDs alone. The folder name must identify
the account email in a filesystem-safe way.

### 2. Admin UI

Add a user-management section reachable from Jane.vessence.com settings.

It should support:

- Email
- Display name
- Capability checkboxes
- Initial memory textarea, one seed fact per line
- Existing user list with email, display name, memory path, vault path,
  capabilities, and created date

Only admin users may call the user-management API. Default admin should be the
first `ALLOWED_GOOGLE_EMAILS` entry unless `VESSENCE_ADMIN_USERS` or
`ADMIN_EMAILS` is configured.

### 3. Login Allowlist

Creating a user should add that email to `ALLOWED_GOOGLE_EMAILS` in
`$VESSENCE_DATA_HOME/.env` and update `os.environ` for the running process.

Do not assume this removes the need for a `jane-web.service` restart. If the
new endpoint code is not already loaded, restart is still required.

### 4. Memory Isolation

Managed users must retrieve from their private ChromaDB only:

- Query `$VESSENCE_DATA_HOME/users/<sanitized_email>/memory/vector_db`
- Collection name: `user_memories`
- Skip global `user_memories`
- Skip global `short_term_memory`
- Skip global `file_index_memories`
- Skip global `user_profile_facts.json`

Important remaining gap: retrieval is only half the job. Conversation writeback
still needs audit. `memory/v1/conversation_manager.py` and any add-fact paths
must not write managed-user turns into Chieh's shared memory lanes.

### 5. Conversation State Isolation

Conversation state keys must include the managed user ID. This prevents one
phone or browser from reusing `jane_android` or another generic session ID
across accounts.

Expected behavior:

- Chieh unmanaged sessions keep legacy session IDs.
- Managed user sessions use something like:
  `person_at_example_com__jane_android`
- FIFO, pending actions, summaries, in-memory history, prewarm, prefetch, and
  standing-brain sessions must use the scoped ID consistently.

### 5.1 Conversation-Bleed Prevention Spec

The system needs one canonical conversation key per active account/device/chat
stream. That key must be produced once at request entry and passed everywhere
that stores or retrieves conversational state.

Canonical key format:

```
<sanitized_email>__<device_id>__<client_session_uuid>
```

Rules:

- `sanitized_email`: derived from the authenticated Google email using the same
  function as the user folder name.
- `device_id`: a stable per-install Android/Web device ID, not the trusted
  device database row alone. Android should create and persist a random
  `jane_device_id` on first launch.
- `client_session_uuid`: a full UUID for the chat thread. Do not truncate to
  eight characters. The current Android `jane_android_<8 chars>` is good enough
  for a single-user prototype but not for multi-user.
- Legacy Chieh sessions may keep existing IDs until migrated, but managed users
  must use the canonical key.

The canonical key must be used for:

- `jane_proxy._sessions`
- per-session `request_gate`
- persistent Claude/Codex/Gemini manager session IDs
- `ConversationManager(session_id)`
- SQLite conversation ledger `session_id`
- `jane/session_summary.py` files
- `vault_web.recent_turns`
- pending action resolver state
- v2/v3 FIFO reads and writes
- memory prewarm and prefetch caches
- live broadcast channels where session-specific progress is shown
- turn-dedupe keys and replay buffers

What must not happen:

- Do not use raw `body.session_id` directly after request entry.
- Do not mix cookie auth session ID with conversation session ID.
- Do not let a phone answer a pending follow-up opened by another phone.
- Do not let a persistent standing-brain session see turns from another phone.
- Do not let retries from one device replay output into another device.

Implementation shape:

1. Add a single helper, for example `resolve_conversation_key(request, body)`,
   in the web layer.
2. It should return `{user_id, sanitized_user_id, device_id, client_session_id,
   conversation_key}`.
3. All chat entry points (`/api/jane/chat`, `/api/jane/chat/stream`,
   `/api/jane/init-session`, v2/v3 Stage 3 escalation) must call this helper or
   receive its result.
4. Downstream code should accept only the resolved `conversation_key` for state
   lookup. Avoid recomputing it in multiple files.
5. Log both the short conversation key and raw client session for debugging.

Collision behavior:

- If two requests have the same canonical key, they are intentionally the same
  conversation and should serialize through the same `request_gate`.
- If two different devices accidentally send the same client session UUID, the
  `device_id` still separates them.
- If two different users accidentally send the same device/session IDs, the
  `sanitized_email` still separates them.
- If any part is missing for a managed user, fail closed with a clear 400/401
  rather than falling back to an unscoped shared ID.

Migration requirements:

- Android should send both `device_id` and `session_id` in chat requests.
- Existing Android installs can keep their current `jane_session_id`, but future
  new/reset sessions should use a full UUID.
- Server should tolerate old clients temporarily by deriving `device_id` from
  trusted device fingerprint only for Chieh's unmanaged account.
- Managed users should require the new protocol before enabling phone tools.

### 6. Vault Isolation

Each managed user must get a private vault:

```
$VESSENCE_DATA_HOME/users/<sanitized_email>/vault/
```

File APIs must resolve paths against the active user's vault root. Until this
is fully wired, managed users must not be allowed to browse or serve Chieh's
global `$VAULT_HOME`.

Required endpoints to audit:

- `GET /api/files`
- `GET /api/files/list/{path}`
- `GET /api/files/meta/{path}`
- `GET /api/files/thumbnail/{path}`
- `GET /api/files/serve/{path}`
- `GET /api/files/find`
- `GET /api/files/search`
- `GET /api/files/play/{path}`
- `GET /api/files/content/{path}`
- `PUT /api/files/content/{path}`
- `POST /api/files/upload`
- `POST /api/files/upload/single`
- `PATCH /api/files/description/{path}`

`vault_web/files.py` has an in-progress optional `root_dir` parameter on some
helpers. Finish that consistently or add a request-scoped vault-root wrapper
in `jane_web/main.py`.

### 7. Capability Isolation

Capability flags should be enforced server-side, not just described in the
prompt.

Initial capability list from the prototype:

- `chat`
- `memory`
- `vault_read`
- `vault_write`
- `email`
- `calendar`
- `phone`
- `web_search`
- `code_assistant`
- `essences`
- `user_admin`

Minimum enforcement:

- No vault access without `vault_read`.
- No vault writes/uploads without `vault_write`.
- No email/calendar actions without the relevant capability and that user's
  OAuth token.
- No phone/SMS/timer commands unless the request is from that user's Android
  device and `phone` is enabled.
- No user creation unless `user_admin` or configured admin.

### 8. OAuth and Tokens

Google OAuth sessions currently store or retrieve Gmail tokens by email. Keep
that email-keyed model; it matches the account folder identity.

Audit:

- `agent_skills/email_oauth.py`
- `agent_skills/calendar_tools.py`
- `/auth/google/callback`
- `/api/auth/google-token`
- trusted device labels and session `user_id`

The raw email and sanitized folder ID must map reliably both ways where needed.

## Android Transcript Evidence

While preparing this job, Chieh asked to read the last two Android transcript
turns. The current latest Android session was:

- Session: `jane_android_3b191135`
- Range: `2026-04-10 03:48:31` to `2026-04-20 11:02:28`
- Total turns: `502`

Last two turns showed a separate but relevant user-facing isolation issue:

1. User: `let's make a 4 minutes`
2. Jane: exposed internal reasoning before setting a 4-minute timer:
   `No evidence gathering needed; this is a direct action per the timer class protocol.`
3. Android tool result: `timer.set` completed for `240000ms`
4. Jane: duplicated the confirmation and exposed callback analysis:
   `Got it, your 4-minute timer is running... Got it, your 4-minute timer is running.`

This should be handled either in this job or a follow-up Android response hygiene
job. User-facing Android responses must not include internal class protocols,
tool callback analysis, or duplicated confirmations.

## Acceptance Criteria

1. Admin can create a managed user from the settings UI.
2. User folder is created under `$VESSENCE_DATA_HOME/users/<sanitized_email>/`.
3. The folder contains `config.json`, `memory/vector_db/`, and `vault/`.
4. The new user's email is added to `ALLOWED_GOOGLE_EMAILS`.
5. The new user can log in and chat with Jane.
6. The new user's memory retrieval returns seeded facts from only their private
   ChromaDB.
7. The new user's chat cannot retrieve Chieh's personal Chroma memory.
8. The new user's file browser cannot see Chieh's vault.
9. Capabilities are enforced by backend checks.
10. Conversation state is scoped by user so `jane_android` does not mix users.
11. Tests cover user creation, private memory retrieval, vault root resolution,
    capability denial, and session ID scoping.

## Suggested Tests

- Unit: `normalize_user_id("person@example.com") == "person_at_example_com"`
- Unit: `create_user_space()` creates config, Chroma path, vault path, and seed
  memories.
- Unit: managed-user memory query returns a seeded fact and does not query shared
  memory.
- Unit: managed-user session ID scoping changes `jane_android` to
  `<user_id>__jane_android`.
- Unit: two devices with the same client session UUID produce different
  canonical conversation keys.
- Unit: two users with the same device/session IDs produce different canonical
  conversation keys.
- Integration: pending action opened on phone A cannot be answered from phone B.
- Integration: concurrent requests from phone A and phone B use separate
  request gates but may still contend for shared model capacity.
- API: non-admin cannot call `/api/admin/users`.
- API: admin creates user and receives public config with memory/vault paths.
- API: managed user without `vault_read` gets 403 for `/api/files`.
- API: managed user with `vault_read` lists only their private vault.
- API: managed user with `vault_write` uploads only into their private vault.
- Regression: Chieh unmanaged account still uses existing shared vault and
  existing memory behavior.

## Files to Start With

- `agent_skills/user_manager.py`
- `jane_web/main.py`
- `jane_web/jane_proxy.py`
- `jane_web/jane_v2/pipeline.py`
- `jane_web/jane_v3/pipeline.py`
- `context_builder/v1/context_builder.py`
- `memory/v1/memory_retrieval.py`
- `memory/v1/conversation_manager.py`
- `vault_web/files.py`
- `vault_web/auth.py`
- `vault_web/oauth.py`
- `vault_web/templates/app.html`

## Notes for Next Session

- Read `AGENTS.md` and the Jane startup sequence first.
- Acquire the code edit lock before editing source.
- The working tree is already dirty from unrelated wake-word, Android, calendar,
  and prior Jane changes. Do not revert unrelated files.
- The prototype may need cleanup before continuing; verify with `git diff` on
  the files listed in "Current WIP State".
- Do not restart `jane-web.service` unless Chieh asks or the restart policy
  threshold is met.
