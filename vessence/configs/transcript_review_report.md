# Transcript Quality Review — 2026-06-16

Generated: 2026-06-17 01:27:50

## Issue 1 [LOW]

**Turn:** 2026-06-16 01:10:45
**User said:** you have access to the water lily Wellness project right

**Problem:** Stage 1 emitted an out-of-schema intent label before falling back to others.

**Root cause:** The classifier returned 'web automation', which is not in the allowed intent set, so the classifier wrapper coerced it to others. Routing was acceptable, but the classifier contract is not tight.

**Suggested fix:** Constrain the classifier output to the canonical enum and add tests for project/codebase questions so they resolve directly to others/escalate without unknown-label warnings.

**Log evidence:**
```
2026-06-16 01:10:43 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-16 01:10:43 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (6151ms) params={}
```

---

## Issue 2 [LOW]

**Turn:** 2026-06-16 01:11:10
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 1 emitted an out-of-schema intent label before falling back to others.

**Root cause:** The classifier returned 'force stage3', which is not a valid class. The fallback still escalated correctly, but this shows the classifier prompt/parser permits non-enum labels.

**Suggested fix:** Make Stage 1 reject or normalize only known enum values at the model-output schema level; add a regression case for meta/system architecture questions.

**Log evidence:**
```
2026-06-16 01:11:08 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-06-16 01:11:08 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1136ms) params={}
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-06-16 01:11:56
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 3 took over three minutes for a repository-familiarization request.

**Root cause:** The turn escalated correctly to Stage 3, but the brain stream ran for 188127ms before finishing. No handler/client issue is shown, but Stage 3 latency is severe for an interactive assistant.

**Suggested fix:** Add a bounded repo-orientation path for Stage 3: gather key files with a time budget, stream progress, and return a concise status instead of allowing a long unbounded exploration.

**Log evidence:**
```
2026-06-16 01:11:56 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=54 sid_override=True class_protocol=n/a
```
```
2026-06-16 01:15:04 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (188127ms)
```

---

## Issue 4 [CRITICAL]

**Turn:** 2026-06-16 01:15:32
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 3 failed to complete a large implementation request before the client disconnected/cancelled.

**Root cause:** Stage 1 escalated correctly, but the primary LLM timed out after 45s, fallback continued for about 14.5 minutes, then the client disconnected and brain execution was cancelled. The user likely received no completed result.

**Suggested fix:** For long code tasks, switch Stage 3 to a durable background job with progress events and resumable results, or reject voice/stream execution into a task mode before starting. Also increase observability around primary/fallback LLM timeout boundaries.

**Log evidence:**
```
2026-06-16 01:15:07 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-16 01:15:51 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-16 01:30:05 INFO [jane.proxy] [audit-178158] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-06-16 01:30:05 WARNING [jane.proxy] [audit-178158] Brain execution cancelled (stream) after 872942ms — likely client disconnect or timeout. Stack:
```
```
2026-06-16 01:30:05 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (873576ms)
```

---

