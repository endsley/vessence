# Transcript Quality Review — 2026-05-12

Generated: 2026-05-13 01:11:17

## Issue 1 [MEDIUM]

**Turn:** 2026-05-12 01:11:15
**User said:** yes those articles and maybe just two days

**Problem:** Follow-up answer was not routed through the pending_action_resolver and got reclassified from scratch

**Root cause:** There is no resolver hit before Stage 1 for this turn. In the v3 pipeline, idle FIFO flushing runs before the resolver, so the pending follow-up state was already unavailable when this reply arrived and the utterance fell through to `others:Low` and Stage 3.

**Suggested fix:** In `jane_web/jane_v3/pipeline.py`, resolve active pending actions before `maybe_idle_flush()`, or exempt unresolved `pending_action` state from the 30s idle flush. Add an explicit log when an idle flush discards a pending follow-up.

**Log evidence:**
```
[2026-05-12 01:11:15] (audit-177856) yes those articles and maybe just two days
```
```
2026-05-12 01:11:12 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (2380ms) params={}
```
```
2026-05-12 01:11:13 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=42 sid_override=True class_protocol=n/a
```

---

## Issue 2 [CRITICAL]

**Turn:** 2026-05-12 01:15:39
**User said:** <class_protocol name="greeting"> These are runtime instructions for handling 

**Problem:** Raw `<class_protocol>` text was misclassified as a real greeting, and the greeting handler's WRONG_CLASS path degraded into an invalid-shape Stage 3 escalation

**Root cause:** The v3 classifier accepted the injected `<class_protocol name="greeting">` payload as user text and returned `greeting:Very High`. The greeting handler then returned `{"wrong_class": true}` without a `text` field; v3 validates handler shape before checking `wrong_class`, so it logged `handler 'greeting' returned invalid shape` and escalated with `reason=greeting:Very High`, which loaded the greeting class protocol into Stage 3.

**Suggested fix:** Sanitize `<class_protocol>...</class_protocol>` and other Stage 3 injection blocks before v3 classification, reusing the v2 stripping logic. In `jane_web/jane_v3/pipeline.py`, check `result.get("wrong_class")` before the `'text'` shape gate, or change `jane_web/jane_v2/classes/greeting/handler.py` to return `None` on WRONG_CLASS.

**Log evidence:**
```
2026-05-12 01:15:37 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 greeting:Very High (1249ms) params={}
```
```
2026-05-12 01:15:38 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'greeting' returned invalid shape → Stage 3
```
```
2026-05-12 01:15:38 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=greeting:Very High voice=False prompt_len=1142 sid_override=True class_protocol=loaded:greeting
```

---

## Issue 3 [CRITICAL]

**Turn:** 2026-05-12 01:16:44
**User said:** it seems to me that you are no longing making any sounds when speech to tex

**Problem:** A voice/STT bug report took 5.6 minutes to answer, and the client-side behavior could not be verified from the available Android diagnostics

**Root cause:** The complaint was routed to Stage 3 and spent 336302ms end-to-end, with the standing brain restarted again at turn start. On the client side, the only Android diagnostic in the entire dataset is wakeword model load, so there are no `voice_flow` or `tool_handler` events to confirm STT relaunch, beep playback, or post-TTS behavior.

**Suggested fix:** Add a hard latency budget and smaller-model fallback for meta/diagnostic turns in Stage 3, stop restarting the standing brain on every vault-unlock mismatch, and emit Android `voice_flow` telemetry for TTS end, STT relaunch, beep playback, and relaunch-skipped reasons with the session id.

**Log evidence:**
```
2026-05-12 01:16:43 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1151ms) params={}
```
```
2026-05-12 01:16:44 INFO [jane.standing_brain] Vault is now unlocked but brain was spawned locked. Restarting brain [claude-opus-4-6]...
```
```
2026-05-12 01:22:20 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (336302ms)
```
```
2026-05-12T06:20:04.832Z [wakeword] Model loaded: hey_jane.onnx
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-05-12 01:22:24
**User said:** can you look at the short-term memory to see if this whole thing is actual

**Problem:** The user asked to inspect short-term memory while the short-term extractor was repeatedly failing

**Root cause:** By this turn, the short-term memory writer had already timed out twice and timed out again during the same conversation with `CLI timed out after 45s`, so fresh short-term notes were not being reliably produced for the very subsystem the user was asking about.

**Suggested fix:** Make `memory.v1.short_term_extractor` fail fast to a heuristic fallback instead of waiting 45s, queue extraction fully out-of-band, and surface an explicit `short_term_memory_write_failed` flag to Stage 3 so memory-inspection answers can report degraded state honestly.

**Log evidence:**
```
2026-05-12 01:13:12 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```
```
2026-05-12 01:16:22 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```
```
2026-05-12 01:23:08 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-05-12 01:27:55
**User said:** __debug_inspect_update_short_term_memory

**Problem:** The debug-inspection turn never completed because Stage 3 was still running when the client disconnected

**Root cause:** This turn again went to `others:Low` and Stage 3, then exceeded 195 seconds before the client disconnected. The server cancelled the stream and logged pipeline completion only after cancellation, not after delivering a usable reply.

**Suggested fix:** Route `__debug_*` commands to a deterministic local debug handler instead of Opus, and add a client-visible Stage 3 timeout/fallback path that returns a partial or deferred result before the mobile client drops the connection.

**Log evidence:**
```
2026-05-12 01:27:54 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (824ms) params={}
```
```
2026-05-12 01:31:10 INFO [jane.proxy] [audit-177856] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-05-12 01:31:10 WARNING [jane.proxy] [audit-177856] Brain execution cancelled (stream) after 195062ms — likely client disconnect or timeout. Stack:
```

---

