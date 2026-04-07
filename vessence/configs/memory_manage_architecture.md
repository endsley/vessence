# Memory & Context Architecture

This document describes the "Tiered Memory Architecture" used by Jane to ensure long-term knowledge retention and prevent context window overflow.

---

## 0. Storage Routing: Vault vs. ChromaDB

This is the most fundamental decision in the memory system. Every piece of information must be routed to the correct store.

| Store | Path | What goes here | What does NOT go here |
|-------|------|----------------|-----------------------|
| **Vault** | `/home/chieh/vault/` | Actual files: PDFs, images, audio, markdown documents, binary artifacts, the SQLite ledger. Things you open, share, or reference by file path. | Extracted facts, summaries, or semantic knowledge |
| **ChromaDB** | `user_memories`, `file_index_memories`, `long_term_knowledge`, `short_term_memory` | Facts, decisions, history of what was built/decided/learned, preferences, events, insights, and file index records in separate retrieval lanes. | Raw files, binary data, large text blobs |

**Decision rule (one question):** Is this a *file* or a *fact*?
- File (has a format, you'd open it) → Vault
- Fact (a sentence or paragraph of knowledge) → ChromaDB

**Examples:**
- Research paper the user sends → Vault (`/vault/pdf/`). The paper's key insight → ChromaDB.
- Voice clip → Vault (`/vault/audio/`). "the user prefers Kokoro TTS voice X" → ChromaDB.
- the user's teaching statement → Vault (`/vault/documents/`). "the user's teaching philosophy emphasizes..." → ChromaDB.
- What we built in a session → ChromaDB (history/fact). The code artifact itself → filesystem (not vault unless explicitly saved).

---

## 1. Overview: The Four Tiers of Memory

When processing a prompt, context is assembled from four tiers:

1.  **Active Context Window:** The immediate, live conversation history, including summaries of older parts of the conversation.
2.  **Short-Term Memory DB:** Shared, persistent ChromaDB at `$VESSENCE_DATA_HOME/vector_db/short_term_memory/`. Stores compact retrieval-oriented summaries of recent conversation turns AND explicitly added time-limited facts. All entries carry a `timestamp` and `expires_at` (default 14-day TTL). Replaces both the old per-session `session_memory` and the separate `forgettable_knowledge` DB. Purged nightly by the Janitor.
3.  **Long-Term Memory DB:** Curated, permanent facts. Two stores: `user_memories` (Jane's shared long-term store, `memory_type: "long_term"` or `"permanent"`) and `long_term_knowledge` (Jane's conversation archivist output at `vector_db/long_term_memory/`). No TTL — janitor may consolidate/deduplicate but never auto-expires.
4.  **File Index Memory DB:** Dedicated ChromaDB collection at `$VESSENCE_DATA_HOME/vector_db/file_index_memory/` named `file_index_memories`. Stores file path, MIME/type, and concise descriptions of vault files. For formats the agent can read, the description must be based on the file contents rather than filename/path only. Queried only for file/vault lookup prompts.
4.  **Permanent Memory (Startup):** Foundational knowledge loaded at the start of a session from architecture files, identity essays, and registries.

---

## 2. Core Components & Processes

### 2.1. Vector Databases

| Collection | Path | What goes here | TTL |
|-----------|------|----------------|-----|
| `user_memories` | `$VESSENCE_DATA_HOME/vector_db/` | Permanent + long-term facts for Jane (`memory_type: "permanent"` or `"long_term"`) | None |
| `long_term_knowledge` | `$VESSENCE_DATA_HOME/vector_db/long_term_memory/` | Jane's conversation archivist output (curated, high-signal facts promoted from short-term) | None |
| `short_term_memory` | `$VESSENCE_DATA_HOME/vector_db/short_term_memory/` | Compact summaries of conversation turns + explicitly added time-limited facts. Shared/persistent across sessions. | 14 days |
| `file_index_memories` | `$VESSENCE_DATA_HOME/vector_db/file_index_memory/` | Vault file index records: path, file name, MIME/type, content-derived description when readable, tags | None |

### 2.1.2. File Index Memory — Design

File indexing records are intentionally separated from human semantic memory.

Use `file_index_memories` for:
- file path lookup
- vault existence checks
- MIME/type metadata
- concise content descriptions of files
- content-derived descriptions for readable files (text, markdown, code, JSON, CSV, PDF, DOCX, images via vision)

Do not store these in `user_memories` by default:
- `Vault file: ...`
- `Saved file 'x' ...`
- path-only operational records

Retrieval rule:
- Jane always queries `short_term_memory`, `user_memories`, and `long_term_knowledge`
- Jane queries `file_index_memories` only when the prompt looks file-oriented, such as questions about files, documents, vault contents, or paths

This prevents file metadata from crowding out real user facts in normal prompts.

**All entries in every DB carry a `timestamp` field** (ISO UTC string) so recency-aware search and Qwen Librarian synthesis can reason about "just told you" vs old facts.

### 2.1.1. Short-Term Memory — Design

Short-term memory is the **"working notepad"** tier: highest-priority during retrieval, self-expiring so it never accumulates indefinitely.

**Replaces:** the old per-session `session_memory` (deleted at session end) AND the separate `forgettable_knowledge` DB. Both are now unified here.

**Purpose / when to use:**
- Compact summaries of conversation turns from current and recent sessions (written automatically by `ConversationManager`)
- Something just implemented or changed (e.g., "Fixed the ChromaDB expiry bug today.")
- A solution just discovered or a workaround in effect
- Cron job execution logs (`--topic cron_logs`)

**Important distinction:** the short-term Chroma tier no longer stores raw full-turn text by default. It stores a concise retrieval note derived from each turn. The raw transcript is still preserved in the SQLite ledger at `$VAULT_HOME/conversation_history_ledger.db`.

**Schema (ChromaDB metadata per entry):**
```
memory_type : "short_term"
author      : "jane" | "system" | "conversation_archivist" | "legacy_amber" | …
topic       : str  (default "General")
subtopic    : str  (default "")
timestamp   : ISO UTC datetime string  ← always present
expires_at  : ISO UTC datetime string  ← set when Archivist marks as short-term, or at add time
ttl_days    : int
session_id  : str  (for conversation turns)
role        : "user" | "assistant"  (for conversation turns)
raw_chars   : int  (original message length before summarization)
summary_chars : int (stored compact summary length)
summary_style : "concise_turn_memory_v1" | "code_change_turn_memory_v1"
```

**Default TTL:** 14 days. Override per entry with `--days N`.

**Automatic turn summarization:**
- `ConversationManager` summarizes each new turn before writing it to `short_term_memory`.
- The stored form should preserve only the shortest facts that maximize later retrieval value: decisions, file paths, current work state, open loops, and solution state.
- Assistant turns that look like code edits are summarized with a code-aware prompt. The summarizer should capture files changed, the behavioral effect of the edit, important functions/classes, and open risks or next steps, instead of restating raw diff text.
- Code-aware summaries use `summary_style: "code_change_turn_memory_v1"` and preserve short `-` bullet lines so retrieval keeps the edit structure instead of flattening it back into prose.
- If summarization fails or times out, the system falls back to a truncated raw-text write rather than losing the memory.
- Legacy short-term entries written before this design change may still be bloated until the migration helper rewrites them.

**Adding short-term memories explicitly:**
- CLI: `agent_skills/memory/v1/add_forgettable_memory.py "fact text" [--days N] [--topic T] [--subtopic S] [--author A]`
- Python: `from agent_skills.add_forgettable_memory import add_forgettable_memory; add_forgettable_memory(fact, ...)`
- Legacy compatibility: older runtime paths may still call `add_forgettable_memory.py` directly. New architecture should treat those writes as Jane memory writes unless explicitly marked as historical.

**Expiry & purge:** The nightly Memory Janitor calls `purge_expired_short_term()` which deletes entries where `expires_at < utcnow()` from `short_term_memory`.

**Cron log convention:** After every cron job execution, log a short-term entry with `--topic cron_logs` recording what ran, when, and the outcome (default 14-day TTL).

**Enforcement:** The git pre-commit hook at `.git/hooks/pre-commit` blocks any commit that stages memory-system source files without also staging this architecture doc. To update and unblock: `git add configs/memory_manage_architecture.md`.

### 2.2. Archival Flow (Short-Term → Long-Term)

The `ConversationManager` Archivist triages entries from the current session in `short_term_memory`:
- **Keep** → promoted to `long_term_knowledge`, deleted from `short_term_memory`
- **Short-Term** → `expires_at` stamped in-place (stays in `short_term_memory` until TTL)
- **Discard** → deleted from `short_term_memory` immediately
- **Retry / Timeout Safety** → if the archivist model errors or times out, the entry is left untouched in `short_term_memory` for a later retry. Failures must not silently discard memory.

Trigger:
- Before local noon: 60 seconds of user idle time, or session `close()`.
- After local noon: idle archival waits until the session has been idle for at least 1 hour, then runs with the smarter local archivist model. Session `close()` still runs a final archival pass immediately.

Archivist decision guidance:
- **Keep** includes durable solution knowledge, not just user facts. If a memory captures a problem that took meaningful effort to solve, the fix that worked, the root cause, or lessons learned likely to help again later, it should be promoted to long-term memory.
- **Short-Term** is for recent execution state and temporary progress that matters now but is unlikely to matter after the current work window.
- **Discard** is for noise, filler, and redundant repetition.

### 2.2. Active Conversation Compaction (Context Window Management)
- **Mechanism:** `ConversationManager` monitors the token count of the live in-memory context window.
- **Trigger:** When 65% of the model's token limit is reached (`CONTEXT_COMPACTION_RATIO` in `jane/config.py`), the oldest portion of `conversation_history` is replaced with a Qwen-generated summary.
- **Note:** This is purely a context-window management step. It does NOT drive archival to long-term memory; that is handled separately (see §2.3).
- **Short-term DB write:** Every message is also written to the shared persistent Short-Term DB immediately on `add_message`, but the vectorized record is a compact retrieval summary rather than the raw full message.

### 2.3. Idle-Triggered Archival (Short-Term → Long-Term)
- **Primary Trigger:** Before local noon, after **60 seconds of user inactivity** (no new messages), if the Short-Term DB contains any entries, the Archivist runs automatically.
- **Afternoon smarter pass:** At 12:00 PM or later, the idle callback defers archival until the user has been idle for at least 1 hour, then runs the Archivist with the smarter local archivist model.
- **Secondary Trigger:** Session end (`close()`), which runs a final archival pass before cleanup.
- **Failure safety:** If the archivist model is slow, unavailable, or times out, the item remains in short-term memory and is retried on a later archival pass instead of being discarded.
- **The old 75% rule is no longer the archival trigger.** Context compaction (now at 65%) controls context-window management only.
- **Process:**
  1. Retrieve all entries currently in the Short-Term DB.
  2. For each entry, Qwen ("The Archivist") decides Keep or Discard using the criteria in `project_specs/context_window_management.md`.
  3. Kept entries are written to the Long-Term DB with source/session metadata.
  4. Entries classified as `Keep` or `Discard` are deleted from Short-Term; `Short-Term` entries remain with a stamped `expires_at`.
- **Session-end Cleanup:** `close()` runs one final archival pass and releases DB handles. The current architecture uses shared persistent short-term storage rather than deleting a per-session ChromaDB directory.

### 2.4. Unified Memory Retrieval
- **Mechanism:** When a prompt is received, the system queries `user_memories`, `short_term_memory`, and Jane's `long_term_knowledge`. It queries `file_index_memories` only for file/vault lookup prompts. Legacy forgettable entries are still swept when present.
- **Recent-memory strategy:** Retrieval uses both semantic top-N and a broader sweep of still-valid recent entries, guaranteeing that very recent work surfaces even when the query phrasing is weakly matched.
- **Tiered output:** Results are organized into labeled sections such as `## Permanent Memory`, `## Long-Term Memory`, and `## Short-Term Memory` so the Librarian always knows recency priority.
- **Jane web conversation summary:** Jane web keeps a Python-owned per-session summary file under `$VESSENCE_DATA_HOME/data/jane_session_summaries/`. Each file stores at most 3 distinct central topics, with `topic`, `state`, and `open_loop`. This is Jane web's continuity layer for stateless turns.
- **Jane web session bootstrap:** Jane web prewarms a per-session bootstrap memory summary at session establishment, caches it in session state, and reuses it for follow-up turns. Heavy bootstrap retrieval should happen once per live web session, not once per message.
- **Structured personal facts for prompt shaping:** Jane web keeps compact personal facts in `$VESSENCE_DATA_HOME/user_profile_facts.json`, grouped into typed categories such as identity, profession, preferences, hobbies, and communication style. Prompt assembly selects only the topic-relevant facts instead of injecting the full `user_profile.md` blob.
- **Separate summarizer subprocess:** After each Jane web turn, a separate local Qwen subprocess (`qwen2.5-coder:14b`) updates that session summary asynchronously. Python validates and writes the JSON summary file.
- **Local Librarian:** The combined results are synthesized by the local librarian model (`gemma3:4b`). On Jane web, the Librarian sees the current user message plus the stored conversation summary, not a replay of recent raw turns. It should return only the shortest memory delta that materially improves the next response.
- **Intent-shaped retrieval and thresholds:** Jane web classifies prompts into lightweight intent lanes (`factual_personal`, `file_lookup`, `project_work`, `casual_followup`) and queries only the relevant memory lanes. Chroma results are filtered by per-lane cosine-distance thresholds before reaching the Librarian.
- **Prompt shaping:** Jane web now uses a tiny base system prompt plus only the dynamic sections needed for that intent. It does not inject the full `user_profile.md`, and it suppresses `current_task_state.json` and conversation summary for simple non-task prompts.
- **Asynchronous writeback:** Short-term memory persistence and session-summary refresh are dispatched after the web response is sent. Memory writeback must not block the final user-visible response.
- **Low-value turn handling:** Very short turns use a rule-based short-term summary, and trivial low-value turns can be skipped entirely instead of paying an LLM summarization cost.
- **File-index lane:** Vault file metadata and descriptions are routed into `file_index_memories`, not mixed into `user_memories`. Query that lane only for file/vault/path prompts.
- **Retrieval shaping goal:** the conversation summary is intentionally tiny. Large prompt growth should come only from retrieved memory tiers, not from replaying recent chat history. If the Librarian prompt is bloated, inspect `long_term_knowledge`, `user_memories`, `short_term_memory`, and `file_index_memories` contents rather than the session summary file.
- **Similarity-gated cache (Jane web):** Jane web keeps a tiny in-process cache for the memory-summary layer only. A cached summary is reused only within the same session, only for a short TTL, and only when the new query embedding is highly similar to a cached query embedding. This skips repeated Chroma + Librarian work on near-duplicate follow-ups while allowing topic pivots to miss the cache naturally.
- **Similarity-gated disk cache (Claude Code hooks):** `startup_code/query_live_memory.py` maintains a disk-based cache at `$VESSENCE_DATA_HOME/data/memory_hook_cache.json` with 5-minute TTL and max 20 entries. Queries with cosine similarity ≥ 0.92 to a cached query reuse the cached summary, skipping ChromaDB + Librarian entirely.
- **Smart brain bypass:** Models with strong reasoning (Claude, OpenAI/GPT-4) receive raw filtered memory sections directly from `build_memory_sections()` instead of passing through the local Gemma librarian. This saves 2–5 seconds per query. Controlled by `JANE_BRAIN` env var; bypass list: `{"claude", "openai", "gpt-4", "gpt-4o"}`. Override with `MEMORY_BYPASS_LIBRARIAN=1` to skip librarian for any model.

### 2.5. Claude Code Memory Integration

Claude Code receives memory context via UserPromptSubmit hooks defined in `~/.claude/settings.json`:

1. **`startup_code/claude_smart_context.py`** — Classifies prompt intent using the same lanes as Jane web (`factual_personal`, `file_lookup`, `project_work`, `casual_followup`). Injects compact identity + user background + task state (~800–2,000 tokens). Replaces the old `identity_hook.sh` + `claude_full_startup_context.py` + `jane_context_hook.sh` (which injected ~25,000 tokens).
2. **`~/.claude/hooks/memory_hook.sh`** — Queries ChromaDB via `query_live_memory.py` and outputs retrieved memory sections.
3. **`~/.claude/hooks/prompt_queue_hook.sh`** — Intercepts `prompt:` prefix messages for the prompt queue.
4. **`~/.claude/hooks/idle_state_hook.sh`** — Records last-active timestamp for idle detection.

**Hook output format:** Hooks output **plain text to stdout** (not JSON). Claude Code auto-injects stdout content as `additionalContext`. The JSON format `{"additionalContext": "..."}` does NOT work with Claude Code hooks despite being documented — plain text is required.

## 3. The High-Fidelity Interaction Ledger (SQLite)

In addition to the semantic vector databases, the system maintains a structured, sequential record of every interaction in a SQLite database. This serves as the system's "Flight Recorder" for auditing, performance analysis, and crash recovery.

### 3.1. Ledger Specification
- **Storage Path:** `$VAULT_HOME/conversation_history_ledger.db`
- **Mechanism:** Every turn (user input and agent response) is automatically recorded by the `ConversationManager` at the moment it is processed.
- **Schema:**
    - `session_id`: Unique ID for the interaction session.
    - `timestamp`: Precise UTC time of the turn.
    - `role`: The speaker (user, assistant, or system).
    - `content`: The raw text of the message.
    - `tokens`: The calculated token count for that specific message.
    - `latency_ms`: The turn-around time for the agent's response.

### 3.2. Role in Debugging and Crash Recovery
The ledger provides Jane with a deterministic way to investigate unexpected failures:
1.  **Post-Mortem Analysis:** If the wrapper or an agent crashes, Jane can query the ledger to see the exact sequence of events leading up to the failure, including raw tool outputs and partial responses that might not have been archived to the Vector DB.
2.  **State Reconstruction:** Because the ledger is sequential, it can be used to reconstruct the "Active Context Window" exactly as it was before a crash, enabling "Session Resume" capabilities.
3.  **Performance Auditing:** By tracking `latency_ms` and `tokens` per turn, Jane can identify specific tools or model behaviors that are causing bottlenecks or excessive costs.

### 3.3. Memory Debugging Aids
- `test_code/benchmark_gemma_librarian.py` measures how retrieval time is split across section building, Librarian model load, prompt ingestion, and generation.
- `test_code/inspect_librarian_input.py` reconstructs the exact Librarian input and writes a readable dump for prompt-size inspection.
- `agent_skills/migrate_short_term_memory.py` rewrites legacy short-term entries into the new concise storage format.
- `agent_skills/normalize_long_term_memory.py` rewrites oversized archived long-term memories into smaller atomic records using review/rewrite/split thresholds.
- `agent_skills/migrate_file_index_memories.py` moves file-index facts out of shared long-term memory into `file_index_memories`.

---

## 4. Nightly Maintenance: The Memory Janitor

To prevent the Long-Term Memory DB from becoming bloated with redundant or outdated information, a nightly maintenance script, "The Memory Janitor" (`agent_skills/memory/v1/janitor_memory.py`), runs to clean and consolidate the database. This process relies on an LLM to perform intelligent clustering and synthesis, rather than using vector distance metrics.

### 4.1. Detailed Algorithm

1.  **Initialization and Fetch**: The script connects to the persistent ChromaDB and retrieves all memories from the `user_memories` collection, including their text and metadata.

1.5. **Purge Expired Short-Term Entries**: Before any consolidation, the janitor calls `purge_expired_short_term()`, which:
    - Deletes all entries in `short_term_memory` whose `expires_at` has passed.
    - Also enforces a hard age cap via `purge_old_forgettable_memories()`, deleting short-term entries older than 14 days by creation timestamp regardless of `expires_at`.
    - Both Unix int and ISO string formats of `expires_at` are handled.

2.  **Protect Permanent and Short-Term Entries**: It iterates through every memory and sets aside entries that must not be consolidated. An entry is excluded if it meets **any** of the following criteria:
    *   Its metadata contains `"memory_type": "permanent"`.
    *   Its metadata contains `"memory_type": "forgettable"` or `"short_term"` — these expire naturally and must not be merged.
    *   Its metadata includes a `file_path`.
    *   Its text content includes the substring `"Saved file '"`.
    *   Its text content includes the substring `"Location: "`.

3.  **Group by Topic**: All remaining (non-permanent) memories are organized into groups based on the `topic` field in their metadata. Memories without a topic are assigned to a "General" group.

4.  **LLM-Powered Consolidation**: The script processes each topic group that contains **five or more** memories. For each group, it dynamically constructs a detailed prompt and sends it to Claude Opus (`claude-opus-4-6`) via the CLI wrapper, with Gemini as a fallback.
    *   **Prompting Strategy**: The model is instructed to act as a "Memory Curator". It receives the entire list of memories for the topic (including IDs, text, and subtopics) and is asked to:
        1.  Identify groups of facts that are redundant or cover the same essential information.
        2.  For each identified group, create a single, high-quality, summarized `new_fact`.
        3.  Consolidate the `subtopic` fields from the original memories into a `new_subtopic`.
    *   **Structured Output**: The prompt requires the model to return its findings in a structured JSON format, specifying which `original_ids` should be merged into a `new_fact`.

5.  **Atomic Deletion and Addition**: The script parses the JSON response from the LLM. For each merge operation returned:
    *   **Deletion**: It deletes all the old, redundant memories from the database using the `original_ids`.
    *   **Addition**: It adds a single new memory to the database containing the synthesized `new_fact`. This new memory is assigned a fresh UUID and given the following metadata: `{"author": "janitor", "status": "compressed", "topic": "[current_topic]", "subtopic": "[new_subtopic]"}`.

6.  **Image Vault Clustering** (`cluster_vault_images()`): After memory consolidation, the janitor reorganizes the flat `vault/images/` directory into a named-subfolder tree.
    *   **Scope**: Only files sitting directly in `vault/images/` root are eligible. Files already inside a subfolder are untouched (avoiding double-moves on repeat runs).
    *   **LLM proposal**: Builds a manifest of each flat image filename + its ChromaDB description, then asks Gemini to assign each image to a sensible subfolder path (e.g., `people/family`, `people/friends`, `agents`, `work`). Max 2–3 levels; lowercase underscored names.
    *   **Move**: `shutil.move()`. Collision-safe: if the destination filename exists, a short UUID hex suffix is appended.
    *   **ChromaDB path update**: Every ChromaDB entry whose document text or `file_path` metadata references the old filename/path is updated via `col.update()` to reflect the new `images/<subfolder>/<filename>` location.
    *   **Report fields**: `images_moved`, `folders_created`, `reasoning` are added to `janitor_report.json`.

7.  **Generate Report**: After all steps, the script saves `janitor_report.json`. Includes: timestamp, `vectors_reduced`, forgettable purge counts, permanent entries protected, topics processed, and `image_clustering` stats.

---

## 5. Dynamic Model Orchestration

### 5.1 Provider Strategy (One Subscription)
Vessence requires only one AI subscription. Setting `JANE_BRAIN` in `.env` configures the entire system:

| Provider | Smart Model (Jane) | Cheap Model (Background) | CLI Binary |
|---|---|---|---|
| `claude` | claude-sonnet-4-6 | claude-haiku-4-5-20251001 | `claude` |
| `openai` | gpt-4o | gpt-4o-mini | `codex` |
| `gemini` | gemini-2.5-pro | gemini-2.5-flash | `gemini` |

**Smart model:** user-facing tasks (Jane and essence interactions).
**Cheap model:** background tasks (archivist, janitor, summarization) via `agent_skills/claude_cli_llm.py`.

All calls go through the provider's CLI binary using the user's existing subscription auth. No separate API keys required. Override with `SMART_MODEL` and `CHEAP_MODEL` env vars if needed.

### 5.2 Background Task LLM (`claude_cli_llm.py`)
A provider-agnostic CLI wrapper at `agent_skills/claude_cli_llm.py` that routes to the correct CLI:
- `completion(prompt)` — uses CHEAP_MODEL for background tasks
- `completion_smart(prompt)` — uses SMART_MODEL for user-facing tasks
- `completion_json(prompt)` — uses CHEAP_MODEL, parses JSON response

Used by: archivist (`conversation_manager.py`), janitor (`janitor_memory.py`).

---

## 6. Update Mandate
This file MUST be updated whenever a change is made to the memory architecture, the Qwen Librarian/Archivist, or the context management strategy of either agent.
