# Vessence System Architecture

This document is the comprehensive technical reference for the Vessence platform. It describes every major subsystem, how they connect, and where the code lives.

**Last updated:** 2026-04-16

> **Invariant (2026-04-16):** Every caller of the local `qwen2.5:7b` model MUST import `LOCAL_LLM_NUM_CTX` from `jane_web/jane_v2/models.py` and pass it as `num_ctx`. Ollama runs a separate runner per `(model, num_ctx)` tuple; any divergent value causes a full model reload (~1.6–14 s) on the next caller swap and defeats `keep_alive=-1`. Never hardcode `num_ctx`; never omit it and rely on Ollama's default (which is the model's `n_ctx_train = 32768` for qwen2.5). See `preference_registry.json::unified_local_llm_num_ctx`.

> **Operational note (2026-04-16):** `jane-web.service` is configured with `Restart=no` (not `on-failure`). The older `on-failure` setting combined with a port-clearing import hook in `main.py` caused duplicate-uvicorn leaks on every graceful restart (~150 orphan threads per restart). Auto-recovery is now handled by `startup_code/jane_healthcheck.sh` which issues an explicit `systemctl restart` on true outages. `graceful_restart.sh` has a hard invariant (Step 0.6) that reconciles multiple live uvicorns before ping-ponging.

---

## 1. System Overview

Vessence is a self-hosted personal AI platform centered on a single live agent identity: Jane. The core architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                        USER INTERFACES                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│  │ Android  │  │   Web    │  │Claude CLI│                   │
│  │ (Kotlin) │  │ (FastAPI)│  │ (Hooks)  │                   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                   │
│       │              │              │                         │
├───────┴──────────────┴──────────────┴─────────────────────────┤
│                     JANE WEB SERVER (port 8081)               │
│  ┌────────────┐  ┌──────────────┐  ┌───────────────────────┐│
│  │ jane_proxy │  │context_builder│  │  Permission Broker   ││
│  └─────┬──────┘  └──────┬───────┘  └───────────────────────┘│
│        │                │                                     │
├────────┴────────────────┴─────────────────────────────────────┤
│            JANE'S INITIAL ACK (fast front half)               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │  Gemma4  │  │  Haiku   │  │  Gemini  │  │ GPT-5-   │     │
│  │  (local) │  │   4.5    │  │  Flash   │  │  nano    │     │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘     │
│   Speaks first · triages · self-handles trivia ·             │
│   emits ETA hint · otherwise delegates to Jane's mind        │
├───────────────────────────────────────────────────────────────┤
│      JANE'S MIND (deep reasoning — "standing brain")          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│  │  Claude  │  │  Gemini  │  │  OpenAI  │   (3 persistent   │
│  │  Opus    │  │   Pro    │  │  Codex   │    CLI processes)  │
│  └──────────┘  └──────────┘  └──────────┘                   │
│                                                               │
├───────────────────────────────────────────────────────────────┤
│                      DATA & MEMORY LAYER                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐ │
│  │ ChromaDB │  │  SQLite  │  │  Vault   │  │  Essences   │ │
│  │ (4 colls)│  │ (ledger) │  │ (files)  │  │ (pluggable) │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────┘ │
│                                                               │
├───────────────────────────────────────────────────────────────┤
│                    AUTOMATION LAYER (Cron)                     │
│  Janitor │ Archivist │ Audit │ Briefing │ Scheduler │ Backup │
└───────────────────────────────────────────────────────────────┘
```

**Jane Unified Identity:**
- **Jane** — The unified technical and personal brain. She is both the permanent continuity layer (long-term memory, project architecture, reasoning) and the runtime vessel (pluggable essences, tool execution, multimodal interaction).

Historical `Amber` references in the repository describe older architecture or legacy implementation paths. They do not represent a second current agent identity.

### 1a. Roles vs models

Jane is one agent from the user's point of view, but her execution is split across two pluggable model slots. A "role" is what a slot does for Jane; a "model" is whatever LLM is currently filling that slot. Swapping models must never change the role vocabulary we use with the user.

```
                ┌─────────────────────────┐
                │          Jane           │
                │  (one agent, one soul)  │
                └───────────┬─────────────┘
                            │
           ┌────────────────┴────────────────┐
           │                                 │
┌──────────▼──────────┐            ┌─────────▼──────────┐
│  Jane's initial ack │            │    Jane's mind     │
│  (fast, ~1-2s)      │            │  (deep reasoning)  │
├─────────────────────┤            ├────────────────────┤
│ • Haiku 4.5         │            │ • Claude Opus 4.6  │
│ • Gemini Flash      │            │ • Gemini 2.5 Pro   │
│ • GPT-5-nano        │            │ • GPT-5.4          │
│ • Gemma4 (local)    │            │                    │
│   (any tiny model)  │            │  (any frontier)    │
└─────────────────────┘            └────────────────────┘
   Speaks first,                     Writes code,
   triages, self-handles             does research,
   trivia/nonsense,                  runs tools,
   emits ETA hints,                  answers hard things.
   otherwise delegates →             Long-lived CLI
                                     ("standing brain").
```

| Role | What it does | Default model (per provider stack) |
|---|---|---|
| **Jane's initial ack** | The fast front half. Speaks first within ~1–2s. Classifies each turn as SELF_HANDLE / MUSIC_PLAY / DELEGATE. Self-handles trivia, greetings, weather, unit conversions, obvious STT garbage (with a "was that meant for me?" check-in), and music routing. Otherwise emits a contextual ack with a verbal ETA hint (TRIVIAL / MEDIUM / BIG) and hands off to Jane's mind. Never tries to answer anything hard. | **Claude stack:** `claude-haiku-4-5-20251001` · **Gemini stack:** `gemini-2.5-flash` · **OpenAI stack:** `gpt-5-nano` · **Local/no-cloud:** `LOCAL_LLM` from `jane_web/jane_v2/models.py` (single source of truth — swap model there) |
| **Jane's mind** (a.k.a. "the standing brain") | The deep reasoner. Writes code, does research, runs tools, maintains long-running projects, replies to anything that wasn't self-handled. Implemented as a long-lived CLI process kept warm to skip cold-start ("standing brain"). | **Claude stack:** `claude-opus-4-6` · **Gemini stack:** `gemini-2.5-pro` · **OpenAI stack:** `gpt-5.4` |

**Vocabulary rules:**
- User-facing (Android UI, web UI, spoken output): always just **"Jane"**. The user should not have to know which slot handled which turn.
- Internal (code, docs, this architecture reference, debugging): say **"Jane's initial ack"** and **"Jane's mind"**. The term **"standing brain"** stays in use but refers specifically to the *infrastructure* — the long-lived CLI process that hosts Jane's mind — not the role itself.
- Python symbols (`StandingBrainManager`, `standing_brain.py`, `GEMMA_ROUTER_MODEL` env var) are infra names and stay as-is; renaming them is churn without upside.

**Default selection policy:** A new user inherits the initial-ack model that is provider-matched to whichever stack is configured for Jane's mind, so the ack latency stays tight by default. Customizing the initial-ack model independently of Jane's mind is a planned user setting, not the default path.

**Pluggability status (2026-04-18):** Jane's mind slot is fully pluggable today via `jane/standing_brain.py` (`ALL_PROVIDERS = ("claude", "gemini", "openai")` with env-var overrides). Jane's initial ack slot now also dispatches across four providers (Ollama / Anthropic / Google / OpenAI) in `intent_classifier/v1/gemma_router.py`, with the Ollama default pulled from `LOCAL_LLM` in `jane_web/jane_v2/models.py` so no specific local model is hardcoded.


---

## 2. Request Lifecycle (Message → Response)

When a user sends a message through any interface, this is the complete flow:

### Phase 1: HTTP Entry
- **Endpoint:** `POST /api/jane/chat/stream` (`jane_web/main.py`)
- Auth validated via session cookie (`get_or_bootstrap_session()`)
- Instant commands (`show job queue`, `my commands`) bypass LLM entirely (<100ms)
- Task classifier checks if this is a "big task" to offload to background queue

### Phase 2: Intent Classification + Context Assembly (Initial-Ack Router)
- **`LOCAL_LLM`** (default: qwen2.5:7b; pluggable via `jane_web/jane_v2/models.py`, called from `intent_classifier/v1/gemma_router.py` — the filename is legacy, the running model is NOT gemma) classifies each message into an intent:
  - `SELF_HANDLE` → greetings, math, trivia (minimal context)
  - `MUSIC_PLAY` → server creates playlist, short-circuits (no Opus needed)
  - `SHOPPING_LIST` → server injects list data, Opus responds
  - `READ_MESSAGES` → server emits `messages.read_inbox` tool call to Android
  - `READ_EMAIL` → server pre-fetches inbox via Gmail API server-side
  - `READ_CALENDAR` → server pre-fetches events via Google Calendar API server-side (shares Gmail OAuth grant)
  - `DELEGATE_OPUS` → everything else (SMS, calls, complex questions, code)
- Pre-warmed at startup via Ollama `keep_alive: -1` (~300ms classification)
- Classification determines **two things**: quick ack content AND context depth

**Architecture principle (2026-04-09):** Gemma is the **router + context assembler**, not just a classifier.
- For READ operations, the server pre-fetches data BEFORE Opus runs and injects it into context
- For WRITE operations (SMS, calls), only the specific tool's protocol (~200 tokens) is injected
- Opus never sees protocols for tools it won't use on this turn
- This keeps context O(1) per turn regardless of how many tools Jane has

### Phase 2.1: Quick Acknowledgment
- Gemma generates a brief ack ("Let me check your messages...") emitted immediately via SSE
- Ack covers the latency of server pre-fetch + Opus thinking
- In voice mode: ack is spoken via TTS. In text mode: suppressed (typing indicator instead).

### Phase 2.5: Stage 2 Fast Handler (SQL short-circuit, no LLM)

Some intent classes have a **Stage 2 handler** — a deterministic Python function that answers directly from a local data source (SQLite, file, etc.) without invoking any LLM.

**Pipeline (`jane_web/jane_v2/pipeline.py`):**
1. **Stage 1** — embedding classifier (`intent_classifier/v2/`) identifies the class via bge-small-en-v1.5 + qwen2.5 validation
2. **Stage 2** — if the matched class has a handler at `jane_web/jane_v2/classes/<class>/handler.py`, the handler is called. If it returns a `dict`, the response is streamed and **Opus is never invoked** (typical latency: ~20–50ms)
3. **Stage 3** — fallback to Opus (current standing brain) if Stage 2 returns `None` or no handler exists

**Logging:** Each turn logs `jane_v3 pipeline: stage2 <class name> handler (<Nms>)` or `stage3` for auditing.

**Current Stage 2 handlers:**

| Class | Handler | Data source | Typical answer |
|:------|:--------|:------------|:---------------|
| `clinic_schedules_info` | `jane_web/jane_v2/classes/clinic_schedules_info/handler.py` | `$VESSENCE_DATA_HOME/schedule.db` SQLite | Patient count or names per day of week; "next/current patient" reply now offers to read the patient's Visit Summary via a STAGE2_FOLLOWUP (`awaiting: "next_patient_details_confirm"`) |
| `tell_joke` | `jane_web/jane_v2/classes/tell_joke/handler.py` | qwen2.5:7b (high-temp) + recent FIFO | Single short clean joke; FIFO context lets "another joke" pivot to a new one. Returns `None` on LLM failure → escalates to Stage 3. |
| `do_math` | `jane_web/jane_v2/classes/do_math/handler.py` | qwen2.5:7b (parser) + Python `ast` safe-eval | Numeric arithmetic answer. Qwen translates the spoken phrase into a single Python expression; an AST walker evaluates only numeric literals + binary/unary ops + a tiny safe call set (sqrt, pow, abs, round, floor, ceil), with an exponent cap (`_MAX_EXPONENT=1000`) to block DoS via giant powers. Qwen alone hallucinated multi-digit products (audit 2026-04-24: 234×567 → 132066 vs actual 132678); Python now does the arithmetic. Returns `None` on parse failure or non-numeric prompts → escalates to Stage 3. |

**Adding a new Stage 2 handler:**
1. Create `jane_web/jane_v2/classes/<class_name>/handler.py` with `async def handle(prompt: str) -> dict | None`
2. Create `jane_web/jane_v2/classes/<class_name>/metadata.py` with `METADATA` dict (name, priority, description, few_shot, ack)
3. Add a matching intent class in `intent_classifier/v2/classes/<class_name>.py`
4. Add adversarial test cases in `intent_classifier/v2/classes/<class_name>_adversarial.json`

### Phase 2.6: Multi-turn handler patterns (Stage 2 conversation flows)

A Stage 2 handler can manage a multi-turn flow by emitting a `STAGE2_FOLLOWUP` `pending_action` in its `structured` block. The next user turn re-enters the same handler via the `pending` kwarg (the v3 pipeline introspects the handler signature). Three canonical patterns:

- **Repeating-read** (`todo_list`, `weather`, `read_calendar`): handler answers, then asks "want another?" with `pending_continuation(awaiting="another_X_or_stop", ...)`. On resume: `end_phrase.is_end()` → `end_conversation("Ok.")`; valid follow-up → answer again + ask again; pivot/garbage → `{abandon_pending: True, force_stage3: True}`. `read_calendar` additionally parks on `awaiting_day_choice` when the user replies `yes` without naming a day, then re-enters the loop after the next day-name reply. The handler also enforces a Stage-2-vs-Stage-3 routing rule: only prompts that explicitly name a specific day or week ("today", "tomorrow", "this week", weekday names) stay in Stage 2 — vague queries ("what's coming up", "anything important") return `None` to escalate to Opus.
- **Confirm-or-revise** (`send_message`, future `send_email`): when LLM extract is uncertain (e.g. qwen `COHERENT=no`), build a draft and ask "Should I send it?" with `pending_continuation(awaiting="send_confirmation", data={"draft":{...}})`. On resume check order is `is_yes` → send + `conversation_end`; `is_no` → ask for revised body (`awaiting="revised_body"`); `end_phrase.is_end` → cancel; else → escalate. **Important:** check `confirmation.is_yes/is_no` BEFORE `end_phrase.is_end` here — bare "no" answers a confirm prompt as "revise", not "abort" (see `agent_skills/confirmation.py` docstring).
- **One-shot action** (`timer`): handler walks the user through required slots (duration → label) via short pendings, then on the final action returns `{conversation_end: True, ...}` so the voice loop closes cleanly.

Shared helpers:
- `agent_skills/end_phrase.is_end(text)` — strict "I'm done" matcher (`stop`, `cancel`, `nevermind`, `bye`, etc.)
- `agent_skills/confirmation.is_yes(text)` / `is_no(text)` — yes/no parser tuned for confirm-or-revise prompts (`is_no` includes `wrong`, `not quite`, `revise`, etc.)
- `agent_skills/private_handler_utils.pending_continuation(handler_class, awaiting, question, data)` — universal `STAGE2_FOLLOWUP` builder
- `agent_skills/private_handler_utils.end_conversation(text="Ok.", structured=None)` — sets `conversation_end: True` so v3's stream emits the NDJSON `conversation_end` event; the Android `ChatViewModel.endVoiceConversation()` then plays a short two-pip `TONE_PROP_ACK` audio cue and falls back to wake-word passive mode.

### Phase 2.7: Stage 3 privacy gate (`jane_web/jane_v3/pipeline.py:_stage3_privacy_check`)

Before any escalation to Opus (Stage 3), the v3 entry points run a chroma-based privacy check on the raw prompt. The gate refuses (returns `PRIVACY_REFUSAL_TEXT` with `conversation_end=True`) when EITHER (a) the closest chroma neighbor within distance 0.40 belongs to a `privacy="local_only"` class, OR (b) ≥3 of the top-5 in-range neighbors are private. This is defense-in-depth on top of the per-handler `is_no_stage3` check — it catches prompts that bypass Stage 2 entirely (e.g. classified as `others`).

### Phase 3: Context Assembly (`context_builder/v1/context_builder.py`)
- **Gemma classification → intent_level mapping** (`CLASSIFICATION_TO_INTENT`):
  - `self_handle` → `greeting` intent (no memory, no tools, no history)
  - `read_messages` → `data_mode` (no memory, no tools; data pre-fetched by server)
  - `read_email` → `data_mode` (same — email data injected into message)
  - `delegate_opus` → full profile (memory, history, all tool protocols)
- **`_classify_prompt_profile()`** selects what context to inject based on intent_level:
  - `tool_mode` → no memory, no history, only the specific tool's rules (~200 tokens)
  - `data_mode` → no memory, no history, no tools (data already in message)
  - `greeting` → no memory, no tools, no history
  - `None` (full) → memory + history + tools + task state + conversation summary
- **System prompt sections** (for full profile):
  1. Base Jane identity
  2. Active essence personality (if loaded)
  3. Essence tools catalog
  4. User background (selective)
  5. Current task state
  6. Conversation summary (last 6 turns, max 2400 chars)
  7. Retrieved memory (ChromaDB, max 6000 chars) — **skipped for tool_mode/data_mode/greeting**
  8. Tool protocols — **only injected for full profile; specific tool context for tool_mode**
  9. Active file context

### Phase 4: Brain Routing (`jane_web/jane_proxy.py`)
- **Standing brain optimization:** If brain is alive AND turn count > 0, skip expensive context rebuild — brain already has context from prior turns. Only inject new message + recent history.
  - For `tool_mode`/`data_mode` turns: even recent history is skipped — only tool context + user message.
- **Single model** for all turns: Claude Opus via standing CLI brain. No tier routing.
- Provider-specific execution path selected by explicit branch in `jane_proxy.py`:
  - `claude` → `persistent_claude.py`
  - `gemini` → `persistent_gemini.py`
  - `codex` → `persistent_codex.py`
  - fallback / non-persistent providers → `brain_adapters.py`
- The internal provider protocols differ, but Jane web normalizes them into the same outward event contract for clients.

### Phase 4.1: Tool Call Follow-Up (Android only)
- When a `client_tool_call` SSE event fires (e.g., `messages.read_inbox`), Android runs the handler
- After the brain's "done" event, if a tool call was dispatched, Android waits up to 10s for the handler to finish
- Tool results are auto-sent as a follow-up message so Opus can respond with actual data in one conversational turn
- This prevents the dead-end where STT re-launches before the user has heard anything

### Phase 5: Streaming Response
- Brain outputs chunks → `jane_proxy.py` emits SSE events to client:
  - `thought` — thinking blocks (rendered inline in thought process display)
  - `tool_use` — tool invocations (name + input)
  - `tool_result` — tool outputs
  - `delta` — response tokens (streamed incrementally)
  - `done` — final response
  - `error` / `provider_error` — errors with switch-provider UI
- `StreamBroadcaster` notifies other connected clients of same session
- Thought process (thoughts, tool use, results) displayed inline in both web and Android chat. Collapsed into expandable summary after response completes.

### Phase 5.1: Provider-Specific Streaming Implementations

All three primary Jane web providers aim to produce the same frontend effect:
- early visible progress
- incremental or near-incremental response delivery
- a final `done` event
- identical web/android client protocol

They achieve that effect with different internal mechanisms:

| Provider | Internal Mechanism | Session Continuity | Native Event Detail | Jane Web Normalization |
|:---------|:-------------------|:-------------------|:--------------------|:-----------------------|
| **Claude** | `claude --print --verbose --output-format stream-json` parsed by `persistent_claude.py` | Claude-owned session via `--resume <session_id>` | Rich NDJSON: text deltas, tool_use, tool_result, thinking, result | Maps directly to `status`, `thought`, `tool_use`, `tool_result`, `delta`, `done` |
| **Gemini** | PTY-based persistent interactive CLI in `persistent_gemini.py` | Jane-owned persistent PTY session | Plain text only, no structured tool event schema | Jane emits `delta` from stdout and synthesizes `status` around context build / routing |
| **Codex** | `codex exec --json` / `codex exec resume --json` parsed by `persistent_codex.py` | Codex-owned thread via `thread_id` + `exec resume` | JSONL turn/item events; command execution items, intermediate agent messages, completed final agent message | Maps planning text into `thought`, command execution into `tool_use` / `tool_result`, final agent message into `delta`, then `done` |

Important distinction:
- **Claude** is the richest native stream. Jane can surface true thought/tool events directly.
- **Gemini** is the least structured native stream. Jane preserves the same client contract by wrapping plain-text streaming with Jane-generated progress status events.
- **Codex** sits in between. It exposes structured JSON events, but assistant text currently arrives as completed message items rather than fine-grained token deltas. Jane therefore promotes non-final agent messages into `thought`, surfaces command execution as `tool_use` / `tool_result`, and delivers the final assistant message as message-level `delta` streaming.

This separation is intentional: provider-specific handlers are isolated so changes to Codex streaming do **not** alter Claude's existing streaming path.

### Phase 6: Memory Writeback (async, non-blocking)
- User + assistant turns appended to in-memory history (max 24 turns)
- `_persist_turns_async()` dispatches to background:
  - Writes to conversation database (SQLite ledger)
  - Writes to short-term ChromaDB for future retrieval
  - Updates session summary
- Request timing logged to `jane_request_timing.log`

**Typical latency:** First token in ~500ms, full response P50 = 2.5-3.5s, P95 = 5-8s.

---

## 3. Four-Tier LLM Strategy

| Tier | Role | Models | Use Cases |
|:-----|:-----|:-------|:----------|
| **Orchestrator** | Primary Brain | Opus 4.6, Sonnet 4.6, GPT-4o | Complex reasoning, architecture, coding, high-stakes decisions |
| **Agent** | Specialist | Sonnet 3.5, Gemini 1.5 Pro | Research, complex memory retrieval, multi-step agent tasks |
| **Utility** | Worker | Haiku 4.5, GPT-4o-mini, Flash | Triage, archival, formatting, summarization |
| **Local** | Privacy & Speed | Qwen2.5-coder:14b, Gemma3:4b | Memory librarian synthesis, classification, sensitive data |

**One-subscription-per-provider strategy:** All LLM calls (user-facing and background) go through the provider's CLI binary (`claude`, `codex`, or `gemini`) using the user's existing subscription auth. No separate API keys needed for the primary brain. `JANE_BRAIN` selects the active provider; `SMART_MODEL` and `CHEAP_MODEL` override defaults.

**Intent-to-tier mapping:**
- Gemma3:4b classifies → `greeting`/`simple` → haiku; `medium` → sonnet; `hard` → opus

---

## 4. Memory Architecture (Tiered ChromaDB)

### 4.1 Storage Tiers

| Collection | Path | Contents | TTL |
|:-----------|:-----|:---------|:----|
| `user_memories` | `$VESSENCE_DATA_HOME/vector_db/` | Permanent + long-term Jane memories. `memory_type: "permanent"` or `"long_term"` | None |
| `user_memories` | `$VESSENCE_DATA_HOME/users/<user_id>/memory/vector_db/` | Managed-user private long-term memory, seeded at user creation | None |
| `long_term_knowledge` | `$VESSENCE_DATA_HOME/vector_db/long_term_memory/` | Archivist output: curated high-signal facts promoted from short-term | None |
| `short_term_memory` | `$VESSENCE_DATA_HOME/vector_db/short_term_memory/` | Compact turn summaries + time-limited facts | 14 days |
| `file_index_memories` | `$VESSENCE_DATA_HOME/vector_db/file_index_memory/` | Vault file paths, MIME types, content-derived descriptions | None |

**Routing rule:** Is it a *file* or a *fact*? File → Vault. Fact → ChromaDB.

**Per-essence isolation:** Each essence gets its own ChromaDB instance at `<essence_folder>/knowledge/chromadb/`. When an essence is deleted, its memory can be optionally ported into Jane's universal `user_memories` (re-keyed with source tags).

**Managed-user isolation:** The admin UI can create managed users under `$VESSENCE_DATA_HOME/users/<sanitized_email>/`, where the folder name is derived from the user's login email (for example `person_at_example_com`) and `config.json` stores the raw email. Each managed user gets a config file, a private ChromaDB at `memory/vector_db/`, and a private vault root at `vault/`. When Jane web sees a session for that managed user, context building bypasses the global user/short-term/file-index retrieval lanes and queries that user's private `user_memories` collection instead. Sessions without a managed config keep the legacy shared-memory behavior.

**Vault + capability enforcement (Job #77):** Every `/api/files/*` endpoint resolves the per-request vault root via `_require_capability(session_id, "vault_read" | "vault_write")`. Unmanaged accounts get implicit full access; managed accounts must list the capability in `config.json`. `search_files` additionally filters Chroma description hits by `user_id` metadata, so two users with a same-named file never see each other's description. Writeback through `add_fact.py` accepts `--memory-path` and `--user-id`; upload endpoints pass the managed user's private path so their facts never land in the shared pool. `resolve_conversation_key(request, body)` produces the canonical `<sanitized_user_id>__<device_id>__<client_session_uuid>` key used downstream (deferred wiring into v2/v3 pipeline — currently those still use `scoped_session_id(user_id, sid)`). Phone/SMS endpoints (`/api/contacts*`, `/api/messages*`, `/api/device/sync-sms`) require the `phone` capability. Admin endpoints (`/api/admin/users*`) require `user_admin` or a configured admin email.

### 4.2 Retrieval Optimization

- **Greeting bypass:** Skips memory search for simple greetings or short follow-ups (<20 chars)
- **Fast-pass:** If semantic search returns near-perfect match (distance < 0.35), returns raw fact directly — skips 2-5s librarian synthesis
- **Intent-gated routing:** `file_index_memories` only queried when `_is_file_query()` detects file-related intent
- **Managed-user routing:** `build_jane_context_async(..., user_id=...)` passes managed users into `build_memory_sections(..., user_memory_path=...)`; prewarm and prefetch use the same scoped path.
- **Memory daemon:** Persistent HTTP service on port 8083 for fast (~200ms) memory retrieval; direct ChromaDB fallback if daemon is down

### 4.3 Maintenance Pipeline

- **Thematic Archivist** (Agent tier): Reads full session transcript after each session, synthesizes "Arcs of Lasting Value" using the Sweet 16 categories. Before writing to long-term, fetches 2 nearest neighbors; a Memory Architect decides to MERGE into existing entry or add NEW.
- **Noise pre-filter:** Regex in `conversation_manager.py` kills operational logs before they reach the LLM.
- **Janitor** (`janitor_memory.py`, every 40 min): Purges expired short-term entries, consolidates redundant facts via LLM, clusters vault images, logs to `janitor_consolidation_history.jsonl`.
- **The Sweet 16 Categories:** Identity Evolution, Architectural Milestones, Project State, Debugging Wisdom, Collaborative Habits, Resource Mapping, Tech Stack Fingerprint, Risk & Mitigation, User Eureka Moments, Future Speculations, Aesthetic Preferences, Cross-Agent Coordination, File Anchors, Don't Search List, Symbolic Shorthand, Proven Command Snippets.

---

## 5. Standing Brain Architecture

Three long-lived CLI processes managed by `StandingBrainManager` in `jane/standing_brain.py`:

| Tier | Claude | Gemini | OpenAI |
|:-----|:-------|:-------|:-------|
| Light | haiku-4-5 | flash | gpt-4.1-mini |
| Medium | sonnet-4-6 | pro | gpt-4.1 |
| Heavy | opus-4-6 | pro | o3 |

All overridable via env vars (`BRAIN_LIGHT_*`, `BRAIN_MEDIUM_*`, `BRAIN_HEAVY_*`).

**Lifecycle:**
- Spawned at `jane-web` startup via `_start_standing_brains()`
- System prompt injected on turn 1 only — subsequent turns send raw message (no re-injection overhead)
- **Reaper policy (every 60s):** Dead brains auto-restart. Running brains killed only if BOTH idle (5+ min) AND CPU >15% sustained for 1 hour.
- **Turn rotation:** Forced restart after 20 turns (`MAX_TURNS_BEFORE_REFRESH`) to prevent context staleness.

**Protocol:**
- Claude CLI: stream-JSON (`--input-format stream-json --output-format stream-json`), custom `_read_ndjson_line()` bypasses asyncio 64KB readline limit
- Gemini: PTY-based persistent session (`jane/persistent_gemini.py`), plain text stdin, max 20 concurrent sessions, 30-min idle reap
- OpenAI/Codex standing-brain fallback: Codex CLI command execution path in `standing_brain.py`

**Jane web persistent brain managers:**
- `jane/persistent_claude.py` — Claude-only. Parses `stream-json` NDJSON, preserves Claude session ids, emits `thought`, `tool_use`, `tool_result`, `delta`, `done`.
- `jane/persistent_gemini.py` — Gemini-only. Keeps a PTY subprocess alive and extracts safe text deltas from plain-text output.
- `jane/persistent_codex.py` — Codex-only. Uses `codex exec --json` for first turn and `codex exec resume --json` for follow-up turns. Parses JSONL events:
  - `thread.started` → stores Codex thread id
  - `turn.started` → `status`
  - non-final `agent_message` items → `thought`
  - `item.started` command execution → `tool_use`
  - `item.completed` / `item.failed` command execution → `tool_result`
  - final `agent_message` item → `delta`
  - `turn.completed` → finalizes as `done`

**Compatibility goal:** despite the different provider protocols, the Jane client always consumes the same outward stream vocabulary: `start`, `status`, `delta`, `done`, `error` (plus richer optional events when the provider supports them).

**Brain thoughts** (thinking blocks, tool use) streamed to web UI as status events.

**Claude CLI /tmp cwd:** `ClaudeBrainAdapter` sets `cwd_override = "/tmp"` so the Claude CLI doesn't search upward for CLAUDE.md hooks.

---

## 6. Essence Platform

Essences are pluggable AI personas that run through the platform. Each defines its own knowledge, skills, personality, and UI.

### 6.1 Essence Folder Structure

```
<essence_folder>/
├── manifest.json           # Master configuration
├── personality.md          # LLM system prompt
├── SPEC.md                 # Reference spec document
├── functions/
│   ├── custom_tools.py     # Callable tools
│   └── tool_manifest.json
├── knowledge/
│   └── chromadb/           # Per-essence vector DB
├── ui/
│   ├── layout.json         # UI configuration
│   └── assets/
├── workflows/
│   ├── onboarding.json
│   └── sequences/
├── working_files/          # Temporary files
├── user_data/              # Accumulated user data
└── essence_data/           # Pre-loaded knowledge
```

### 6.2 Manifest Format

Required fields: `essence_name`, `role_title`, `version`, `author`, `description`, `preferred_model` (`model_id` + `reasoning`), `permissions`, `capabilities` (`provides` + `consumes`), `ui` (`type`), `shared_skills`.

Key manifest properties:
- `has_brain: true/false` — Whether essence has its own LLM brain
- `capabilities.provides` — What this essence offers (e.g., `["tax_calculation", "form_generation"]`)
- `capabilities.consumes` — What it needs from other essences
- `ui.type` — `chat`, `card_grid`, `form_wizard`, `dashboard`, `hybrid`
- `interaction_patterns.proactive_triggers` — Cron-based autonomous actions

### 6.3 Lifecycle

1. **Build** (`agent_skills/essence_builder.py`): 12-section guided interview → spec → `build_essence_from_spec()` scaffolds folder
2. **Validate** (`agent_skills/validate_essence.py`): Schema checks on manifest, required dirs/files
3. **Load** (`agent_skills/essence_loader.py`): Validates manifest, reads personality.md, initializes per-essence ChromaDB, returns `EssenceState`
4. **Auto-load at startup:** `_auto_load_essences()` scans `ESSENCES_DIR`, loads all valid essences
5. **Activate:** `POST /api/essences/{name}/activate` sets as active; personality injected into context builder
6. **Execute:** Tools callable via `POST /api/essence/{name}/tool/{tool_name}`; UI served at `GET /essence/{name}`
7. **Unload/Delete:** Unload removes from memory. Delete permanently removes files + optionally ports memory into Jane's universal collection.

### 6.4 Orchestration Modes

**Mode A (Top-Down):** Jane as PM. `JaneOrchestrator.decompose_task()` breaks user request into subtasks, maps each to an essence by capability keyword matching + role/description scoring. Jane dispatches, aggregates, may call on one essence to produce final product.

**Mode C (Collaborative / Peer-to-Peer):** `CapabilityRegistry` manages a live map of `capability → [provider essences]`. Essences can `request_service(capability, payload)` from peers. Platform auto-wires based on declared capabilities. Self-request protection built in.

User chooses mode, or Jane suggests based on task complexity.

### 6.5 Essence Scheduling

`agent_skills/essence_scheduler.py` runs every minute via cron. Each essence can declare jobs in `<essence_folder>/cron/jobs.json`. Supports cron expressions, idle-only gating, 600s timeout, duplicate prevention.

### 6.6 Current Essences

| Essence | Location | Description |
|:--------|:---------|:------------|
| Tax Accountant 2025 | `~/ambient/essences/tax_accountant_2025/` | Tax interview, document parsing, calculation, form generation. Model: opus-4-6. UI: interview_wizard. |
| Work Log | `~/ambient/essences/work_log/` | Activity tracking and logging |

**Display order:** Jane is always #1, Work Log is always last. Others alphabetically between.

---

## 7. Claude Code Hook System

When Jane runs as a Claude Code session (CLI), hooks inject context and gate tool usage. Registered in `~/.claude/settings.json`.

### 7.1 UserPromptSubmit Hooks (every prompt)

| Hook | File | Purpose |
|:-----|:-----|:--------|
| `claude_smart_context.py` | `startup_code/` | Classifies prompt intent via `_classify_prompt_profile()`, injects only needed context sections (800-2000 tokens vs. 25,000 before). Replaced 3 legacy hooks. |
| `memory_hook.sh` | `~/.claude/hooks/` | Queries ChromaDB via daemon (port 8083, ~0.5s) or subprocess fallback (~3s). Skips short anaphoric prompts (≤8 words with pronouns). Deduplicates across session. |
| `jane_context_hook.sh` | `~/.claude/hooks/` | Injects precomputed `jane_context.txt` (rebuilt nightly at 3:15 AM by `regenerate_jane_context.py`) |
| `identity_hook.sh` | `~/.claude/hooks/` | Injects compact Jane/user identity from `jane_identity_compact.md` (rebuilt at 3:00 AM) |
| `prompt_queue_hook.sh` | `~/.claude/hooks/` | Processes next item from prompt queue if active |
| `idle_state_hook.sh` | `~/.claude/hooks/` | Idle detection and state management |

### 7.2 PreToolUse Hooks

| Hook | Matcher | Purpose |
|:-----|:--------|:--------|
| `read_discipline_hook.py` | Read, Edit, Grep, Glob, Agent | Enforces efficient file access: warns on large-file-first reads (>200 lines without prior search), code-map-first gaps, re-reads (3+ times same file). State in `/tmp/claude-read-discipline/`. |
| `check_system_load.sh` | Bash, Agent | Gates execution based on CPU/memory load |

### 7.3 Stop Hook

| Hook | Purpose |
|:-----|:--------|
| `context_summary_hook.sh` | Saves conversation summary on session end |

### 7.4 Web Permission Gate

For Jane web UI sessions (`JANE_WEB_PERMISSIONS=1`):
- `jane/hooks/permission_gate.py` — PreToolUse hook in CLI subprocess
- Tools requiring approval: Bash, Write, Edit, NotebookEdit
- Read-only bash commands auto-approved; dangerous patterns (`rm -rf`, `git push --force`, `DROP TABLE`) always flagged
- Flow: CLI tool call → hook fires → HTTP POST to `permission_broker.py` → SSE event → web UI dialog → user approve/deny → hook unblocks
- 5-minute timeout → auto-deny. Fail-open if web server unreachable.

### 7.5 OpenAI Codex CLI Memory Bridge

OpenAI Codex CLI does not use Claude Code's `UserPromptSubmit`,
`PreToolUse`, `PostToolUse`, or `Stop` hook stack on this machine. To keep
Codex Jane connected to live memory, Codex is configured with a local stdio
MCP server:

- **Server name:** `jane-memory`
- **File:** `startup_code/codex_memory_mcp.py`
- **Tools:** `query_jane_memory(query, max_chars=12000)`, `jane_memory_paths()`
- **Retrieval backend:** `memory.v1.memory_retrieval.build_memory_sections()`
  against `$VESSENCE_DATA_HOME/vector_db`

This is not a true automatic prompt hook: Codex must call the MCP tool before
answering memory-sensitive prompts. The Codex runtime rules in `AGENTS.md`
therefore require explicit ChromaDB lookup for prompts involving "remember",
"recently", prior decisions, project history, preferences, personal/family
context, or architecture/debugging rationale. Current runtime behavior still
requires code/log verification after memory recall.

---

## 8. Web Server & API (`jane_web/main.py`, port 8081)

FastAPI server (~3500 lines) serving all routes. Vault web (port 8080) functionality consolidated into jane_web.

### 8.1 Route Groups

**Chat & Brain**
- `POST /api/jane/chat` — Sync chat
- `POST /api/jane/chat/stream` — Streaming chat (primary)
- `POST /api/jane/init-session` — Initialize session
- `POST /api/jane/session/end` — End session
- `GET /api/jane/live` — SSE for real-time updates
- `POST /api/jane/switch-provider` — Switch LLM provider at runtime
- `GET /api/jane/current-provider` — Active provider + model + alive status
- `POST /api/jane/prefetch-memory` — Pre-load memories for faster context
- `GET /api/jane/announcements` — System announcements

**Authentication**
- `POST /api/auth/google-token` — Exchange Google OAuth token
- `GET /auth/google` / `GET /auth/google/callback` — OAuth flow
- `POST /api/auth/check` — Verify session
- `POST /api/auth/verify-otp` — OTP login
- `POST /api/auth/logout` — Revoke session
- `GET /api/auth/devices` — Trusted devices
- `DELETE /api/auth/devices/{id}` — Revoke device

**Vault & Files**
- `GET /api/files` — List root vault directory
- `GET /api/files/list/{path}` — List directory (paginated)
- `GET /api/files/serve/{path}` — Serve file (Range request support)
- `POST /api/files/upload` — Batch upload
- `GET /api/files/search` — Full-text search
- `GET /api/files/find` — Fuzzy name search
- `PATCH /api/files/description/{path}` — Update file description/tags

**Essences**
- `GET /api/essences` — List all (type filter: all/active/inactive)
- `GET /api/essences/active` — Currently active essence
- `POST /api/essences/{name}/load` / `unload` / `activate` — Lifecycle
- `DELETE /api/essences/{name}` — Delete (optional memory porting)
- `POST /api/essence/{name}/tool/{tool_name}` — Invoke essence tool
- `GET /essence/{name}` — Serve essence UI page
- `GET /api/essences/capabilities` — Capability → essence map

**Briefing (News)**
- `GET /api/briefing/articles` — List articles (topic/category filter)
- `GET /api/briefing/article/{id}` — Article detail
- `GET /api/briefing/audio/{id}/{type}` — TTS for article
- `POST /api/briefing/fetch` — Trigger immediate fetch
- `GET /api/briefing/search` — Semantic search via ChromaDB
- `GET/POST/PUT/DELETE /api/briefing/topics[/{name}]` — List / add / rename-or-edit / remove tracked topics (UI: Topics Modal on `/briefing` with per-row inline edit)

**Facebook Marketplace**
- `GET/POST /api/marketplace/searches` — List / create saved-search bundles
- `GET/DELETE /api/marketplace/search/{name}` — Detail + flat listings / remove
- `GET /api/marketplace/listing/{name}/{slug}/{id}` — Full listing (description, photos[])
- `GET /api/marketplace/summary/{name}` — Stage-2 LLM (qwen2.5:7b) brief written by `summarize.py`
- `GET/POST /api/marketplace/refresh/{name}` — Poll status / spawn background harvest+summarize subprocess
- `GET /marketplace-image/{name}/{slug}/{id}/{photo_name}` — Serve saved photo
- Harvester module: `agent_skills/marketplace/` — `harvester` (Playwright), `summarize` (Ollama), `refresh` (background runner with pid-alive status file); uses stored `facebook_julius` browser profile so no 2FA
- Cron: `startup_code/run_marketplace_cron.sh` at 2am daily (headless-forced)
- UI: third pill ("Marketplace") on `/briefing` — saved-search grid → listings grid + AI summary panel → single-listing detail with photo gallery; per-card Pull-now / Edit / Delete + header-bar Pull-now / Edit; shared editor modal for create + edit

**Tax Accountant**
- `POST /api/tax/interview/start` / `answer` — Guided interview
- `POST /api/tax/calculate` — Compute taxes
- `POST /api/tax/generate` — Generate form PDFs
- `POST /api/tax/upload` — Upload documents

**Settings & Configuration**
- `GET/PUT /api/app/settings` — User preferences
- `GET/POST /api/settings/models` — LLM model config
- `GET/POST /api/settings/personality` — Jane personality selection

**Permission System**
- `POST /api/jane/permission/request` — Request tool approval
- `POST /api/jane/permission/respond` — Approve/deny
- `GET /api/jane/permission/pending` — Pending requests

**TTS, Downloads, Shares, Playlists**
- `POST /api/tts/generate` — Text-to-speech
- `GET /downloads/{filename}` — Release artifacts
- `GET/POST/DELETE /api/shares` — Public share links
- `GET/POST/PUT/DELETE /api/playlists` — Audio playlists

**Web UI Pages** (server-rendered HTML)
- `/` — Main chat UI
- `/chat`, `/vault`, `/essences`, `/worklog`, `/briefing`, `/guide`, `/architecture`
- `/manifest.webmanifest`, `/sw.js` — PWA support

### 8.2 Stderr Error Detection & Provider Switching

Background asyncio task monitors CLI stderr for rate-limit/billing/quota errors across all 3 providers. On detection:
1. `provider_error` SSE event emitted to frontend
2. Frontend shows colored switch buttons (Claude=violet, Gemini=blue, OpenAI=emerald)
3. `POST /api/jane/switch-provider` kills current CLI, installs new CLI if needed, spawns new process, persists to `.env`

---

## 9. Automation & Cron System

18 active cron jobs + essence scheduler. All execute via `/home/chieh/google-adk-env/adk-venv/bin/python`. Automation tasks that need LLM use `jane/automation_runner.py` which routes to the appropriate CLI binary.

### 9.1 Job Schedule

| Schedule | Job | File | Purpose |
|:---------|:----|:-----|:--------|
| `* * * * *` | Essence Scheduler | `essence_scheduler.py` | Check for due essence tasks |
| `*/5 * * * *` | Job Queue Runner | `job_queue_runner.py` | Process pending jobs from `configs/job_queue/` |
| `*/30 * * * *` | Screen Dimmer | `screen_dimmer.py` | Dim display after sunset (zip 02155) |
| `*/40 * * * *` | Memory Janitor | `janitor_memory.py` | Purge expired, consolidate redundant, cluster images |
| `0 */6 * * *` | Nightly Audit | `nightly_audit.py` | Code vs. docs drift detection, auto-fix safe issues |
| `0 2 * * *` | USB Backup | `usb_sync.py` | Incremental rsync, weekly hard-link snapshots (30-day retention) |
| `0 2 * * *` | Audit Auto-Fixer | `audit_auto_fixer.py` | Apply safe fixes from audit |
| `10 2 * * *` | Daily Briefing | `run_briefing.py` | Fetch news, summarize (gemma3:12b), TTS via XTTS |
| `10 2 * * *` | Code Map Keywords | `evolve_code_map_keywords.py` | Extract code keywords from messages, update proxy |
| `30 2 * * *` | Update Checker | `check_for_updates.py` | Check for codebase/dependency updates |
| `0 3 * * *` | Identity Essay | `generate_identity_essay.py` | Regenerate Jane identity from recent interactions |
| `0 3 * * *` | System Janitor | `janitor_system.py` | Temp cleanup, log rotation (2-day retention) |
| `15 3 * * *` | Jane Context Rebuild | `regenerate_jane_context.py` | Rebuild `jane_context.txt` from source configs |
| `15 4 * * *` | Code Map Generator | `generate_code_map.py` | Regenerate CODE_MAP_CORE/WEB/ANDROID with line numbers |
| `0 5 * * *` | Ambient Heartbeat | `ambient_heartbeat.py` | Autonomous research: search 9 topics, implement up to 3 tasks |
| `0 10 * * *` | Update Notifier | `notify_updates.py` | Notify user of available updates |

### 9.2 Automation Runner (`jane/automation_runner.py`)

Central dispatch for cron and queue jobs:
- Reads `$AUTOMATION_CLI_PROVIDER` (falls back to `$JANE_BRAIN`)
- Codex/Claude Code: runs prompt via CLI with `--dangerously-bypass-approvals-and-sandbox`
- Other providers: uses `brain_adapters.py`
- Timeout resolution per provider

### 9.3 Archival Pipeline

Conversation turns flow through a triage pipeline:
1. **ConversationManager** (`agent_skills/conversation_manager.py`) detects idle (60s before noon, 1h after noon)
2. Archivist LLM reads session transcript, applies Sweet 16 categories
3. Decisions: **Keep** → promoted to `long_term_knowledge`; **Short-Term** → stamped with `expires_at`; **Discard** → deleted; **Timeout/Error** → left for retry
4. Before promoting, Memory Architect checks 2 nearest neighbors → MERGE or NEW
5. Janitor (`janitor_memory.py`, every 40 min) consolidates further

---

## 10. Android App (Native Kotlin)

**Location:** `android/` (native Kotlin/Jetpack Compose; Flutter prototype at `/home/chieh/projects/ambient/` was deleted)

### 10.1 Architecture

- **Language:** Kotlin, targeting SDK 35 (min SDK 26)
- **UI framework:** Jetpack Compose (Material 3)
- **State management:** MVVM — ViewModels with `StateFlow` → Composables with `collectAsState()`
- **Networking:** OkHttpClient + Retrofit (Gson converter), persistent cookie jar
- **Auth:** OTP code login → session cookie stored in `CookieStore` (SharedPreferences-backed)
- **Local storage:** SharedPreferences for settings, session IDs, voice config. Chat persistence via `ChatPersistence` (JSON file-based).
- **Image loading:** Coil

### 10.2 Key Components

| Component | File | Purpose |
|:----------|:-----|:--------|
| Entry point | `MainActivity.kt` | Single-activity architecture, Compose navigation, wake word intent handling |
| Application | `VessencesApp.kt` | App-level init |
| API Client | `data/api/ApiClient.kt` | Singleton OkHttpClient, Retrofit instances (vault + jane), cookie management |
| Chat Screen | `ui/chat/ChatScreen.kt` | Main chat UI: message list, input row, voice status banner, attachment sheet |
| Chat ViewModel | `ui/chat/ChatViewModel.kt` | Core chat logic: streaming, TTS, STT (SpeechRecognizer), wake word bridge, message queue |
| Chat Repository | `data/repository/ChatRepository.kt` | NDJSON streaming via OkHttp `POST /api/jane/chat/stream` |
| Login | `ui/auth/LoginScreen.kt` + `LoginViewModel.kt` | OTP auth flow |
| Settings | `ui/settings/SettingsScreen.kt` + `SettingsViewModel.kt` | Theme, always-listening toggle, wake word threshold, trusted devices, shares |
| Vault | `ui/vault/VaultScreen.kt` + `VaultViewModel.kt` | File browser for server vault |
| Briefing | `ui/briefing/BriefingScreen.kt` + `BriefingViewModel.kt` | News articles with TTS audio playback |
| Music | `ui/music/MusicScreen.kt` + `MusicViewModel.kt` | Playlist browser, Media3 playback service |
| Essences | `ui/essences/EssencesScreen.kt` + `EssencesViewModel.kt` | Essence list, load/activate |
| Markdown | `ui/components/MarkdownText.kt` | CommonMark rendering in chat bubbles |
| Update Checker | `data/api/UpdateChecker.kt` | Version check via `/api/app/latest-version`, DownloadManager-based install |
| Crash Reporter | `CrashReporter.kt` | Uncaught exception → POST to `/api/crash-report` |
| Diagnostic Reporter | `DiagnosticReporter.kt` | Fire-and-forget diagnostics → POST to `/api/device-diagnostics` (uses raw `HttpURLConnection`, not `ApiClient`) |

### 10.3 Voice & Wake Word System

| Component | File | Purpose |
|:----------|:-----|:--------|
| AlwaysListeningService | `voice/AlwaysListeningService.kt` | Foreground service with wake lock. Runs OpenWakeWord detector on mic audio. On detection: vibrates, wakes screen, signals bridge, launches activity. Sends periodic heartbeat diagnostics. |
| OpenWakeWordDetector | `voice/OpenWakeWordDetector.kt` | ONNX Runtime pipeline: raw PCM → mel spectrogram → audio embeddings → wake word classifier. Current model is `openwakeword/hey_jane.onnx`, the April 19 v8-era classifier. Runtime threshold defaults to `Constants.DEFAULT_WAKE_WORD_THRESHOLD = 0.8f`; the service requires 5 consecutive above-threshold frames before triggering. |
| WakeWordBridge | `voice/WakeWordBridge.kt` | Singleton bridge between service and ChatViewModel. `activated` StateFlow signals wake word detection. `sttActive` flag keeps service paused while conversation is ongoing. |
| VoiceController | `voice/VoiceController.kt` | Vosk-based offline STT (fallback for SpeechRecognizer) |
| AndroidTtsManager | `voice/AndroidTtsManager.kt` | Kotlin coroutine wrapper around Android TTS engine |
| VoiceSettingsRepository | `data/repository/VoiceSettingsRepository.kt` | SharedPreferences for always-listening enabled, trigger phrase, threshold, trained state |

**Wake word flow:**
1. `AlwaysListeningService` detects wake word → **stops itself** (releases mic cleanly) → vibrates → wakes screen → `WakeWordBridge.signal()` → launches MainActivity
2. `ChatViewModel` collects `WakeWordBridge.activated` → waits 1.5s for activity to settle → launches system STT via `ChatInputRow` (same path as mic button tap)
3. `WakeWordBridge.sttActive = true` keeps service stopped for entire conversation
4. User speaks → `SpeechRecognizer.onResults` → `sendMessage(fromVoice=true)` → Jane streams response → TTS → auto-listen → repeat
5. Conversation ends (STT timeout / no speech) → `sttActive = false` → service restarts wake word detection

#### Wake Word Model Provenance: `hey_jane.onnx` v8-era Model

The deployed `android/app/src/main/assets/openwakeword/hey_jane.onnx` is not the v7 backup. It was overwritten by a later OpenWakeWord training run on 2026-04-19 and then packaged into the Android release assets.

Evidence:
- Active source asset: `android/app/src/main/assets/openwakeword/hey_jane.onnx`
  - timestamp: `2026-04-19 21:24:10 -0400`
  - size: `2,398,347` bytes
  - SHA-256: `aa46e37a850fdb10433c35a26b058c97a57d737ee163d2d36b9a3d6b12d5d3bf`
- Release merged asset has the same SHA-256, so the packaged release asset matches the source asset.
- v7 backup: `android/app/src/main/assets/openwakeword/hey_jane_v7_backup.onnx`
  - timestamp: `2026-04-19 14:12:24 -0400`
  - SHA-256: `dc982a383d31c6bf865adff3099ff814375362bdbbd14a9d25c9ad499154049a`
- Git provenance: commit `42ffbcad03f80478a23a8f43f99ff824bc4baf31` modified `hey_jane.onnx`, added `hey_jane_v7_backup.onnx`, added `wake_word/TRAINING.md`, and modified `wake_word/train_oww.py`.
- Run provenance: `/tmp/train_v8.log`, timestamp `2026-04-19 21:28:28 -0400`, records the training run that saved to `.../android/app/src/main/assets/openwakeword/hey_jane.onnx`.

Training process from `/tmp/train_v8.log`:
- Trainer banner: `OpenWakeWord 'hey jane' classifier training v3`; source-disjoint splits, temporal jitter, reviewed fixes.
- Positives:
  - `23` real recordings from `wake_word/samples/hey_jane_*.ogg`.
  - `47` English `edge-tts` voices.
  - `188` synthetic positive clips generated from four phrase capitalizations.
  - `211` total positive sources.
  - `2,635` positive clips before temporal jitter.
- Negatives:
  - hard TTS confusables and general voice-assistant/background-speech phrases generated with the same `47` English voices.
  - `2,489` valid hard-negative TTS clips and `1,596` valid general-negative TTS clips.
  - `4,085` TTS negative sources.
  - `35,785` total negative sources including disk negatives.
  - `79,840` total negative clips.
- Split:
  - train sources: `169` positive, `28,668` negative.
  - validation sources: `42` positive, `7,167` negative.
  - source-disjoint split prevents augmented copies of the same source from crossing train/validation.
- Feature extraction:
  - train features: `12,198` positive, `127,856` negative.
  - validation features: `602` positive, `15,912` negative.
  - features are OpenWakeWord embedding windows shaped `(16, 96)`.
- Training:
  - DNN classifier trained on CPU; the run's stage label says `Training DNN classifier (with hard negative mining)`.
  - epoch 0: `P=0.3719 R=0.9817 F1=0.5395 FPR=0.0627`.
  - epoch 40: `P=0.8151 R=0.9518 F1=0.8782 FPR=0.0082`.
  - epoch 80: `P=0.8589 R=0.9302 F1=0.8931 FPR=0.0058`.
  - epoch 200: `P=0.8422 R=0.9485 F1=0.8922 FPR=0.0067`.
  - early stopped at epoch `229`; best F1 during training was `0.9161`.
- Final validation thresholds:
  - `thr=0.3`: `P=0.8754 R=0.9568 F1=0.9143 FPR=0.0052`
  - `thr=0.4`: `P=0.8806 R=0.9551 F1=0.9163 FPR=0.0049`
  - `thr=0.5`: `P=0.8829 R=0.9518 F1=0.9161 FPR=0.0048`
  - `thr=0.6`: `P=0.8882 R=0.9502 F1=0.9181 FPR=0.0045`
  - `thr=0.7`: `P=0.8910 R=0.9369 F1=0.9134 FPR=0.0043`
- Export:
  - ONNX opset 18.
  - weights inlined; stale `.onnx.data` sidecar removed.
  - ONNX vs PyTorch max diff: `0.00000042`.
  - output size: `2,398,347` bytes (`2342.1 KB`).
- Verification:
  - all 23 real recordings scored `0.9984` to `0.9997`.
  - Speech Commands false positives: `0/500 (0.0%)` at the script's verification threshold.
  - silence: `0.0000`; random noise: `0.0000`.

Operational note: v8 validation metrics were reported for thresholds `0.3` through `0.7`, but Android currently defaults to `0.8` and also requires 5 consecutive detections. If "Hey Jane" misses in background speech or noisy rooms while logs show near-miss scores below `0.8`, investigate threshold/confirmation policy before assuming the model file is wrong.

### 10.4 Streaming Protocol

NDJSON over HTTP (same as web):
```json
{"type": "status", "data": "Loading memory..."}
{"type": "thought", "data": "thinking text"}
{"type": "tool_use", "data": {"tool": "name", "input": "..."}}
{"type": "tool_result", "data": "result text"}
{"type": "delta", "data": "token"}
{"type": "done", "data": "full response"}
{"type": "error", "data": "error message"}
```

Parsed by `util/NdjsonParser.kt`. Thoughts and tool events rendered inline in chat bubbles.

### 10.5 Version Management

Single source of truth: `version.json` at repo root (`version_code` + `version_name`).
- `android/app/build.gradle.kts` reads `version.json` at build time
- `jane_web/main.py` reads `version.json` for `/api/app/latest-version` endpoint
- `configs/CHANGELOG.md` must have a matching `## v{version_name}` entry (enforced by Gradle build check)
- APK deployed to `marketing_site/downloads/vessences-android-v{version_name}.apk`

### 10.6 Key Behaviors

- **Shared Jane session:** `ChatPreferences.getJaneSessionId()` returns a persistent session ID stored in SharedPreferences. Same session used by wake word and manual chat.
- **Auto-listen after TTS:** When enabled, `onSendComplete()` speaks Jane's reply via TTS, then auto-starts SpeechRecognizer for the next user utterance.
- **Screen wake:** Wake word detection from screen-off uses `FULL_WAKE_LOCK + ACQUIRE_CAUSES_WAKEUP`, `setShowWhenLocked(true)`, `setTurnScreenOn(true)`, and keyguard dismissal.
- **Battery optimization:** Requests `ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` when always-listening is enabled.

---

## 11. Docker Deployment

### 11.1 Services

| Service | Port | Image Size | Purpose |
|:--------|:-----|:-----------|:--------|
| jane | 8090 | 770 MB | FastAPI + CLI-at-boot |
| onboarding | 3000 | 139 MB (Alpine) | First-run wizard |
| chromadb | 8000 | (Docker Hub) | Vector database |

**Total download:** ~210 MB (was 1.3 GB). Amber service removed — essences run through Jane's standing brain.

### 11.2 CLI Installation

Jane image bakes in 3 CLIs: `@google/gemini-cli`, `@anthropic-ai/claude-code`, OpenAI Codex. `JANE_BRAIN` env var selects which is active. `install_brain.sh` handles first-boot installation.

### 11.3 Networking

- **Traefik:** `jane.localhost` / `vault.localhost` both route to `jane:8081` (unified since v0.1.71; vault service retired).
- **Cloudflare:** Named tunnel (token in `.env`) or quick-tunnel fallback. Opt-in: `docker compose --profile cloudflare up`

### 11.4 Onboarding

First-run wizard at `localhost:3000`: system check → setup form → identity interview → writes `.env` and `user_profile.md`.

### 11.5 CI/CD

`.github/workflows/docker-publish.yml` builds all images on push to main, pushes to Docker Hub with semver + sha tags. Multi-platform: linux/amd64 + linux/arm64.

---

## 12. Directory Layout

### 12.1 Root Paths

| Path | Env Var | Purpose |
|:-----|:--------|:--------|
| `~/ambient/` | `AMBIENT_BASE` | Project root |
| `~/ambient/vessence/` | `VESSENCE_HOME` | Code repository (git-tracked) |
| `~/ambient/vessence-data/` | `VESSENCE_DATA_HOME` | Runtime data, logs, credentials, vector DBs (not git-tracked) |
| `~/ambient/vault/` | `VAULT_HOME` | User files (PDFs, images, audio, documents) |
| `~/ambient/essences/` | `ESSENCES_DIR` | Essence definitions |
| `~/ambient/skills/` | `SKILLS_DIR` | Skill implementations |

### 12.2 Code Repository (`VESSENCE_HOME`)

```
vessence/
├── jane/                    # Core Jane agent logic
│   ├── config.py            # Central config (100+ constants)
│   ├── standing_brain.py    # Persistent CLI process manager
│   ├── brain_adapters.py    # Provider adapters (Claude/Gemini/OpenAI)
│   ├── context_builder.py   # Context assembly & prompt profiling
│   ├── persistent_gemini.py # PTY-based Gemini session manager
│   ├── persistent_codex.py  # Codex JSONL session manager
│   ├── automation_runner.py # Cron/queue task dispatch
│   ├── task_spine.py        # Task graph & interrupt stack
│   ├── research_router.py   # Research offload via Ollama
│   ├── session_summary.py   # Session archival
│   ├── tts.py               # Text-to-speech
│   └── hooks/               # Permission gate, policy
│       ├── permission_gate.py
│       └── permission_policy.json
├── jane_web/                # FastAPI web server
│   ├── main.py              # All routes (~3500 lines)
│   ├── jane_proxy.py        # Brain proxy & streaming
│   ├── broadcast.py         # SSE broadcasting
│   ├── permission_broker.py # Tool approval coordinator
│   ├── task_classifier.py   # Big-task detection
│   └── task_offloader.py    # Background queue
├── agent_skills/            # 50+ executable skills
│   ├── conversation_manager.py  # Session management & archival
│   ├── memory_retrieval.py      # ChromaDB semantic search daemon
│   ├── essence_builder.py       # Essence interview system
│   ├── essence_runtime.py       # Runtime & orchestration
│   ├── essence_loader.py        # Load/unload/validate
│   ├── essence_scheduler.py     # Essence cron dispatch
│   ├── janitor_memory.py        # Memory maintenance
│   ├── janitor_system.py        # System cleanup
│   ├── nightly_audit.py         # Code vs. docs audit
│   ├── job_queue_runner.py      # Job queue processor
│   ├── prompt_queue_runner.py   # Prompt queue processor
│   └── ...
├── configs/                 # Architecture docs, templates, job queue
│   ├── Jane_architecture.md     # This file
│   ├── memory_manage_architecture.md
│   ├── SKILLS_REGISTRY.md
│   ├── CRON_JOBS.md
│   ├── TODO_PROJECTS.md
│   ├── CHANGELOG.md
│   ├── job_queue/               # Pending/completed job specs
│   ├── personalities/           # Personality presets
│   ├── nginx/                   # Reverse proxy config
│   ├── systemd/                 # Service definitions
│   └── templates/               # Essence template
├── vault_web/               # Vault UI (shared with jane_web)
│   ├── auth.py                  # Multi-user auth
│   └── templates/               # HTML templates
├── startup_code/            # Bootstrap scripts
│   ├── claude_smart_context.py  # Hook: smart context injection
│   ├── regenerate_jane_context.py
│   ├── build_docker_bundle.py
│   ├── usb_sync.py
│   └── bot_watchdog.sh
├── android/                 # Native Kotlin/Compose Android app (see §10)
├── relay_server/            # Multi-user tunnel relay (port 8082) + WebSocket router
├── marketing_site/          # Public landing page
├── onboarding/              # First-run wizard
├── docker/                  # Docker build files
└── .env.example             # Template env vars
```

### 12.3 Runtime Data (`VESSENCE_DATA_HOME`)

```
vessence-data/
├── .env                     # Active configuration (secrets)
├── data/
│   ├── task_spine.json          # Active task graph
│   ├── interrupt_stack.json     # Paused tasks
│   ├── current_task_state.json  # Current project state
│   ├── active_essence.json      # Currently loaded essence
│   ├── user_profile_facts.json  # Personal facts
│   ├── preference_registry.json # Enforced preferences
│   └── jane_identity_compact.md # Identity essay
├── vector_db/               # ChromaDB collections
│   ├── (user_memories)
│   ├── short_term_memory/
│   ├── long_term_memory/
│   └── file_index_memory/
├── logs/                    # All log files
│   ├── jane_request_timing.log
│   ├── jane_web.log
│   ├── audits/
│   └── ...
├── credentials/             # API keys, tokens
└── users/                   # Per-user config directories
    └── <user_id>/config.json
```

---

## 13. Configuration Reference

### 13.1 Config Cascade

```
.env (VESSENCE_DATA_HOME/.env)
    ↓ load_dotenv()
jane/config.py (resolves paths, exports 100+ constants)
    ↓ import
All modules
```

`jane/config.py` is the single source of truth. All scripts import from it. `llm_config.py` re-exports LLM constants for backward compatibility.

### 13.2 Key Environment Variables

| Category | Variable | Default | Purpose |
|:---------|:---------|:--------|:--------|
| **Paths** | `AMBIENT_BASE` | `~/ambient/` | Project root |
| | `VESSENCE_HOME` | `{AMBIENT_BASE}/vessence` | Code repo |
| | `VESSENCE_DATA_HOME` | `{AMBIENT_BASE}/vessence-data` | Runtime data |
| | `VAULT_HOME` | `{AMBIENT_BASE}/vault` | User files |
| **Provider** | `JANE_BRAIN` | `gemini` | Active provider: `gemini`/`claude`/`openai` |
| | `SMART_MODEL` | (per provider) | User-facing model override |
| | `CHEAP_MODEL` | (per provider) | Background model override |
| | `AUTOMATION_CLI_PROVIDER` | (from JANE_BRAIN) | Cron job provider |
| **Auth** | `GOOGLE_API_KEY` | (required) | Gemini API key |
| | `GOOGLE_CLIENT_ID` / `SECRET` | (optional) | OAuth |
| | `ALLOWED_GOOGLE_EMAILS` | (optional) | Comma-separated allowlist |
| | `SESSION_SECRET_KEY` | (auto-generated) | Session cookie key |
| **Memory** | `SHORT_TERM_TTL_DAYS` | `14` | Short-term memory expiration |
| | `CHROMA_SEARCH_LIMIT` | `10` | Semantic search results |
| | `CONTEXT_COMPACTION_RATIO` | `0.65` | Compact at 65% of max window |
| **Features** | `JANE_WEB_PERMISSIONS` | `0` | Enable tool approval UI |
| | `USER_NAME` | `the user` | Personalization |
| **Infra** | `CHROMA_HOST` | (empty local, `chromadb` Docker) | ChromaDB host |
| | `CLOUDFLARE_TUNNEL_TOKEN` | (optional) | Public URL |

### 13.3 Personal Name Portability

All hardcoded name references in agent prompts replaced with `os.environ.get('USER_NAME', 'the user')`. Set `USER_NAME` in `.env` at onboarding.

---

## 14. Multi-User Support

- `ALLOWED_GOOGLE_EMAILS` supports comma-separated emails
- Each email gets its own session with `user_id` derived from email
- Per-user directory at `$VESSENCE_DATA_HOME/users/<user_id>/config.json` (display_name, personality, memory_namespace)
- `agent_skills/user_manager.py` provides `get_user_config()`, `create_user_space()`, `set_user_personality()`, `list_personalities()`
- Personality presets in `configs/personalities/`: `default.md`, `professional.md`, `casual.md`, `technical.md`
- Settings UI: personality dropdown per user

---

## 15. Communication Channels

- **Primary:** Vessence Android app — native chat, voice (mic + TTS), wake word, file attachments, vault browser
- **Web:** `jane.vessences.com` (port 8081) — full-featured chat + vault + essences + thought process display
- **CLI:** Claude Code with hooks — developer workflow
- Discord bridge retired (2026-03-21). All communication through Vessence app or web.

---

## 16. Component Hardening

- **Persistent Gemini session:** PTY subprocess avoids cold starts. Gated by `JANE_WEB_PERSISTENT_GEMINI` env var.
- **Wrapper log writeback:** Async queue + background thread for PTY transcript logging (no sync I/O on event loop).
- **PTY echo disabled:** `termios` prevents double-input display.
- **Swappable brains:** `jane_proxy.py` routes through shared context builder + pluggable CLI adapters.
- **Research token conservation:** Web search results synthesized by local Ollama model instead of main brain.
- **Single in-progress bubble:** One assistant bubble while thinking; status updates rendered inside same bubble.
- **Watchdog restart policy:** Requires repeated failed probes + cooldown to prevent false restarts.
- **Background task wrapper:** `agent_skills/claude_cli_llm.py` provides `completion()`, `completion_smart()`, `completion_json()` — routes to correct CLI based on `JANE_BRAIN`.
- **Task spine enforcement:** Persistent `task_spine.json` + `interrupt_stack.json` for pausing/resuming long-running work.

### 16.1 Per-class Privacy + Routing Flags

Two optional fields in a class's `metadata.py` `METADATA` dict control cloud exposure:

| Flag | Values | Effect |
|------|--------|--------|
| `no_stage3` | `True` / unset | Never escalates to Stage 3 (cloud brain). Stage 2 handler IS the final answer-giver. On handler crash / invalid shape / explicit escalation request / wrong_class, the pipeline substitutes a safe class-agnostic deflection (`SAFE_CLINIC_DEFLECTION`) and returns as a Stage 2 success. |
| `privacy` | `"local_only"` / unset | Content must never leave the local process. Cloud-bound FIFO reads (Stage 3 transcript, Opus ack) project the turn as `[private turn — class: <name>]`; the persistence worker unconditionally skips Haiku thematic memory + session summary for this turn, independent of stage. FIFO itself stores the full turn (Stage 2 is entirely local — classifier, resolver, and handlers need the real content to resume follow-up flows). |

Enforcement layers (in `jane_web/jane_v2/pipeline.py` + `jane_web/jane_v2/recent_context.py` + `jane_web/jane_v3/pipeline.py` + `jane_web/jane_proxy.py`):
1. **Stage 3 guard** (both v2 non-streaming and streaming, v3 `_classify_and_maybe_handle`) — intercepts every escalation decision.
2. **Cloud-bound read-time redaction** (`recent_context.get_recent_context(..., redact_local_only=True)`) — `render_stage3_context` passes `redact_local_only=True` so the Opus prompt sees only `[private turn — class: <name>]` for `privacy=local_only` turns. `render_stage2_context` (used by Stage 2 handlers, classifier v3, and `pending_action_resolver`) passes `False` and sees full content — required so `pending_action.data` fields like `day_of_week` / `last_detail_type` survive across turns. FIFO stores full content in both cases; redaction is a read-side projection keyed off the `privacy` field on each record.
3. **Ledger writeback** (`memory/v1/conversation_manager.py`) — stores the full turn on-disk (not cloud-facing) along with the `cls` column for audit. `show_transcript.py` reads the ledger.
4. **Haiku/summary skip** (`jane_proxy._persist_turns_async`) — explicit privacy gate *before* the Stage-2 skip so a future reroute of a private class can't accidentally expose content to cloud writeback.

Shared utilities: `agent_skills/private_handler_utils.py` — `is_no_stage3(cls)`, `privacy_for(cls)`, `safe_deflection(cls)`, `SAFE_CLINIC_DEFLECTION`. Lookup tolerates both `"clinic schedules info"` and `"clinic_schedules_info"` forms.

Currently marked `local_only`: **`clinic_schedules_info` only** (patient data from `$VESSENCE_DATA_HOME/schedule.db`). No other class is private by default.

---

## 17. AI Review Panel — Multi-Model Consultation

Jane can consult other frontier AI CLIs installed on the same machine for second opinions.

**Tool:** `agent_skills/consult_panel.py`

**Available peers:** Auto-detected via `shutil.which()`. Currently: `gemini`, `codex`, `claude`.
Skip Ollama and other non-frontier local models.

**When to consult:**
- Big tasks where the user expects Jane to be busy ("go build X, let me know when done")
- Architecture decisions with no obvious right answer
- After writing 50+ lines of critical code (peer code review)
- Stuck debugging after 2-3 failed attempts
- Generating tests for new code

**When NOT to consult:**
- Regular chat / Q&A (keep it fast)
- Simple commands and quick tasks
- Short code edits (<50 lines)
- Anything where response speed matters (Android voice, web chat)

**Rules:**
- The calling brain excludes itself (Claude doesn't ask Claude, Gemini doesn't ask Gemini)
- Queries run in parallel — total wait = slowest responder, not sum
- If a peer fails (quota, timeout), proceed with the others
- If ALL peers fail, proceed solo with own judgment
- Announce consultations visibly: `## Consulting Gemini and OpenAI on this decision...`
- ALL brains (Claude, Gemini, OpenAI) follow these same rules when they are the active brain

## 18. Model Context Protocol (MCP) — Tool Integration

Every tool and essence MUST define an MCP (`mcp.json`) that tells Jane how to use it. This is the plug-and-play interface for third-party tool development.

### 18.1 What the MCP Defines
1. **Triggers** — keywords and phrases that activate the tool
2. **Commands** — available actions with parameters, API endpoints, response format
3. **Response tags** — special tags (e.g., `[MUSIC_PLAY:id]`) that the client parses for actions
4. **Error handling** — what to say when things fail
5. **Client requirements** — what Android/web needs to support the tool

### 18.2 How Jane Uses MCPs
- **Startup**: all `mcp.json` files are loaded and indexed by keywords
- **Per request**: the initial-ack router checks keywords → loads matching MCP into context → knows exact command format
- **Delegation**: if Claude handles it, MCP is included in Claude's context too
- **Marketplace**: MCP is mandatory for publishing — buyers see it as the capabilities list

### 18.3 Completeness Rule
A tool/essence is NOT complete without a valid MCP. The essence builder interview MUST include MCP definition as a required section.

**Full spec**: `configs/MCP_SPEC.md`

## 19. Operational Checklist

1. **Qwen Delegation Check:** Code analysis, search summarization, or log triage → delegate to Qwen sub-agent.
2. **Micromanagement Audit:** Did I perform low-level edits that should have been autonomous? My role is strategic intent.
3. **Documentation Update Check:** If architecture, capabilities, or processes changed → update relevant config docs.
