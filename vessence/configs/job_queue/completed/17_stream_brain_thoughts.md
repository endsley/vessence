# Job: Stream Standing Brain Thoughts to Web UI

Status: done
Priority: 1
Model: opus
Created: 2026-03-24

## Objective
Surface Jane's intermediate thinking (tool calls, reasoning, discoveries) in the web chat UI as they happen. Currently these are visible on the CLI but hidden on web — the user sees silence until the final response.

## What to stream
From Claude CLI's stream-json output, capture:
- **Text deltas from thinking blocks** — "Let me check...", "Found it...", "The issue is..."
- **Tool use events** — "Reading jane_proxy.py", "Running grep for...", "Editing file..."
- **Status text** — any intermediate text output before the final response

## Display rules
- Show as **small font** (same size as existing status updates / intermediary steps)
- Thoughts are **white text** (not grey like regular status updates) — distinguishes Jane's active reasoning from system status
- Displayed in the collapsible status log area of the chat bubble
- Collapsed after the final response arrives (same as current status log behavior)

## Implementation

### Backend (jane/standing_brain.py)
1. In `_read_claude_response()`, detect additional event types:
   - `assistant` events with `thinking` content blocks → emit as thought
   - `assistant` events with `tool_use` blocks → format as "Using [tool_name]: [brief description]"
   - `assistant` events with intermediate text → emit as thought
2. Yield these as a special tuple or tagged string so the proxy can distinguish thoughts from response text
3. Option: yield `("thought", text)` vs `("delta", text)` — or emit directly via a callback

### Backend (jane_web/jane_proxy.py)
1. In `run_adapter_async()`, when the standing brain yields a thought, emit it as a new event type: `emit("thought", text)`
2. Keep emitting `emit("delta", text)` for actual response text

### Frontend (vault_web/templates/jane.html)
1. Add handler for `event.type === 'thought'`:
   - Push to `msg.statusLog` (same as status events)
   - But render with white text class instead of grey
2. In the status log template, distinguish thoughts from status:
   - Regular status: `text-slate-500` (grey, existing)
   - Thoughts: `text-slate-200` (white, new)
   - Could tag each statusLog entry with `{text, type}` instead of just a string
3. Thoughts collapse into the expandable summary after response finishes (same as status)

## Verification
- Send a complex question on web Jane
- See intermediate thoughts appear in real time (white, small font)
- See tool use events ("Reading file X", "Running grep")
- Final response replaces the working state
- Thoughts collapse into expandable "Jane worked through N steps" summary
- Simple greetings show no thoughts (no tool use, no thinking)

## Files Involved
- `jane/standing_brain.py` — parse thinking/tool_use events from stream-json
- `jane_web/jane_proxy.py` — emit "thought" events
- `vault_web/templates/jane.html` — render thoughts in white, status in grey

## Notes
- The thinking block content from Haiku/Sonnet/Opus may contain raw chain-of-thought. Filter out overly internal reasoning — show user-facing summaries, not raw model internals.
- Tool use events are the most valuable — "Reading config.py line 84", "Running tests", "Editing jane_proxy.py" give real visibility into what Jane is doing.
- This also helps debug slow responses — user can see exactly where Jane is stuck.
