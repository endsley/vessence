# Job: Context Window Monitor — Auto-Rotate Persistent Claude Sessions

Status: complete
Priority: 2
Created: 2026-03-22

## Objective
Build a monitor that detects when a persistent Claude CLI session is approaching its context window limit and seamlessly rotates to a fresh session — carrying forward essential context via ChromaDB so the user experiences no interruption.

## Context
On 2026-03-22, Jane web runs persistent Claude CLI sessions via `--resume <session_id>` (see `jane/persistent_claude.py`). This keeps multi-turn conversation state inside Claude's own context window. The problem: there is no mechanism to detect when that context window is filling up. Once it overflows, Claude either degrades silently (drops earlier context) or errors out — and nobody catches it.

Current session management:
- `jane/persistent_claude.py` — `ClaudePersistentManager` manages sessions, tracks `turn_count` and `last_used`
- `jane_web/jane_proxy.py` — `_use_persistent_claude()` gates the feature; `_execute_brain_stream()` wires streaming
- `jane_web/jane_proxy.py` — `_prune_stale_sessions()` removes sessions idle for `SESSION_IDLE_TTL_SECONDS`
- `jane/persistent_claude.py` — `prune_stale()` removes sessions idle for 6 hours
- **No context size tracking exists.** No rotation. No graceful handoff.

Claude Code's `stream-json` output includes a `"result"` event at the end of each turn. This event may contain token usage info or session metadata that can be used for tracking.

## Design

### Detection Strategy
The monitor needs to know how full the context window is. Options (investigate in order of preference):

1. **Parse `result` event from stream-json** — check if it includes `usage` fields (input_tokens, output_tokens, cache stats). If so, track cumulative token count per session.
2. **Track cumulative response/prompt sizes** — sum up `len(prompt_text)` sent and `len(response_text)` received per session as a rough char-based estimate (÷4 ≈ tokens).
3. **Turn count heuristic** — if no token data is available, use turn count as a proxy (e.g., rotate after N turns).

Threshold: rotate when estimated usage exceeds ~70-80% of the model's context window (check the model's limit — Opus/Sonnet have different windows).

### Rotation Strategy
When the threshold is hit on the next `run_turn()` call:

1. **Summarize the prior conversation** — extract the key context the user would expect Jane to remember:
   - What topic they were discussing
   - Any decisions made
   - Any pending tasks or follow-ups
2. **Save summary to ChromaDB** — use `add_fact.py` with topic `session_handoff` so it's retrievable
3. **Start a fresh Claude session** — clear `claude_session_id` so the next turn creates a new `--print` call (no `--resume`)
4. **Inject the summary into the new session's first prompt** — via `context_builder.py` so the fresh session has continuity
5. **Emit a status event** — `on_status("Refreshing session context...")` so the user sees what's happening

### Seamlessness Requirements
- The user should NOT have to do anything — rotation happens automatically
- The user should see a brief status indicator (not an error)
- The new session should "know" what was being discussed — test this explicitly
- No messages should be lost — if rotation happens mid-request, the current request must still complete on the old session before rotating

## Steps

### 1. Investigate stream-json result event for token usage
```python
# In _process_ndjson_line(), log the full "result" event to see what fields are available
elif event_type == "result":
    logger.info("Result event keys: %s", list(event.keys()))
    # Look for: usage, token_count, input_tokens, output_tokens, etc.
```

### 2. Add token/size tracking to ClaudePersistentSession
```python
@dataclass
class ClaudePersistentSession:
    session_id: str
    claude_session_id: str | None = None
    last_used: float = field(default_factory=time.time)
    turn_count: int = 0
    estimated_tokens: int = 0  # NEW: cumulative token estimate
    prompt_chars_sent: int = 0  # NEW: fallback tracking
    response_chars_received: int = 0  # NEW: fallback tracking
```

### 3. Update _execute_streaming to extract and accumulate token usage
After each turn in `run_turn()`, update the session's token tracking from the result event or from prompt/response sizes.

### 4. Add rotation check in run_turn()
```python
async def run_turn(self, session_id, prompt_text, ...):
    session = await self.get(session_id)

    # Check if we need to rotate
    if self._should_rotate(session):
        await self._rotate_session(session, on_status)

    # ... existing turn logic ...
```

### 5. Implement _should_rotate()
Compare estimated tokens against model context limit (with 70-80% threshold).

### 6. Implement _rotate_session()
- Generate a conversation summary (could use Claude itself for this, or extract from ChromaDB recent entries)
- Save to ChromaDB as session_handoff
- Clear claude_session_id
- Emit status

### 7. Wire summary injection into context_builder.py
When building context for a fresh session that has a recent `session_handoff` entry, include it in the system prompt.

### 8. Test: multi-turn conversation that exceeds threshold
Simulate a long conversation (or lower the threshold temporarily) and verify:
- Rotation triggers at the right time
- New session knows prior context
- No error shown to user
- Status event is emitted

## Files Involved
- `jane/persistent_claude.py` — session management, streaming, rotation logic
- `jane/context_builder.py` — system prompt assembly, inject handoff summaries
- `jane_web/jane_proxy.py` — where run_turn is called from the web layer
- `agent_skills/add_fact.py` — saving handoff summaries to ChromaDB

## Fix & Improve
If any step fails or reveals a problem:
- **Fix it** — don't just report the failure. Trace the root cause and patch the code.
- **If you spot potential issues** (race conditions, lost messages, double-rotation) — fix them proactively.
- **If you see improvements** (better summarization, smarter thresholds, adaptive rotation) — make them.
- Document every fix/improvement in the job's completion notes.

## Notes
- Claude Code's context window size depends on the model. Check if the result event reports the model name.
- The summarization step itself uses tokens — account for that in the budget.
- Consider whether rotation should happen *before* or *after* the current turn. Before is safer (avoids hitting the wall mid-response).
- `context_builder.py` already queries ChromaDB — the handoff summary injection should fit naturally into that flow.
