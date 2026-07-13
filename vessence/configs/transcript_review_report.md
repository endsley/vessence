# Transcript Quality Review — 2026-07-11

Generated: 2026-07-12 23:49:25

## Issue 1 [CRITICAL]

**Turn:** 2026-07-11 00:03:03
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 3 did not complete the requested project-familiarization turn.

**Root cause:** The classifier backend had already failed with Ollama/Qwen 500s and ack generation also failed, then the escalated brain stream ran for about 132s before the client disconnected and the server cancelled brain execution.

**Suggested fix:** Add a bounded Stage 3 execution timeout with a resumable background-task path: return an immediate status response, keep the Codex/brain task running server-side when appropriate, and expose completion/progress instead of cancelling on client stream disconnect.

**Log evidence:**
```
2026-07-11 00:02:54 WARNING [intent_classifier.v3.classifier] v3: qwen call failed (Server error '500 Internal Server Error' for url 'http://localhost:11434/api/generate'
```
```
2026-07-11 00:02:58 WARNING [jane_web.jane_v2.pipeline] ack generation failed (Server error '500 Internal Server Error' for url 'http://localhost:11434/api/generate'
```
```
2026-07-11 00:05:10 INFO [jane.proxy] [audit-178374] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-07-11 00:05:10 WARNING [jane.proxy] [audit-178374] Brain execution cancelled (stream) after 126733ms — likely client disconnect or timeout. Stack:
```
```
2026-07-11 00:05:10 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (132054ms)
```

---

## Issue 2 [LOW]

**Turn:** 2026-07-11 23:45:12
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 1 reported an unknown class from the classifier.

**Root cause:** Qwen returned 'force stage3', which is not in the allowed intent taxonomy, so the pipeline coerced it to others:Low. The fallback routing to Stage 3 was acceptable for this complex source-code question, but the classifier prompt/schema allowed an invalid label.

**Suggested fix:** Constrain classifier output to the canonical enum with strict JSON/schema validation, and add a classifier normalization/test case for source-code inspection requests so invalid labels like 'force stage3' cannot be emitted.

**Log evidence:**
```
2026-07-11 23:45:10 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-07-11 23:45:10 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (4696ms) params={}
```
```
2026-07-11 23:45:11 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=132 sid_override=True class_protocol=n/a
```

---

## Issue 3 [CRITICAL]

**Turn:** 2026-07-11 23:47:34
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 3 returned an implausibly short response for a large code-modification request.

**Root cause:** The request was escalated to Stage 3, but the brain result was only 99 characters after about 1.8s. Nearby logs show the primary Claude CLI was failing due to the org monthly spend limit, while the standing brain still emitted a tiny canned result instead of performing source inspection or implementation.

**Suggested fix:** Treat provider spend-limit errors as a hard degraded-state signal for Stage 3 coding tasks; do not return a generic 99-character completion. Route to a configured working fallback brain with tools, or return a clear failure/status response.

**Log evidence:**
```
2026-07-11 23:47:32 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-07-11 23:47:33 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=750 sid_override=True class_protocol=n/a
```
```
2026-07-11 23:47:34 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI (claude) failed (exit 1): You've hit your org's monthly spend limit · run /usage-credits to ask ... Attempting fallback.
```
```
2026-07-11 23:47:36 INFO [jane.standing_brain] Brain [claude-sonnet-5] result event: result_len=99, accumulated=99, lines_read=3
```
```
2026-07-11 23:47:36 INFO [jane.standing_brain] Brain [claude-sonnet-5] turn 4 complete in 1821ms (99 chars, 1 raw events)
```

---

## Issue 4 [CRITICAL]

**Turn:** 2026-07-11 23:47:47
**User said:** # Task: Self-heal android_crash_report: === VESSENCE CRASH REPORT ===

**Problem:** Stage 3 did not actually self-heal the Android crash report.

**Root cause:** The crash-report task was correctly escalated as a complex request, but the standing brain again returned only 99 characters in about 2.4s. Subsequent logs show Claude spend-limit failures and OpenAI fallback failure, so the configured frontier brain path was not capable of completing the requested diagnosis/fix.

**Suggested fix:** Add health checks before accepting self-heal/coding tasks: verify the configured Stage 3 provider and fallback can run with tools. If unavailable, fail fast with an actionable error instead of producing a tiny generic answer.

**Log evidence:**
```
2026-07-11 23:47:46 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (7668ms) params={}
```
```
2026-07-11 23:47:47 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1622 sid_override=True class_protocol=n/a
```
```
2026-07-11 23:47:50 INFO [jane.standing_brain] Brain [claude-sonnet-5] result event: result_len=99, accumulated=99, lines_read=3
```
```
2026-07-11 23:47:50 INFO [jane.standing_brain] Brain [claude-sonnet-5] turn 5 complete in 2376ms (99 chars, 1 raw events)
```
```
2026-07-11 23:47:54 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI (claude) failed (exit 1): You've hit your org's monthly spend limit · run /usage-credits to ask ... Attempting fallback.
```
```
2026-07-11 23:48:26 WARNING [agent_skills.claude_cli_llm] Fallback to openai failed: Command '['codex', 'exec', '--dangerously-bypass-approvals-and-sandbox', '-m', 'gpt-5.4-mini', 'Extr...
```

---

## Issue 5 [MEDIUM]

**Turn:** 2026-07-11 23:47:52
**User said:** unknown short follow-up after crash-report prompt

**Problem:** Stage 1 short-circuited a likely continuation as unclear instead of preserving the active complex-task flow.

**Root cause:** Immediately after the crash-report task, the classifier produced unclear:Very High and the pipeline short-circuited at Stage 2. No pending_action resolver entry appears in the logs, so the follow-up was not routed back to the active Stage 3/task context.

**Suggested fix:** For active Stage 3 coding/self-heal sessions, create a pending action or session continuation token so short follow-ups route back to Stage 3 unless explicitly unrelated.

**Log evidence:**
```
2026-07-11 23:47:52 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 unclear:Very High (1166ms) params={}
```
```
2026-07-11 23:47:53 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: unclear short-circuit (classifier verdict)
```
```
2026-07-11 23:47:53 INFO [jane.proxy] [audit-178382] Persistence worker started stage=stage2 cls=unclear user_chars=39 assistant_chars=82
```

---

