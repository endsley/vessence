# Transcript Quality Review — 2026-07-01

Generated: 2026-07-02 01:39:49

## Issue 1 [LOW]

**Turn:** 2026-07-01 01:12:44
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 1 produced an out-of-taxonomy intent label before falling back to others.

**Root cause:** The classifier returned 'force stage3', which is not a valid Stage 1 class. The fallback routed correctly to Stage 3, but the classifier contract is not constrained.

**Suggested fix:** Constrain classifier output to the allowed intent enum with schema/grammar decoding and add a regression test for invalid labels.

**Log evidence:**
```
2026-07-01 01:12:42 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-07-01 01:12:42 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1177ms) params={}
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-07-01 01:13:02
**User said:** use the source code as your guide

**Problem:** A context-dependent follow-up was sent to Stage 3 with no Jane-side conversation history.

**Root cause:** The previous and follow-up Stage 3 calls both show history=0. The follow-up prompt was only 33 characters, so the logs do not show enough context being supplied for the brain to know what source-code question it refers to.

**Suggested fix:** Pass the last N session messages or a compact turn summary into Stage 3 for same-session follow-ups, or log and verify persistent Codex session reuse keyed by sid.

**Log evidence:**
```
2026-07-01 01:12:44 INFO [jane.proxy] [audit-178288] stream_message brain=OpenAI history=0 msg_len=132 file_ctx=False
```
```
2026-07-01 01:13:01 INFO [jane.proxy] [audit-178288] stream_message brain=OpenAI history=0 msg_len=33 file_ctx=False
```

---

## Issue 3 [LOW]

**Turn:** 2026-07-01 01:16:38
**User said:** currently, the waterlily site is web only meant for browsers on laptops and computers

**Problem:** Stage 1 again produced an invalid intent label before fallback.

**Root cause:** The classifier returned 'web automation', which is outside the supported taxonomy. Routing still escalated to Stage 3, but the warning shows taxonomy drift.

**Suggested fix:** Update the classifier prompt/schema so code, web, and project-work requests resolve to the canonical complex/others escalation class only.

**Log evidence:**
```
2026-07-01 01:16:34 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-07-01 01:16:34 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (8605ms) params={}
```

---

## Issue 4 [CRITICAL]

**Turn:** 2026-07-01 01:31:19
**User said:** # Task: Waterlily iterative refactor 1/5

**Problem:** Stage 3 work was cancelled after the client disconnected, so the requested refactor did not complete.

**Root cause:** The Stage 3 stream started, then the proxy logged a client disconnect and cancelled brain execution after 82146ms.

**Suggested fix:** Decouple long-running Stage 3 coding tasks from the client stream: continue the brain task in the background, send keepalives, persist the result, and let the client reconnect to status.

**Log evidence:**
```
2026-07-01 01:31:18 INFO [jane.proxy] [audit-178288] stream_message brain=OpenAI history=0 msg_len=2810 file_ctx=False
```
```
2026-07-01 01:32:41 INFO [jane.proxy] [audit-178288] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-07-01 01:32:41 WARNING [jane.proxy] [audit-178288] Brain execution cancelled (stream) after 82146ms — likely client disconnect or timeout. Stack:
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-07-01 19:23:57
**User said:** (android voice turn; transcript unavailable, text_len=20)

**Problem:** A simple Android voice greeting took about a minute despite using the Stage 2 fast path.

**Root cause:** The logs show Codex standing-brain startup failed on a locked sqlite database, memory context fell back to a slow path, Stage 1 took 11120ms, and the deterministic greeting handler then took 46947ms.

**Suggested fix:** Make greeting and other deterministic Stage 2 handlers independent of memory/context and standing-brain startup. Add short circuit-breaker timeouts around memory daemon access and fix Codex sqlite locking with single-owner startup or separate runtime state directories.

**Log evidence:**
```
2026-07-01 18:57:35 ERROR [jane.web] Standing Brain startup failed: Codex app-server stdout closed. Error: failed to initialize sqlite state runtime under /home/chieh/.codex: failed to initialize state runtime at /home/chieh/.codex: error returned from database: (code: 5) database is locked
```
```
2026-07-01 19:23:42 WARNING [context_builder.v1.context_builder] Memory daemon unavailable (timed out) — falling back to slow path
```
```
2026-07-01 19:24:13 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 greeting:Very High (11120ms) params={}
```
```
2026-07-01 19:25:00 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage2 greeting handler (46947ms)
```

---

## Issue 6 [MEDIUM]

**Turn:** 2026-07-01 19:25:57
**User said:** why was it taking you so long

**Problem:** The latency explanation turn was itself slow.

**Root cause:** Android sent the voice message at 19:25:08, Stage 1 did not finish until 19:25:25, Stage 3 escalation did not start until 19:25:55, and the full response finished at 19:26:11.

**Suggested fix:** Instrument the gap between Stage 1 completion and Stage 3 escalation, then move or bound any context-building work there. For short diagnostic questions, skip slow memory retrieval when the daemon is unavailable.

**Log evidence:**
```
2026-07-01T19:25:08.968Z [voice_flow] voice_flow[send_message] text_len=29 fromVoice=True
```
```
2026-07-01 19:25:25 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (15667ms) params={}
```
```
2026-07-01 19:25:55 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=202 sid_override=True class_protocol=n/a
```
```
2026-07-01 19:26:11 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (15716ms)
```

---

## Issue 7 [MEDIUM]

**Turn:** 2026-07-01 19:26:23
**User said:** (android follow-up STT result; transcript unavailable, text_len=11)

**Problem:** Android captured a nonempty follow-up STT result but did not send it to the server.

**Root cause:** The client logged stt_result text_len=11 after the post-TTS relaunch, but there is no following voice_flow[send_message] event.

**Suggested fix:** Route nonempty post-TTS STT results through the same send_message path as wakeword-initiated speech, or log an explicit suppression reason when intentionally dropping a result.

**Log evidence:**
```
2026-07-01T19:26:20.569Z [voice_flow] voice_flow[relaunch_launched] path=sentence_tts
```
```
2026-07-01T19:26:23.648Z [voice_flow] voice_flow[stt_result] text_len=11
```
```
2026-07-01T19:26:26.090Z [wakeword] Model loaded: hey_jane.onnx
```

---

