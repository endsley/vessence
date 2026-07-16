# Transcript Quality Review — 2026-07-15

Generated: 2026-07-16 00:07:19

## Issue 1 [CRITICAL]

**Turn:** 2026-07-15 00:03:52
**User said:** # Task: Self-heal android_crash_report: === VESSENCE CRASH REPORT ===

**Problem:** Stage 3 failed to complete the crash-report self-heal request; the client disconnected after fallback failures.

**Root cause:** Stage 1 correctly escalated the complex request as others:Low, but Stage 3 routed to Claude despite Claude being over spend limit, then the Codex/OpenAI fallback failed and the stream was cancelled after about 70s.

**Suggested fix:** Add provider health checks/circuit breakers before routing, skip exhausted providers, validate fallback model names, and return a queued/deferred-task ACK instead of streaming until timeout for long code-repair work.

**Log evidence:**
```
2026-07-15 00:03:50 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (9161ms) params={}
```
```
2026-07-15 00:03:51 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1622 sid_override=True class_protocol=n/a
```
```
2026-07-15 00:03:52 INFO [jane.proxy] [audit-178408] stream_message brain=Claude history=0 msg_len=1622 file_ctx=False
```
```
2026-07-15 00:03:56 WARNING [jane.proxy] [audit-178408] Claude brain exhausted (You've hit your org's monthly spend limit · run /usage-credits to ask your admin for a higher limit) - disconnecting Claude and switching Jane to Codex
```
```
2026-07-15 00:04:10 WARNING [agent_skills.claude_cli_llm] Fallback to openai failed: Command '['codex', 'exec', '--dangerously-bypass-approvals-and-sandbox', '-m', 'gpt-5.4-mini', 'Extr...
```
```
2026-07-15 00:05:03 WARNING [jane.proxy] [audit-178408] Brain execution cancelled (stream) after 70478ms — likely client disconnect or timeout.
```

---

## Issue 2 [LOW]

**Turn:** 2026-07-15 23:45:09
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 1 emitted an unsupported intent label before falling back to others.

**Root cause:** The classifier returned unknown class 'force stage3', which is not in the canonical class set. Routing still escalated correctly, but the classifier contract is drifting.

**Suggested fix:** Constrain classifier output to the canonical enum and map any internal force-stage3 sentinel before logging; add a regression test for meta/code questions.

**Log evidence:**
```
2026-07-15 23:45:07 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-07-15 23:45:07 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (2851ms) params={}
```

---

## Issue 3 [CRITICAL]

**Turn:** 2026-07-15 23:45:43
**User said:** use the source code as your guide

**Problem:** Follow-up context was lost before Stage 3.

**Root cause:** The turn depends on the prior architecture question, but Stage 3 was invoked with history=0 and file_ctx=False, so the brain received only the short anaphoric prompt without the previous question or source context.

**Suggested fix:** Persist and pass per-session conversation history into Stage 3 for sid_override sessions; if history is unavailable and the prompt is anaphoric, combine it with the previous turn or ask for clarification. For code-grounded prompts, trigger repo/source inspection before answering.

**Log evidence:**
```
[2026-07-15 23:45:09] (audit-178417) right now, you are using the same codex process for each prompt instead of spawning a new one each time right for the stage 3 brain?
```
```
[2026-07-15 23:45:43] (audit-178417) use the source code as your guide
```
```
2026-07-15 23:45:43 INFO [jane.proxy] [audit-178417] stream_message brain=OpenAI history=0 msg_len=33 file_ctx=False
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-07-15 23:48:06
**User said:** please familiarize yourself with the waterlily project

**Problem:** Stage 1 took almost a minute before escalating.

**Root cause:** The classifier returned others:Low only after 58,758ms, making the fast classifier the latency bottleneck before Stage 3 even started.

**Suggested fix:** Put a hard timeout around Stage 1 and default timeout/unknown to others:Low Stage 3; warm or restart the classifier backend when latency spikes.

**Log evidence:**
```
2026-07-15 23:48:03 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (58758ms) params={}
```
```
2026-07-15 23:48:05 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=54 sid_override=True class_protocol=n/a
```
```
2026-07-15 23:48:06 INFO [jane.proxy] [audit-178417] stream_message brain=OpenAI history=0 msg_len=54 file_ctx=False
```

---

