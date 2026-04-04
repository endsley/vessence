# Jane Streaming Architecture — Evolution & Current Design

## History

### Phase 1: One-Shot Subprocess (Original)
```
Web/Android → jane_proxy → claude --print -p "full context" → plain text response
```
- Every message spawned a **new** `claude -p` process
- Full system prompt + memory + all conversation history resent every time
- Output: plain text only — no tool visibility, no intermediary steps
- User experience: silence → full response appears at once
- Cost: ~26K tokens per message (base context) + growing history

### Phase 2: Canned Status Messages (March 21)
```
jane_proxy spawns _emit_periodic_status() alongside claude -p
```
- Added rotating canned messages: "Thinking...", "Drafting...", "Wrapping up..."
- These were **fake** — they didn't reflect what Claude was actually doing
- Better UX (user sees something is happening) but misleading

### Phase 3: Haiku Summarizer (March 22, ~2 AM)
```
jane_proxy spawns _ResponseSummarizer that calls Haiku every 5-7 seconds
```
- Accumulated partial text, called `claude --model haiku --print` to summarize
- Emitted 1-sentence status like "Explaining the USB sync architecture"
- Problems:
  - Extra token cost (Haiku call every 5-7 seconds)
  - Added latency (subprocess spawn per summary)
  - Still only summarized **text output**, not tool use
  - Cross-session broadcast also used Haiku (broadcast.py)

### Phase 4: Persistent Sessions + stream-json (March 22, current)
```
jane_proxy → claude --print --verbose --output-format stream-json --resume <session>
```
- **Real tool_use events** streamed natively from Claude Code
- Zero extra cost — `--verbose` just exposes what's already happening
- Status updates are **actual operations**: "Reading main.py", "Searching code: broadcast"
- Session persistence via `--resume` — Claude maintains its own context
- Haiku summarizer **removed** — redundant, replaced by real events

## Current Architecture

### Entry Point
```
Web/Android → jane_web (FastAPI) → jane_proxy.py → persistent_claude.py
```

### Event Flow (stream-json)
```json
// 1. Claude decides to read a file
{"type":"assistant","message":{"content":[
  {"type":"tool_use","name":"Read","input":{"file_path":"main.py"}}
]}}
→ jane_proxy emits: {"type":"status","data":"Reading file: main.py"}

// 2. Claude searches code
{"type":"assistant","message":{"content":[
  {"type":"tool_use","name":"Grep","input":{"pattern":"def broadcast"}}
]}}
→ jane_proxy emits: {"type":"status","data":"Searching code: def broadcast"}

// 3. Claude writes response text (streamed as deltas)
{"type":"assistant","message":{"content":[
  {"type":"text","text":"Here's what I found..."}
]}}
→ jane_proxy emits: {"type":"delta","data":"Here's what I found..."}

// 4. Final result
{"type":"result","session_id":"abc-123","total_cost_usd":0.02}
→ jane_proxy emits: {"type":"done","data":"full response"}
```

### Tool Labels (human-readable)
| Claude Tool | Status Message |
|---|---|
| Read | "Reading file: {filename}" |
| Edit | "Editing file: {filename}" |
| Write | "Writing file: {filename}" |
| Bash | "Running command: {description}" |
| Grep | "Searching code: {pattern}" |
| Glob | "Finding files: {pattern}" |
| WebSearch | "Searching the web: {query}" |
| WebFetch | "Fetching webpage: {url}" |
| Agent | "Launching agent: {description}" |

### What Was Removed
- `_emit_periodic_status()` — canned rotating messages
- `_ResponseSummarizer` — Haiku-based text summarizer (5-7 second interval)
- `brain_status_task` — task that emitted canned messages during brain execution
- `summarizer_task` — task that ran Haiku summarization loop

### What Was Kept
- `StreamBroadcaster` in `broadcast.py` — still needed for **cross-session** updates (web watching CLI activity, Android watching web). Active client gets real events; other clients get Haiku summaries.
- `_emit_keepalive` — prevents proxy/tunnel timeout on long-running requests

### Why This Is Better

| Metric | Before (Haiku) | After (stream-json) |
|---|---|---|
| Extra token cost | ~500-2000 tokens/message (Haiku calls) | 0 |
| Status accuracy | Summarized approximation | Exact tool operations |
| Latency | +1-2s per summary call | 0 (events are real-time) |
| Tool visibility | None — black box | Full — read, edit, search, bash visible |
| Code capability | Text-only chatbot | Full coding agent (file edit, search, bash) |

### Files Changed
- `jane/persistent_claude.py` — parses `tool_use` events, emits as `on_status`
- `jane_web/jane_proxy.py` — removed summarizer/canned status, wires `on_status=emit("status",...)`
- `jane_web/broadcast.py` — kept for cross-session only
