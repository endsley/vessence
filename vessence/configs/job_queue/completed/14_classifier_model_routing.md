# Job: Classifier-Based Model Routing — Right Model for Each Message

Status: complete
Completed: 2026-03-24 00:40 UTC
Notes: Added _CLASSIFIER_MODEL_MAP and _resolve_model_for_brain() to jane_proxy.py. Both sync and stream brain paths accept model_override. Classifier's model recommendation (haiku/sonnet/opus) maps to real model IDs. WEB_CHAT_MODEL remains default fallback.
Priority: 1
Model: sonnet
Created: 2026-03-23
Depends on: Job #04 (Intent Classifier)

## Objective
Use the Gemma3:4b classifier to automatically route each web/Android message to the optimal model (gemma/haiku/sonnet/opus) based on difficulty. Save tokens and reduce latency for simple messages while preserving full power for complex tasks.

## Benchmark Results (2026-03-23)
- Accuracy: 10/10 correct classifications
- Warm latency: 1.0-1.4s per classification
- Cold start: 33.8s (one-time GPU model load)

## Certainty-Based Bump-Up + Keyword Heuristic

The classifier returns a certainty score (0-100). Combined with keyword detection:

| Certainty | Action |
|-----------|--------|
| 90-100 | Trust the classification as-is |
| 70-89 | Bump up one level (simple→medium, medium→hard) |
| <70 | Default to Opus (too uncertain to risk under-provisioning) |

**Keyword heuristic (code-side, no LLM):** If message contains "build", "implement", "entire", "from scratch", "all files", "every endpoint", "redesign", "migrate", "audit all" — force hard/opus regardless of classifier output. These patterns consistently fool Gemma into medium when they're actually hard.

**Conversation continuity:** If previous 3 messages were hard, bump next classification to at least medium — "ok do it" after complex discussion = "execute the complex plan."

## Classification Prompt (tested and validated)
**V3 short prompt — 10/10 on standard test, 85% on extended (hard detection improved by bump-up rule)**
```
You are a message classifier for Jane, an AI assistant. Classify the user's message into one of 4 levels and recommend a model.

## Levels
GREETING — casual social interaction, no work needed
SIMPLE — quick lookup, status check, short factual answer
MEDIUM — requires reasoning, investigation, or multi-step work
HARD — complex task requiring deep analysis, code generation, or long-running work

## Examples

### GREETING (10 examples)
- "hey" → greeting
- "good morning" → greeting
- "thanks" → greeting
- "ok got it" → greeting
- "sounds good" → greeting
- "bye" → greeting
- "night" → greeting
- "cool" → greeting
- "hey jane you there?" → greeting
- "yo" → greeting

### SIMPLE (10 examples)
- "show me the job queue" → simple
- "what's the weather" → simple
- "how many files in my vault" → simple
- "is ollama running" → simple
- "what model are you using" → simple
- "when was the last backup" → simple
- "list my briefing topics" → simple
- "what time is it" → simple
- "show me recent prompts" → simple
- "how much disk space do I have" → simple

### MEDIUM (10 examples)
- "investigate why the briefing fetch failed" → medium
- "update the daily briefing with new content" → medium
- "fix the broken import in ambient_heartbeat.py" → medium
- "add a dismiss button to the briefing cards" → medium
- "check the crash logs and tell me what happened" → medium
- "switch the tunnel to HTTP/2" → medium
- "add a new topic to the daily briefing" → medium
- "why is the web response slow" → medium
- "can you look into the memory leak" → medium
- "run the job queue" → medium

### HARD (10 examples)
- "refactor the auth system to use OAuth" → hard
- "build the tax accountant essence" → hard
- "do a deep stability audit of all code" → hard
- "redesign the Android home screen" → hard
- "implement the intent classifier with Gemma" → hard
- "write tests for every API endpoint" → hard
- "migrate the entire folder structure" → hard
- "build a new essence from scratch" → hard
- "audit all 20 files for crash-prone patterns and fix them" → hard
- "implement zero-downtime deployment" → hard

## Model mapping
- greeting → gemma (handle locally, no cloud call)
- simple → haiku
- medium → sonnet
- hard → opus

## Conversation continuity
If the previous 3 messages were classified as "hard" (deep work), classify the next message as at least "medium" even if it looks simple — because "ok do it" after a complex discussion means "execute that complex plan."

## Context about the user
Name: {user_name}
Time: {time_of_day}, {day_of_week}
Last interaction: {last_interaction_ago}
Pending jobs: {pending_job_count}
Recent completions: {recent_completions}

## Instructions
1. Read the message carefully
2. Match it to the closest example category
3. If unsure between two levels, pick the HIGHER one (better to over-provision than under)
4. Rate your certainty 0-100 (0=wild guess, 100=absolutely sure). Be honest.
5. Generate a natural acknowledgment that varies each time — no canned responses
6. Reply ONLY as JSON: {"level": "...", "model": "...", "certainty": 0-100, "response": "..."}

Message: "{user_message}"
```

## Implementation

### 1. Create `agent_skills/intent_classifier.py`
- `classify(message, recent_history=None)` → returns `{"level", "model", "certainty", "response"}`
- Calls Gemma3:4b via Ollama (env var `INTENT_CLASSIFIER_MODEL`, default `claude-haiku-4-5-20251001`)
- Builds the prompt with user context (name, time, pending jobs, etc.)
- Includes conversation continuity check (last 3 messages)
- Strips `<think>` tags if using deepseek
- Returns parsed JSON, falls back to `{"level": "medium", "model": "sonnet", "certainty": 50}` on parse failure
- **Post-classification adjustments:**
  1. Certainty bump-up: if certainty <90, bump level up one tier
  2. If certainty <70, force hard/opus
  3. Keyword heuristic: if message contains hard-indicator words ("build", "implement", "entire", "from scratch", "audit all", "redesign", "migrate"), override to hard/opus
  4. Conversation continuity: if last 3 levels were hard, bump to at least medium

### 2. Update `jane_web/jane_proxy.py`
- Before the brain call, run `classify(message)`
- If level is `greeting`: send Gemma's response directly, skip brain entirely
- If level is `simple/medium/hard`:
  - Send Gemma's acknowledgment to the client immediately (as a status event)
  - Pass `model` from classifier to the brain call (override the default model)
  - Stream the real response when ready

### 3. Model override in brain call
- `_execute_brain_stream()` currently uses whatever model the persistent session was created with
- Add a `model_override` parameter that the classifier can set
- For persistent Claude sessions: first turn uses the classified model, subsequent turns in the same session keep it (don't switch mid-conversation)

### 4. Conversation continuity tracking
- Store the last 3 classification levels in the session state
- If all 3 are "hard", bump the next classification to at least "medium"
- Reset when the conversation topic clearly changes (new greeting = reset)

### 5. Logging for tuning
- Log every classification: `timestamp | message_preview | level | model | response_time_ms`
- Write to `logs/classifier.log`
- Periodically review for misclassifications and add those as new examples

## User Override
- If message contains "think hard" or "use opus" → force opus regardless of classification
- If message contains "quick" → force haiku
- These are escape hatches, not normal flow

## Files Involved
- New: `agent_skills/intent_classifier.py`
- Update: `jane_web/jane_proxy.py` — classify before brain call, model routing
- Update: `jane/brain_adapters.py` — accept model_override parameter
- Update: `jane/persistent_claude.py` — model selection per turn
- New: log file `logs/classifier.log`

## Notes
- Classifier model is local-only (Gemma3:4b via env var) — Docker default is Haiku
- 40 few-shot examples give strong pattern anchoring
- "If unsure, pick higher" prevents under-provisioning
- The classifier + ack is one Ollama call, not two (classify and respond in one shot)
- Cold start (33.8s) happens once per Ollama session — keep Gemma loaded
