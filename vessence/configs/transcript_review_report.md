# Transcript Quality Review — 2026-07-12

Generated: 2026-07-13 23:51:19

## Issue 1 [MEDIUM]

**Turn:** 2026-07-12 23:45:44
**User said:** use the source code as your guide

**Problem:** Stage 3 did not attach or inspect source context after an explicit source-code instruction.

**Root cause:** The turn routed to generic Stage 3 as others:Low, but the proxy logged file_ctx=False and the standing brain used only recent history. No code map/source-injection log appeared.

**Suggested fix:** Update the Stage 3 code-intent detector to treat phrases like "use the source code" and follow-ups to code-architecture questions as code-context requests, then inject the code map or route to the code-capable brain.

**Log evidence:**
```
2026-07-12 23:45:39 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1790ms) params={}
```
```
2026-07-12 23:45:43 INFO [jane.proxy] [audit-178391] stream_message brain=Claude history=0 msg_len=33 file_ctx=False
```
```
2026-07-12 23:45:44 INFO [jane.proxy] [audit-178391] Standing brain turn 6 — injected recent history only
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-07-12 23:46:03
**User said:** please familiarize yourself with the waterlily project

**Problem:** Project familiarization was handled as a short generic chat response instead of a source-inspection task.

**Root cause:** The turn escalated to Stage 3 with no file context, no code-map injection, and a 99-character result after about 2.3 seconds, which is not enough evidence of repository inspection.

**Suggested fix:** Route explicit project-familiarization requests to a code/repo inspection path that reads project files and reports what was inspected before claiming familiarity.

**Log evidence:**
```
2026-07-12 23:46:01 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1140ms) params={}
```
```
2026-07-12 23:46:03 INFO [jane.proxy] [audit-178391] stream_message brain=Claude history=0 msg_len=54 file_ctx=False
```
```
2026-07-12 23:46:03 INFO [jane.proxy] [audit-178391] Standing brain turn 7 — injected recent history only
```
```
2026-07-12 23:46:05 INFO [jane.standing_brain] Brain [claude-sonnet-5] turn 8 complete in 2302ms (99 chars, 1 raw events)
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-07-12 23:46:10
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 1 rejected a valid web_automation classification because qwen returned the label with a space.

**Root cause:** The classifier warned that qwen returned unknown class 'web automation'. Source inspection shows the registered class is web_automation, while parsed labels are only lowercased before allowed-class validation, so the space/underscore variant was dropped to others and Stage 3 received no web_automation class protocol.

**Suggested fix:** Canonicalize parsed classifier labels before validation: normalize spaces and underscores against the class registry, then return the registry key such as web_automation. Also constrain qwen output to the runtime class enum.

**Log evidence:**
```
2026-07-12 23:46:09 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-07-12 23:46:09 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1800ms) params={}
```
```
2026-07-12 23:46:10 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=750 sid_override=True class_protocol=n/a
```

---

## Issue 4 [CRITICAL]

**Turn:** 2026-07-12 23:48:13
**User said:** # Task: Self-heal android_crash_report: === VESSENCE CRASH REPORT ===

**Problem:** Foreground handling was delayed by failing LLM fallback attempts before Stage 3 began.

**Root cause:** Stage 1 completed at 23:46:28, but Stage 3 escalation did not start until 23:48:13. In between, the primary Claude CLI hit the monthly spend limit, OpenAI/Codex fallback failed repeatedly, and the web heartbeat failed.

**Suggested fix:** Add a provider circuit breaker and time-box fallback attempts. Do not block the foreground pipeline on self-healing or audit LLM subprocesses; move them to a background worker or return an explicit provider-unavailable error.

**Log evidence:**
```
2026-07-12 23:46:28 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (5873ms) params={}
```
```
2026-07-12 23:46:37 WARNING [agent_skills.claude_cli_llm] Fallback to openai failed: Command '['codex', 'exec', '--dangerously-bypass-approvals-and-sandbox', '-m', 'gpt-5.4-mini', 'Extr...
```
```
2026-07-12 23:47:14 WARNING [agent_skills.claude_cli_llm] Fallback to openai failed: Command '['codex', 'exec', '--dangerously-bypass-approvals-and-sandbox', '-m', 'gpt-5.4-mini', 'Extr...
```
```
2026-07-12 23:47:44 WARNING [jane.web] heartbeat ping failed (1 in a row):
```
```
2026-07-12 23:48:13 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1622 sid_override=True class_protocol=n/a
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-07-12 23:48:13
**User said:** # Task: Self-heal android_crash_report: === VESSENCE CRASH REPORT ===

**Problem:** Self-heal crash report was routed to generic Stage 3 chat with no evidence of repair execution.

**Root cause:** The crash report was classified as others:Low and escalated with class_protocol=n/a and file_ctx=False. The standing brain returned only a 99-character response in 2.6 seconds; no code-lock, file-read, patch, build, or verification logs appear.

**Suggested fix:** Detect android_crash_report/self-heal payloads and route them to the self-healing repair executor or Codex job path with source access, code lock acquisition, patching, and verification. If repair cannot run, say so explicitly.

**Log evidence:**
```
2026-07-12 23:48:13 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1622 sid_override=True class_protocol=n/a
```
```
2026-07-12 23:48:13 INFO [jane.proxy] [audit-178391] stream_message brain=Claude history=0 msg_len=1622 file_ctx=False
```
```
2026-07-12 23:48:16 INFO [jane.standing_brain] Brain [claude-sonnet-5] turn 10 complete in 2643ms (99 chars, 1 raw events)
```
```
2026-07-12 23:48:16 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (3409ms)
```

---

