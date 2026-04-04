# Spec: Thematic Short-Term Memory (Rolling 20 Themes)

## Problem
Current short-term memory stores one entry per turn (summarized or raw truncated). This grows unbounded, produces fragmented retrieval results, and the per-turn summarizer was silently failing (Ollama model mismatch). The archivist already does thematic archival for long-term — short-term should follow the same pattern.

## Solution
Replace per-turn short-term writes with a **rolling set of up to 20 thematic memory slots**. Each new turn is classified: does it belong to an existing theme, or does it start a new one? The matching theme's summary is updated in place with the new information.

## Data Model

Each theme slot in ChromaDB:
```json
{
  "id": "session_{sid}_theme_{index}",
  "document": "Theme summary text (updated in place as turns arrive)",
  "metadata": {
    "session_id": "abc123",
    "theme_title": "Docker onboarding auth fix",
    "theme_index": 3,
    "turn_count": 7,
    "first_turn_at": "2026-03-28T21:00:00Z",
    "last_updated_at": "2026-03-28T22:15:00Z",
    "memory_type": "short_term_theme",
    "expires_at": "2026-04-11T22:15:00Z"
  }
}
```

## Algorithm

On each new turn (user + assistant pair):

1. **Fetch current themes** for this session from ChromaDB (up to 20)
2. **Classify the turn** — send to local LLM (gemma3:4b):
   ```
   Given these existing themes:
   1. "Docker onboarding auth fix" — fixing OAuth flow for Docker installs
   2. "Jane web empty response bug" — standing brain returning 0 chars
   ...

   New turn:
   User: <message>
   Jane: <response>

   Does this turn add detail to an existing theme (respond with the theme number),
   or does it introduce a genuinely new topic (respond with NEW: <theme title>)?
   Prefer matching existing themes — only say NEW if this is clearly a different subject.
   ```
3. **If existing theme** (the common case): **Update in place**
   - Send to LLM: "Here is the current summary for this theme. Incorporate the new turn's key details."
   - ChromaDB `update()` — overwrites the document with the enriched summary
   - No new entries created. The memory count stays the same.
4. **If genuinely new theme** (less common):
   - If < 20 themes: `add()` a new slot
   - If = 20 themes: drop the oldest theme (by `last_updated_at`) and reuse its slot via `update()`
5. **No TTL management needed per-turn** — themes expire based on `last_updated_at + 14 days`

### Key principle
The short-term memory size is **bounded and mostly static**. The normal operation is `update()`, not `add()`. New entries are rare — only when the conversation genuinely shifts to a new topic. A typical 50-turn conversation might create 3-5 themes, with the rest of the turns enriching those existing themes.

## What Changes

### Remove
- `_write_to_short_term()` — no more per-turn writes
- `_summarize_for_short_term()` — no more per-turn summarization
- `_should_store_short_term_turn()` — no more noise filtering (the LLM handles this naturally)

### Add
- `_update_thematic_memory(user_msg, assistant_msg)` — the new entry point
- `_classify_turn_theme(themes, turn)` — LLM classifies: existing theme or new
- `_update_theme_summary(theme_doc, turn)` — LLM updates a theme's summary
- `_create_theme(title, turn)` — creates a new theme slot

### Keep unchanged
- SQLite ledger writes (raw transcript for thematic archival)
- Long-term thematic archival (reads from SQLite, not short-term)
- ChromaDB short_term_memory collection (same collection, different entry format)

## Async Architecture

The thematic memory update runs in a **separate background process** so it never blocks the response path.

### Flow
1. `jane_proxy.py` finishes streaming the response to the user
2. Fires off the thematic update as a background task (existing persistence worker pattern)
3. The worker process does the 2 LLM calls + ChromaDB update independently
4. If the worker is still processing when the next turn arrives, it queues — no dropped turns

### Implementation
- Use the existing `asyncio.create_task()` pattern already used for persistence/writeback
- The thematic worker is a standalone async function: `_update_thematic_memory_async(session_id, user_msg, assistant_msg)`
- It acquires a per-session lock to prevent concurrent theme updates on the same session
- If a turn arrives while the previous update is in progress, it waits for the lock (not dropped)

### Failure Isolation
- Worker crashes don't affect the response path
- If the LLM is down, fall back to raw text in the most recent theme slot
- Log failures to `jane_writeback_timing.log` for debugging

## LLM Calls Per Turn
- 1 call to classify (existing vs new theme) — ~50 tokens out
- 1 call to update the theme summary — ~150 tokens out
- Total: 2 LLM calls per turn via **Sonnet** (claude-sonnet-4-6) for high-quality thematic judgment
- Runs fully async in background — zero impact on user-facing latency
- Uses `claude_cli_llm.completion()` (existing CLI wrapper, uses the user's Claude subscription)

## Retrieval
When building context for a new request, the librarian queries the 20 theme summaries instead of individual turns. Higher signal, better semantic matching.

## Migration
- Old per-turn entries (with `summary_style` metadata) can coexist
- New entries use `memory_type: "short_term_theme"`
- Janitor can clean up old-format entries over time

## Edge Cases
- **Very short turns** ("ok", "thanks"): LLM classifies as belonging to the most recent active theme or ignores
- **Topic jumps**: User switches topics mid-conversation → new theme created
- **20 theme overflow**: Oldest theme dropped. The thematic archival (long-term) should have already captured it if it was valuable.
- **LLM failure**: Fall back to raw text in the most recent theme slot (same as current fallback)
- **Rapid turns**: Per-session lock serializes updates — no race conditions, no dropped turns

## Files to Modify
1. `agent_skills/conversation_manager.py` — replace `_write_to_short_term` with async thematic version
2. `jane_web/jane_proxy.py` — fire thematic worker as background task (same pattern as current writeback)
3. `jane/config.py` — add `SHORT_TERM_MAX_THEMES = 20`
4. `agent_skills/search_memory.py` — no changes needed (already queries by semantic similarity)

## Estimated Scope
- ~150 lines new code in conversation_manager.py
- ~50 lines removed (old per-turn write path)
- ~10 lines in jane_proxy.py (swap writeback call)
- Testing: verify theme creation, updates, overflow, async timing, and retrieval quality
