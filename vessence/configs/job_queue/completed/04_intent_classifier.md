# Job: Intent Classifier — Triage + Instant Acknowledgment Layer

Status: complete
Completed: 2026-03-24 00:35 UTC
Notes: intent_classifier.py created (230 lines). jane_proxy.py updated — classifier runs before brain call, greetings skip pipeline entirely. Certainty bump-up, keyword heuristic, conversation continuity all implemented. INTENT_CLASSIFIER_MODEL=gemma3:4b set in .env.
Priority: 1
Model: sonnet
Created: 2026-03-23

## Objective
Add a fast triage layer (Gemma3:4b locally, Haiku for Docker) that classifies every incoming web/Android message into 4 difficulty levels and immediately responds with a natural acknowledgment before the full pipeline runs. This gives users a conversational feel — no more staring at dots.

## Classifier Model
- Local: `gemma3:4b` via Ollama (env var `INTENT_CLASSIFIER_MODEL`, default `claude-haiku-4-5-20251001`)
- Local machine: set `INTENT_CLASSIFIER_MODEL=gemma3:4b` in local .env

## 4 Classification Levels

| Level | Examples | Gemma Acknowledgment | Then what |
|-------|----------|---------------------|-----------|
| **greeting** | "hey", "hi", "morning", "you there?" | Gemma responds directly with a personalized greeting. **Done — no handoff.** | Nothing |
| **simple** | "show me the job queue", "what time is it", "how's the server" | Quick natural ack: "On it." / "Let me check." / "One sec." | Kick off full pipeline |
| **medium** | "investigate the crash logs", "update the briefing", "fix the broken import" | Natural ack: "Sure, looking into that now." / "Yep, give me a moment on this." | Kick off full pipeline |
| **hard** | "refactor the auth system", "build the tax accountant essence", "run the full job queue" | Scoped ack: "That's a big one — I'll work through it and check in with you along the way." | Kick off full pipeline + periodic progress updates |

## Key Design Decisions
1. **Gemma never answers questions** — only greetings get a full Gemma response. Everything else is just an acknowledgment + handoff.
2. **No canned responses** — Gemma generates fresh, varied acknowledgments each time. Prompt includes Jane's personality + the user's message so the ack feels natural.
3. **Drop "quick factual" as a category** — too risky for Gemma to distinguish "what time is it" from "what was our last mistake". Both go to full pipeline.
4. **Acknowledgments ("thanks", "ok", "got it")** — treated as greetings. Gemma responds directly, no handoff.
5. **Farewells ("bye", "night")** — treated as greetings. Gemma responds directly, no handoff.

## Flow
```
Message arrives (web/Android only, not CLI)
    ↓
Gemma classifies: greeting / simple / medium / hard  (<200ms)
    ↓
├── greeting/ack/farewell:
│     Gemma generates personalized response using greeting context
│     → Send to user. Done.
│
├── simple/medium:
│     Gemma generates natural acknowledgment
│     → Send ack to user immediately
│     → Kick off full pipeline in background
│     → Stream real response when ready
│
└── hard:
      Gemma generates scoped acknowledgment (mentions it'll take time)
      → Send ack to user immediately
      → Kick off full pipeline in background
      → Send periodic progress updates via live broadcast
      → Stream real response when ready
```

## Greeting Context (pre-built, cached, <50ms)

**Static facts (from user_profile.md, loaded once at startup):**
- User's name
- Family members
- Profession
- Communication style
- Hobbies/interests

**Dynamic facts (cheap system checks, no LLM/ChromaDB):**
- Current time + day of week + workday/weekend
- Time since last interaction
- Pending job queue count
- Pending prompt queue count
- Whether Jane is currently working on a background task
- Recent completions to report
- System health (Ollama up/down, services running)

**Classifier + Acknowledgment Prompt:**
```
You are Jane, a technical partner and friend. Classify this message and respond.

User: the user (friend)
Time: 8:42 PM EDT, Friday
Last seen: 3 hours ago
Background: 2 jobs queued, briefing just finished
Tone: warm, direct, no filler. Vary your phrasing every time.

Message: "{user_message}"

1. Classify as: greeting, simple, medium, or hard
2. Generate a natural acknowledgment (1-2 sentences max)
   - greeting: respond warmly, mention something relevant if available
   - simple: brief ack like "On it." or "Let me check."
   - medium: slightly longer: "Looking into that now."
   - hard: scope it: "That's a solid chunk of work — I'll dig in and keep you posted."

Reply as JSON: {"level": "...", "response": "..."}
```

## Files Involved
- New: `agent_skills/intent_classifier.py` — classify(), build_greeting_context(), generate_ack()
- Update: `jane_web/jane_proxy.py` or `jane_web/main.py` — intercept before brain call, send ack, then run pipeline
- Update: `jane/context_builder.py` — accept difficulty level, optimize context loading per level
- Read: `user_profile.md` — cached at startup
- Read: job queue, prompt queue, system state — for dynamic context

## Notes
- CLI is excluded — Claude Code handles its own interaction
- Classifier should be <200ms (Gemma3:4b is fast enough)
- If classifier fails, default to full pipeline with no ack (never block the user)
- Log every classification for tuning: "message → level → ack sent → pipeline result"
- The ack appears as a regular Jane message in the chat — then the real response follows as a second message (or replaces the ack via streaming)
