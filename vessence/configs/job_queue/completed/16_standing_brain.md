# Job: Standing Brain — Provider-Agnostic Long-Lived CLI with Stream-JSON I/O

Status: complete
Completed: 2026-03-24 16:45 UTC
Notes: Full implementation complete using CLI stream-json I/O (no API key needed). Three standing Claude CLI processes (haiku/sonnet/opus) spawned at jane-web startup via StandingBrainManager. Each process stays alive between messages using --input-format stream-json --output-format stream-json. Results: greeting response 9.3s → 6.4s (eliminated ~3s subprocess spawn). Brain execute 8.1s → 5.3s. Remaining latency is pure API round trip. Auto-starts on boot, auto-restarts dead processes, reaps idle brains after 30min. RAM: ~300MB per process (~900MB total). Graceful fallback to CLI subprocess if standing brain not started.
Priority: 1
Model: opus
Created: 2026-03-24

## Objective
Replace the current "Resume Brain" architecture (spawns a new `claude` subprocess per message with `--resume`) with a "Standing Brain" architecture (one long-lived Claude CLI process per model, communicating via stdin/stdout stream-json). Eliminates ~2-3s subprocess spawn overhead per message.

## Architecture

### Current (Resume Brain)
```
Each message → subprocess.Popen(["claude", "--resume", session_id, "-p", msg])
  → 1-2s process spawn + 1s CLI init + API latency
  → process exits after response
```

### New (Standing Brain)
```
Service startup → spawn 1 standing process per model tier:
  claude --print --input-format stream-json --output-format stream-json --dangerously-skip-permissions --model <model>

Each message → write JSON to stdin → read JSON from stdout
  → ~0s spawn overhead, just API latency
  → process stays alive between messages
```

### Three Standing Brains — Provider-Agnostic

| Tier | Claude (JANE_BRAIN=claude) | Gemini (JANE_BRAIN=gemini) | Use case | Tools |
|------|---------------------------|---------------------------|----------|-------|
| Light | claude-haiku-4-5 | gemini-2.5-flash | Greetings, simple | No |
| Medium | claude-sonnet-4-6 | gemini-2.5-pro | Investigation, fixes | No |
| Heavy | claude-opus-4-6 | gemini-2.5-pro (thinking) | Complex builds | Yes |

### Provider Abstraction
- `StandingBrainManager` reads `JANE_BRAIN` env var at startup
- Spawns 3 brains using the provider-specific method:
  - **Claude**: CLI with `--input-format stream-json --output-format stream-json` (bidirectional pipe)
  - **Gemini**: CLI with PTY stdin/stdout (already proven in persistent_gemini.py)
  - **OpenAI**: Python SDK directly (`openai.chat.completions.create`) — Codex CLI has no stream-json mode
- The classifier + proxy don't need to know which provider — they just say "use light/medium/heavy"
- Switching provider = change env var + restart service. No code changes.
- Each provider implements a `StandingBrainProvider` interface: `send(prompt) -> async generator[str]`

### Provider Implementations
```
StandingBrainProvider (abstract)
  ├── ClaudeCLIProvider    → claude --print --input-format stream-json ...
  ├── GeminiCLIProvider    → gemini PTY stdin/stdout (existing pattern)
  └── OpenAIPythonProvider → openai.chat.completions.create(stream=True)
```

### Model Config (in .env or config.py)
```
# Claude tiers
BRAIN_LIGHT_CLAUDE=claude-haiku-4-5-20251001
BRAIN_MEDIUM_CLAUDE=claude-sonnet-4-6
BRAIN_HEAVY_CLAUDE=claude-opus-4-6

# Gemini tiers
BRAIN_LIGHT_GEMINI=gemini-2.5-flash
BRAIN_MEDIUM_GEMINI=gemini-2.5-pro
BRAIN_HEAVY_GEMINI=gemini-2.5-pro

# OpenAI tiers
BRAIN_LIGHT_OPENAI=gpt-4.1-mini
BRAIN_MEDIUM_OPENAI=gpt-4.1
BRAIN_HEAVY_OPENAI=o3
```

### Shared State (One Jane Identity)
- All 3 brains share the same ChromaDB (short-term, long-term, file index)
- All 3 brains share the same conversation history (unified session)
- All 3 brains get the same personality and user profile
- Context depth varies by PromptProfile (greeting=slim, hard=full)
- Conversation turns from any brain get written to the shared history
- Provider switch preserves all memory and history — only the brain changes

## Steps

### 1. Prototype stream-json I/O
- Test bidirectional stream-json with a simple script:
  ```bash
  echo '{"type":"user","content":"hi"}' | claude --print --input-format stream-json --output-format stream-json
  ```
- Understand the JSON message format for input and output
- Document the event types and how to detect response completion

### 2. Build StandingBrainManager (new file: jane/standing_brain.py)
- Class that manages long-lived Claude CLI processes
- One process per model tier (haiku, sonnet, opus)
- Methods:
  - `start(model)` — spawn the process with stream-json flags
  - `send(model, prompt_text) -> async generator[str]` — write to stdin, yield response chunks from stdout
  - `health_check(model)` — verify process is alive
  - `restart(model)` — kill and respawn if stuck
  - `shutdown()` — clean termination of all processes
- Asyncio-based with non-blocking I/O (like persistent_gemini.py pattern)
- Auto-restart on crash with backoff

### 3. Integrate with jane_proxy.py
- Replace `_execute_brain_stream()` calls to persistent_claude with standing_brain
- Classifier picks level → level maps to brain tier → route to correct standing process
- Keep persistent_claude.py as fallback if standing brain fails

### 4. Handle conversation context
- Each brain process maintains its own internal context (Claude CLI remembers prior turns)
- But we also need cross-brain context: if haiku answered a greeting, opus should know
- Solution: prepend a "recent conversation summary" to each message sent to the brain
- The context_builder already does this — just ensure it includes turns from all brains

### 5. Session and lifecycle management
- Start all 3 brains at jane-web startup (alongside gemma pre-warm)
- Idle timeout: kill brain if no messages for 30 min, restart on next request
- Token rotation: when a brain hits 70% context, summarize and restart fresh
- Process monitoring: health check every 60s, auto-restart dead brains

### 6. Testing
- Send greeting → verify haiku responds via standing brain (no subprocess spawn)
- Send complex question → verify opus responds via standing brain
- Kill a brain process → verify auto-restart works
- Measure latency: greeting should be <2s, complex should be <5s (excluding API thinking time)

## Verification
- `ps aux | grep claude` shows 3 standing processes (haiku, sonnet, opus)
- Greeting response time < 2s (currently 9s)
- No `subprocess.Popen` in the hot path for messages
- All 3 brains share conversation history in ChromaDB
- Brains auto-restart after crash or idle timeout
- Timing logs show no "process spawn" stage

## Files Involved
- `jane/standing_brain.py` (NEW — core implementation)
- `jane_web/jane_proxy.py` — route to standing brain instead of persistent_claude
- `jane_web/main.py` — start standing brains at startup
- `jane/persistent_claude.py` — kept as fallback, no longer primary path
- `jane/context_builder.py` — ensure cross-brain context works

## Notes
- The `--input-format stream-json` flag is key — need to verify exact JSON schema Claude CLI expects
- The opus brain needs `--dangerously-skip-permissions` for tool use (file read/write/bash)
- Haiku and sonnet brains may not need tool permissions since they handle simple/medium tasks
- This is the same pattern as persistent_gemini.py (PTY + stdin/stdout) but with structured JSON instead of terminal scraping
- RAM: ~1.5 GB total for all 3 brains (5% of 31 GB available)
- This also fixes the "Jane is offline" flicker — single-worker uvicorn won't block on subprocess spawn during health checks
