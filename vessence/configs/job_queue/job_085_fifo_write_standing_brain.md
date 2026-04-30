# Job #85: Add FIFO write to standing brain persistence path

**Status: completed**
**Priority: high**
**Created: 2026-04-29**

## Problem

The SQLite FIFO (`vault_web/recent_turns.py`) — which stores per-session turn summaries for cheap sequential retrieval — is never written to by the standing brain (Opus) path. Only the v2/v3 pipeline handler paths call `_persist_turn_to_fifo`. As a result, the most substantive conversations (user ↔ Opus) have zero FIFO entries.

### Evidence

- Current Android session `jane_android_3b191135` has 0 FIFO entries despite multiple Stage 3 turns today.
- `stage3_escalate.py` has 0 references to `recent_turns` or `_persist_turn_to_fifo`.
- `jane_proxy.py`'s `_persist_turns_async` writes to ChromaDB and session summary but not the FIFO.
- The v3 non-streaming path (`jane_v3/pipeline.py:712`) and v2 pipeline both write to FIFO, but the standing brain streaming path bypasses them entirely.

## Fix

Add a `_persist_turn_to_fifo` call in `jane_proxy.py`'s `_persist_turns_async` function (around line 1545), right alongside the thematic memory update. The FIFO write is cheap (~1ms SQLite insert) and does not require an LLM call.

### Implementation notes

- Import `_persist_turn_to_fifo` from `jane_web.jane_v2.pipeline`
- Call it with `stage="stage3"`, the session_id, user_message, and assistant_message
- The FIFO caps at 20 entries per session via built-in eviction — no cleanup needed
- This should run for all stages (stage2 and stage3) in `_persist_turns_async`, but only stage3 currently reaches this code path (stage2 short-circuits earlier)
- Watch for the feedback loop that was previously observed (2026-04-26 comment in `conversation_manager.py:955-966`) — the FIFO write here should use the raw user/assistant text, NOT the Haiku theme summary

## Related

- ChromaDB thematic memory misclassification is a separate issue (Haiku classification bias + corrupted theme summaries). This job only addresses the FIFO gap.
