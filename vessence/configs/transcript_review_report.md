# Transcript Quality Review — 2026-05-23

Generated: 2026-05-24 01:23:42

## Issue 1 [CRITICAL]

**Turn:** 2026-05-23 01:15:43
**User said:** hey Jane, can you take a look at the ~/code/waterlily project for me

**Problem:** Local project inspection was escalated to Stage 3 without file/project context.

**Root cause:** Stage 1 routed the request as others and Stage 3 was invoked with file_ctx=False, so the frontier brain had no attached context for ~/code/waterlily. The request then occupied Stage 3 for 227.7s.

**Suggested fix:** Add local-path/code-project intent detection before escalation: expand ~/ paths, verify the project path, and attach file context or route to the Codex/code-agent backend with that cwd. If the path is inaccessible, fail fast with a clarifying question.

**Log evidence:**
```
2026-05-23 01:15:41 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (4047ms) params={}
```
```
2026-05-23 01:15:42 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=68 sid_override=True class_protocol=n/a
```
```
2026-05-23 01:15:42 INFO [jane.proxy] [audit-177951] stream_message brain=OpenAI history=0 msg_len=68 file_ctx=False
```
```
2026-05-23 01:19:30 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (227698ms)
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-05-23 01:19:43
**User said:** currently is your background large language model using Claude codex or call I mean

**Problem:** Runtime model/status question missed the fast path and went to Stage 3.

**Root cause:** Stage 1 returned others:Low with no params; there is no deterministic self-status/model-status handler, so Stage 2 did nothing and Stage 3 handled a question that should be answerable from live config.

**Suggested fix:** Add a self_status or model_status classifier category and Stage 2 handler that reads the configured Stage 3 brain/model from the live proxy/config and returns it directly.

**Log evidence:**
```
2026-05-23 01:19:42 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1105ms) params={}
```
```
2026-05-23 01:19:42 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=105 sid_override=True class_protocol=n/a
```
```
2026-05-23 01:19:43 INFO [jane.proxy] [audit-177951] stream_message brain=OpenAI history=0 msg_len=105 file_ctx=False
```
```
2026-05-23 01:19:58 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (15643ms)
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-05-23 01:20:01
**User said:** can you tell me if currently you are using cold decks or Claude cold as the base

**Problem:** Follow-up model question was sent to Stage 3 with no conversation history and took about 2 minutes.

**Root cause:** The same session id was used, but jane.proxy logged history=0. The ASR-corrupted terms needed prior context from the previous turn, and the missing model-status fast path forced a 119.5s Stage 3 call.

**Suggested fix:** Persist and load session history when sid_override=True, and handle model/status questions in Stage 2 with ASR aliases such as codex/cold decks.

**Log evidence:**
```
2026-05-23 01:20:00 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1062ms) params={}
```
```
2026-05-23 01:20:01 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=94 sid_override=True class_protocol=n/a
```
```
2026-05-23 01:20:01 INFO [jane.proxy] [audit-177951] stream_message brain=OpenAI history=0 msg_len=94 file_ctx=False
```
```
2026-05-23 01:22:00 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (119496ms)
```

---

## Issue 4 [LOW]

**Turn:** 2026-05-23 01:22:16
**User said:** currently which large language model is being used as Jane Webb

**Problem:** Stage 1 produced an out-of-schema class before falling back to others.

**Root cause:** The classifier returned 'force stage3', which the pipeline did not recognize and converted to others. Routing still reached Stage 3, but the classifier prompt/schema is not constrained to the valid taxonomy.

**Suggested fix:** Constrain classifier output to the allowed enum and add parser tests for unknown labels. If force_stage3 is intentional, add it as an explicit alias.

**Log evidence:**
```
2026-05-23 01:22:15 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-05-23 01:22:15 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1208ms) params={}
```

---

## Issue 5 [MEDIUM]

**Turn:** 2026-05-23 01:22:16
**User said:** currently which large language model is being used as Jane Webb

**Problem:** Simple model-status question took almost 2 minutes because it was handled by Stage 3.

**Root cause:** After the unknown-class fallback, Stage 3 was invoked with history=0 and file_ctx=False and completed after 118.8s; no Stage 2 runtime model handler answered from config.

**Suggested fix:** Use a deterministic model-status handler for this intent and return the active backend/model name from the live configuration instead of escalating to the frontier brain.

**Log evidence:**
```
2026-05-23 01:22:16 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=63 sid_override=True class_protocol=n/a
```
```
2026-05-23 01:22:16 INFO [jane.proxy] [audit-177951] stream_message brain=OpenAI history=0 msg_len=63 file_ctx=False
```
```
2026-05-23 01:24:15 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (118773ms)
```

---

