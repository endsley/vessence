# Architecture

## Web Request Lifecycle
```
Browser/Android → Cloudflare Tunnel → jane_web/main.py (routes)
  → jane_proxy.py: stream_message() or send_message()
    → intent_classifier.py (gemma3:4b): classify level → greeting/simple/medium/hard
    → context_builder.py: build system prompt (greeting=slim, hard=full memory+task state)
    → standing_brain.py: StandingBrainManager.send(tier, message, system_prompt)
        (persistent_claude.py / persistent_gemini.py as fallback cold-start)
    → conversation_manager.py: persist turns to ChromaDB
```

## Model Routing
```
gemma3:4b (classifier only, never responds) → determines tier
  greeting/simple → light  (slim context, no memory retrieval)
  medium          → medium (full context + memory + task state)
  hard            → heavy  (full context + memory + task state + research)

Default models per provider (all overridable via env vars):
  Claude  → light=haiku-4-5, medium=sonnet-4-6,   heavy=opus-4-6
  Gemini  → light=flash,     medium=pro,           heavy=pro
  OpenAI  → light=gpt-4.1-mini, medium=gpt-4.1,   heavy=o3
Active provider set by JANE_BRAIN env var (claude|gemini|openai)
```

## Standing Brain Sessions
```
3 long-lived CLI processes per provider (light/medium/heavy tiers)
  System prompt injected on turn 1 only — subsequent turns send raw message
  Forced restart after 20 turns (MAX_TURNS_BEFORE_REFRESH) to refresh context
  Reaper (every 60s): auto-restart dead brains; kill only if idle (5+ min) AND
    CPU >15% sustained for 1 hour — never kills brains actively handling work
Prompt Queue: dedicated "prompt_queue_session" via internal API (localhost:8081)
```

## Memory Flow
```
User message → librarian (gemma3:4b) queries ChromaDB
  → short_term_memory (14-day TTL, concise summaries)
  → long_term_memory (permanent facts, shared with Amber)
  → context_builder assembles into system prompt
Write: conversation_manager.py summarizes turns → ChromaDB
```

## Cron Pipeline (nightly 2:00-6:00 AM)
```
2:00  usb_sync.py          (incremental backup)
2:10  run_briefing.py       (daily news, gemma3:12b summaries)
2:15  janitor_memory.py     (ChromaDB cleanup)
2:30  check_for_updates.py
3:00  janitor_system.py     (system maintenance)
3:15  regenerate_jane_context.py
4:00  generate_identity_essay.py
4:15  generate_code_map.py  (this index)
5:00  ambient_heartbeat.py
```

## Key Directories
```
jane_web/     → FastAPI web server (routes, auth, streaming)
jane/         → Brain adapters, persistent sessions, context builder
vault_web/    → HTML templates (jane.html, app.html, briefing.html)
agent_skills/ → Standalone scripts (classifier, memory, TTS, queue)
amber/        → Google ADK agent (Amber's brain)
essences/     → Self-contained AI agent packages
```

<!-- AUTO-GENERATED BELOW — do not edit below this line -->

# Code Map Index

Split into three targeted maps:
- `CODE_MAP_CORE.md` — Python backend (jane/, agent_skills/, amber/, startup_code/)
- `CODE_MAP_WEB.md` — Web frontend (vault_web/templates/)
- `CODE_MAP_ANDROID.md` — Android app (Kotlin)

Run `python agent_skills/generate_code_map.py` to regenerate all, or pass `core`, `web`, or `android` to regenerate one.
