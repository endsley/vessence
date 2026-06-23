# Transcript Quality Review — 2026-06-22

Generated: 2026-06-23 01:36:27

## Issue 1 [LOW]

**Turn:** 2026-06-22 01:10:10
**User said:** you have access to the water lily Wellness project right

**Problem:** Stage 1 emitted an unsupported intent label before falling back to others.

**Root cause:** The classifier returned 'web automation', which is not in the accepted class set. The pipeline converted it to others:Low and escalated to Stage 3, so routing was probably safe, but classifier protocol compliance failed.

**Suggested fix:** Constrain classifier output to the allowed enum, or add an explicit alias mapping for project/web automation requests to a supported Stage 3 category.

**Log evidence:**
```
2026-06-22 01:10:09 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-22 01:10:09 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (4704ms) params={}
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-06-22 01:10:27
**User said:** right now, you are using the same codex process for each prompt instead of spa

**Problem:** Stage 1 emitted an unsupported 'force stage3' label, then Stage 3 took 163 seconds for a direct architecture question.

**Root cause:** The classifier generated a non-enum label and fell back to others:Low. Stage 3 then started at 01:10:24 and did not finish until 01:13:07. The logs do not expose subspan timing inside Stage 3, so the proven bottleneck is the OpenAI stream_message span.

**Suggested fix:** Add a valid 'stage3_direct' or equivalent class for meta/architecture questions, and instrument Stage 3 with model/context/tool subspans plus an SLA timeout or progress response.

**Log evidence:**
```
2026-06-22 01:10:23 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-06-22 01:10:24 INFO [jane.proxy] [audit-178210] stream_message brain=OpenAI history=0 msg_len=132 file_ctx=False
```
```
2026-06-22 01:13:07 INFO [jane.proxy] [audit-178210] Jane stream pipeline task finished
```
```
2026-06-22 01:13:07 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (163214ms)
```

---

## Issue 3 [CRITICAL]

**Turn:** 2026-06-22 01:13:12
**User said:** use the source code as your guide

**Problem:** Multi-turn context and source-code context were not provided for a follow-up instruction.

**Root cause:** The same conversation id was used, but Stage 3 was called with history=0 and file_ctx=False. The prompt length was only the current 33-character follow-up, so Stage 3 had no logged access to the prior question or the requested source-code context.

**Suggested fix:** Load conversation history by session id before Stage 3, and route source-code requests to a workspace-aware code path that attaches repository context or invokes the code agent.

**Log evidence:**
```
2026-06-22 01:13:11 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=33 sid_override=True class_protocol=n/a
```
```
2026-06-22 01:13:12 INFO [jane.proxy] [audit-178210] stream_message brain=OpenAI history=0 msg_len=33 file_ctx=False
```

---

## Issue 4 [CRITICAL]

**Turn:** 2026-06-22 01:13:36
**User said:** please familiarize yourself with the waterlily project

**Problem:** Project familiarization was handled by Stage 3 without logged project context and took 220 seconds.

**Root cause:** Stage 1 sent the request to Stage 3 as others:Low. The Stage 3 call had history=0 and file_ctx=False, then the pipeline did not finish until 219711ms later. Background short-term memory extraction also repeatedly timed out during this window.

**Suggested fix:** Detect project/codebase familiarization requests and route them to a code-aware worker with repository access. Move short-term memory extraction off the latency-sensitive path or cap it to a short asynchronous attempt.

**Log evidence:**
```
2026-06-22 01:13:36 INFO [jane.proxy] [audit-178210] stream_message brain=OpenAI history=0 msg_len=54 file_ctx=False
```
```
2026-06-22 01:13:53 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-06-22 01:15:23 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```
```
2026-06-22 01:17:15 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (219711ms)
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-06-22 01:17:20
**User said:** currently, the waterlily site is web only meant for browsers on laptops and comput

**Problem:** Large code implementation request was classified through an unsupported label, sent to Stage 3 without logged code context, and took 518 seconds.

**Root cause:** The classifier again returned unsupported 'web automation' and fell back to others:Low. Stage 3 then received history=0 and file_ctx=False for a codebase-wide UI task, with no Stage 2/code handler or client tool execution shown. The Stage 3 span lasted 517889ms.

**Suggested fix:** Add a supported code/project intent that routes implementation requests to the Codex/code-agent path with workspace context, progress streaming, and bounded Stage 3 orchestration time.

**Log evidence:**
```
2026-06-22 01:17:18 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-06-22 01:17:20 INFO [jane.proxy] [audit-178210] stream_message brain=OpenAI history=0 msg_len=750 file_ctx=False
```
```
2026-06-22 01:25:57 INFO [jane.proxy] [audit-178210] Jane stream pipeline task finished
```
```
2026-06-22 01:25:57 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (517889ms)
```

---

