# Transcript Quality Review — 2026-04-17

Generated: 2026-04-18 01:37:04

## Issue 1 [CRITICAL]

**Turn:** 2026-04-17 09:41:33
**User said:** do an online search, i'm pretty sure Codex also has a md file which it runs from

**Problem:** Stage 3 took over two minutes to answer a follow-up and appears to have produced no accumulated response text.

**Root cause:** The pending_action_resolver correctly routed the turn as a Stage 3 follow-up, but the standing brain turn ran for 144389ms and logged result_len=802 with accumulated=0, indicating the stream adapter did not accumulate deliverable text even though raw events were read.

**Suggested fix:** Fix standing_brain stream parsing so final result events are always surfaced even when accumulated streaming text is empty; add a timeout/fallback that returns the final result payload instead of an empty response.

**Log evidence:**
```
2026-04-17 09:41:31 INFO [jane_web.jane_v2.pending_action_resolver] resolver: stage3_followup (awaiting=remove_from_runner_too)
```
```
2026-04-17 09:41:32 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=stage3_followup:High voice=False prompt_len=454 sid_override=True class_protocol=missing:stage3_followup
```
```
2026-04-17 09:43:57 INFO [jane.standing_brain] Brain [claude-opus-4-6] result event: result_len=802, accumulated=0, lines_read=30
```
```
2026-04-17 09:43:57 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 15 complete in 144389ms (802 chars, 2 raw events)
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-04-17 12:18:19
**User said:** weather request

**Problem:** Weather fast path was classified correctly but was slow for a Stage 2 handler.

**Root cause:** Stage 1 classified weather with High confidence in 41ms, but Stage 2 weather handler took 9957ms. Android relaunched STT only after the delayed response, so the user experienced a long pause.

**Suggested fix:** Profile the weather handler network/API path and add request timeouts plus cached recent weather for voice fast path; emit an immediate short acknowledgement only if the handler is expected to exceed a voice latency budget.

**Log evidence:**
```
2026-04-17 12:18:19 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: weather:High  (raw=WEATHER conf=1.00 margin=1.00 lat=41ms)
```
```
2026-04-17 12:18:29 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: stage2 weather handler (9957ms)
```
```
2026-04-17T12:18:19.957Z [voice_flow] voice_flow[stt_result] text_len=29
```
```
2026-04-17T12:18:34.895Z [voice_flow] voice_flow[relaunch_launched] path=non_sentence_tts
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-04-17 15:53:49
**User said:** I'm just wondering if I give you permission for Google Docs would you be able to edit it

**Problem:** Stage 3 gave an ungrounded/inaccurate answer about Google Docs capability.

**Root cause:** The turn correctly escaped the stale todo-list pending action and escalated to Stage 3, but the follow-up memory logs show Stage 3 answered without full conversation/tool evidence, then later admitted it could not verify the actual Google Docs state.

**Suggested fix:** Require Stage 3 capability answers to inspect registered tools/integrations before answering; add a Google Docs capability protocol that distinguishes read-only document access, API auth, and edit/write access.

**Log evidence:**
```
2026-04-17 15:53:47 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → todo list (awaiting=category)
```
```
2026-04-17 15:53:47 INFO [jane_web.jane_v2.pipeline] pipeline: handler abandoned pending → falling through to Stage 1
```
```
2026-04-17 15:53:47 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: others:Low  (raw=DELEGATE_OPUS conf=1.00 margin=1.00 lat=64ms)
```
```
2026-04-17 15:55:05 WARNING [memory.v1.conversation_manager] Unparseable theme classification: I cannot access the full conversation history needed to verify whether this Google Docs discussion r
```

---

## Issue 4 [CRITICAL]

**Turn:** 2026-04-17 15:58:41
**User said:** okay please hook that up for me

**Problem:** Stage 3 turn took nearly three minutes for an implementation request.

**Root cause:** Stage 1 delegated correctly, but the standing brain turn took 172350ms and logged accumulated=0 despite result_len=1850, matching the empty/late response failure mode seen elsewhere.

**Suggested fix:** Separate implementation work from voice response: return a short confirmed plan quickly, then run code work asynchronously. Also fix stream accumulation when result events arrive without incremental text.

**Log evidence:**
```
2026-04-17 15:58:39 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: others:Low  (raw=DELEGATE_OPUS conf=0.60 margin=0.20 lat=100ms)
```
```
2026-04-17 15:58:40 INFO [jane.proxy] [jane_android] v2 stage2: cls=DELEGATE_OPUS delegate=True conv_end=False tools=0 resp='Looking into it...'
```
```
2026-04-17 16:01:33 INFO [jane.standing_brain] Brain [claude-opus-4-6] result event: result_len=1850, accumulated=0, lines_read=67
```
```
2026-04-17 16:01:33 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 19 complete in 172350ms (1850 chars, 7 raw events)
```

---

## Issue 5 [MEDIUM]

**Turn:** 2026-04-17 16:02:32
**User said:** so we might go to work so bad about state to

**Problem:** Stage 3 responded to the wrong topic after a likely STT-garbled request.

**Root cause:** Stage 1 correctly escalated an unclear utterance, but Stage 3 replied as if the user wanted to continue Google Docs editing setup. The response was over-anchored to prior context instead of asking for clarification.

**Suggested fix:** For low-confidence/garbled voice text, add a Stage 3 voice guardrail: if the literal message is semantically unclear, ask a clarification question instead of continuing the previous implementation topic.

**Log evidence:**
```
2026-04-17 16:02:27 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: others:Low  (raw=DELEGATE_OPUS conf=0.00 margin=0.00 lat=64ms)
```
```
2026-04-17 16:02:31 INFO [jane.proxy] [jane_android] v2 stage2: cls=DELEGATE_OPUS delegate=True conv_end=False tools=0 resp="Got it. Let's proceed with the Google Docs editing setup."
```
```
2026-04-17T16:02:28.470Z [voice_flow] voice_flow[send_message] text_len=44 fromVoice=True
```

---

## Issue 6 [CRITICAL]

**Turn:** 2026-04-17 16:02:58
**User said:** can we make it so that stage 2 can handle it like editing of to do

**Problem:** Stage 3 took more than three minutes for a Stage 2 design/change request.

**Root cause:** Stage 1 forced Stage 3 appropriately, but the standing brain took 197669ms. Memory/theme summarization was also timing out in the same window, suggesting background LLM work was contending with interactive Stage 3.

**Suggested fix:** Throttle or isolate memory/theme LLM jobs from interactive Stage 3; enforce an interactive response timeout with partial-progress fallback and move long code changes into background jobs.

**Log evidence:**
```
2026-04-17 16:02:57 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: others:Low  (raw=FORCE_STAGE3 conf=0.80 margin=0.60 lat=38ms)
```
```
2026-04-17 16:03:34 WARNING [memory.v1.conversation_manager] Theme classification LLM failed: CLI timed out after 45s
```
```
2026-04-17 16:06:16 INFO [jane.standing_brain] Brain [claude-opus-4-6] result event: result_len=1250, accumulated=0, lines_read=61
```
```
2026-04-17 16:06:16 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 21 complete in 197669ms (1250 chars, 7 raw events)
```

---

## Issue 7 [MEDIUM]

**Turn:** 2026-04-17 16:23:38
**User said:** okay that is not what I asked for

**Problem:** Todo-list follow-up state repeatedly trapped the conversation before eventually falling through.

**Root cause:** The pending_action_resolver kept routing short follow-ups to the todo-list handler using awaiting=category. Some turns were accepted as todo-list category follow-ups, and only later did the handler abandon pending and fall through to Stage 1.

**Suggested fix:** Add an LLM or semantic gate inside pending_action_resolver for todo-list category follow-ups: route to the pending handler only when the reply is a plausible category/item selection; otherwise clear pending and re-run Stage 1 immediately.

**Log evidence:**
```
2026-04-17 16:22:17 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → todo list (awaiting=category)
```
```
2026-04-17 16:23:12 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → todo list (awaiting=category)
```
```
2026-04-17 16:23:24 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → todo list (awaiting=category)
```
```
2026-04-17 16:23:37 INFO [jane_web.jane_v2.pipeline] pipeline: handler abandoned pending → falling through to Stage 1
```

---

## Issue 8 [MEDIUM]

**Turn:** 2026-04-17 16:29:10
**User said:** ok, i am having trouble with stage 2, if i ask about the TODO list

**Problem:** Stage 3 was too slow for an analysis/debugging question.

**Root cause:** Stage 1 correctly delegated to Stage 3, but the standing brain required 135680ms while CPU was elevated, causing a degraded voice/web experience.

**Suggested fix:** For debugging questions, return an immediate evidence-gathering response and continue asynchronously; cap synchronous standing brain execution and reduce background CPU contention.

**Log evidence:**
```
2026-04-17 16:29:01 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: others:Low  (raw=DELEGATE_OPUS conf=0.00 margin=0.00 lat=0ms)
```
```
2026-04-17 16:31:13 INFO [jane.standing_brain] Brain [claude-opus-4-6] idle + CPU elevated (39.9%), monitoring...
```
```
2026-04-17 16:31:26 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 23 complete in 135680ms (727 chars, 7 raw events)
```

---

## Issue 9 [CRITICAL]

**Turn:** 2026-04-17 16:44:44
**User said:** what? that's a horrible idea. In stage 2 we already use the LLM as gate

**Problem:** Stage 3 response was cancelled after client disconnect, leaving the turn unresolved.

**Root cause:** The server started Stage 3 correctly, but the client disconnected after about 3 seconds and brain execution was cancelled instead of continuing to completion for later delivery.

**Suggested fix:** Decouple Stage 3 execution from the HTTP/stream client connection for voice/web requests; persist the job and deliver the result when ready, or send a resumable pending response.

**Log evidence:**
```
2026-04-17 16:44:43 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=347 sid_override=True class_protocol=n/a
```
```
2026-04-17 16:44:44 INFO [jane.proxy] [a5469b79247a] v2 stage2: cls=DELEGATE_OPUS delegate=True conv_end=False tools=0 resp='Got it, considering LLM input for context.'
```
```
2026-04-17 16:44:47 INFO [jane.proxy] [a5469b79247a] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-04-17 16:44:47 WARNING [jane.proxy] [a5469b79247a] Brain execution cancelled (stream) after 3004ms — likely client disconnect or timeout. Stack:
```

---

## Issue 10 [MEDIUM]

**Turn:** 2026-04-17 17:09:15
**User said:** weather request

**Problem:** Weather fast path was correct but slow because the dispatcher gate check delayed or failed.

**Root cause:** Stage 1 classified weather at High confidence, but the dispatcher still attempted a gate check, failed open after about 12 seconds, and the total Stage 2 weather handler latency reached 19100ms.

**Suggested fix:** Skip the dispatcher gate check for High-confidence deterministic classes before invoking any LLM gate; the later 18:34 logs show this optimization working.

**Log evidence:**
```
2026-04-17 17:09:15 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: weather:High  (raw=WEATHER conf=1.00 margin=1.00 lat=323ms)
```
```
2026-04-17 17:09:27 WARNING [jane_web.jane_v2.stage2_dispatcher] dispatcher gate check failed () — failing open
```
```
2026-04-17 17:09:34 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: stage2 weather handler (19100ms)
```

---

## Issue 11 [MEDIUM]

**Turn:** 2026-04-17 17:10:55
**User said:** so you're saying the reason why the weather took longer is because the gate itself

**Problem:** Stage 3 gave a misleading explanation for weather latency.

**Root cause:** The reply attributed the delay to deeper processing, but the logs show the concrete cause was a dispatcher gate check failure before the weather handler completed.

**Suggested fix:** When asked to explain latency, Stage 3 should inspect pipeline logs and cite exact timings for Stage 1, gate check, handler, and client relaunch instead of inferring from context.

**Log evidence:**
```
2026-04-17 17:09:27 WARNING [jane_web.jane_v2.stage2_dispatcher] dispatcher gate check failed () — failing open
```
```
2026-04-17 17:09:34 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: stage2 weather handler (19100ms)
```
```
2026-04-17 17:10:55 INFO [jane.proxy] [jane_android] v2 stage2: cls=DELEGATE_OPUS delegate=True conv_end=False tools=0 resp='Yes, the deeper processing to ensure accuracy took more time'
```

---

## Issue 12 [CRITICAL]

**Turn:** 2026-04-17 17:49:03
**User said:** I would like to change the subject to Weathers

**Problem:** Stage 1 failed to classify an explicit weather subject-change request as weather.

**Root cause:** The todo-list pending handler correctly abandoned the stale pending action, but Stage 1 then classified the explicit weather request as others/DELEGATE_OPUS with conf=0.80, sending it to slow Stage 3 instead of the weather handler.

**Suggested fix:** Add subject-change normalization before classification, e.g. strip phrases like 'change the subject to' and singular/plural normalize 'weathers' to weather; add regression tests for subject-change utterances.

**Log evidence:**
```
2026-04-17 17:48:59 INFO [jane_web.jane_v2.pipeline] pipeline: handler abandoned pending → falling through to Stage 1
```
```
2026-04-17 17:48:59 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: others:Low  (raw=DELEGATE_OPUS conf=0.80 margin=0.60 lat=757ms)
```
```
2026-04-17 17:49:01 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=170 sid_override=True class_protocol=n/a
```
```
2026-04-17 17:54:13 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 30 complete in 310115ms (698 chars, 5 raw events)
```

---

## Issue 13 [CRITICAL]

**Turn:** 2026-04-17 18:35:00
**User said:** unknown voice turn near weather testing

**Problem:** Pipeline returned an SMS inbox summary during a Stage 3 escalation, likely for the wrong intent.

**Root cause:** Stage 1 classified the turn as others/DELEGATE_OPUS, but inside the proxy the intent_classifier dispatched READ_MESSAGES and returned SMS inbox data with tools=0. This bypassed the explicit client-tool protocol for reading messages and appears unrelated to the surrounding weather/stage-2 testing context.

**Suggested fix:** Remove nested intent dispatch inside Stage 3 proxy for already-escalated turns, or require the outer Stage 1 class to match before running deterministic handlers. READ_MESSAGES must emit the Android client fetch marker instead of fabricating inbox summaries server-side.

**Log evidence:**
```
2026-04-17 18:34:49 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: others:Low  (raw=DELEGATE_OPUS conf=0.40 margin=0.20 lat=95ms)
```
```
2026-04-17 18:34:50 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=150 sid_override=True class_protocol=n/a
```
```
2026-04-17 18:34:51 INFO [intent_classifier.v1.gemma_stage2] stage2: dispatching READ_MESSAGES (session=jane_android)
```
```
2026-04-17 18:35:00 INFO [jane.proxy] [jane_android] v2 stage2: cls=READ_MESSAGES delegate=False conv_end=False tools=0 resp='### Summary of SMS Inbox Data\n\n#### Personal/Important Conta'
```

---

## Issue 14 [MEDIUM]

**Turn:** 2026-04-17 18:38:45
**User said:** no no I actually think we should focus on the different issue

**Problem:** Follow-up resolver overrode an explicit change-of-focus message.

**Root cause:** Stage 3 had set awaiting=misclassified_examples, and the resolver routed the next user turn directly to stage3_followup even though the user said they wanted to focus on a different issue.

**Suggested fix:** Teach pending_action_resolver to detect cancellation/change-topic phrases such as 'different issue', 'not that', and 'change the subject'; clear the awaiting marker and route through Stage 1 or Stage 3 fresh context.

**Log evidence:**
```
2026-04-17 18:38:17 INFO [jane_web.jane_v2.pipeline] pipeline: stage3 emitted AWAITING marker → topic=misclassified_examples
```
```
2026-04-17 18:38:43 INFO [jane_web.jane_v2.pending_action_resolver] resolver: stage3_followup (awaiting=misclassified_examples)
```
```
2026-04-17 18:38:44 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: resolver → stage3_followup (awaiting=misclassified_examples)
```

---

## Issue 15 [LOW]

**Turn:** 2026-04-17 18:42:14
**User said:** no I don't think that's the right solution

**Problem:** Follow-up flow converted a rejection into another confirmation-style follow-up and then set yet another pending action.

**Root cause:** The resolver correctly recognized the message as a response to confirm_skip_router_fix, but Stage 3 did not close or revise the proposal cleanly; it produced a long response and emitted awaiting=preferred_approach, prolonging the loop.

**Suggested fix:** For negative confirmation replies, Stage 3 should acknowledge rejection, summarize the discarded proposal, and ask one concrete alternative question only if necessary; avoid chaining generic AWAITING markers.

**Log evidence:**
```
2026-04-17 18:42:12 INFO [jane_web.jane_v2.pending_action_resolver] resolver: stage3_followup (awaiting=confirm_skip_router_fix)
```
```
2026-04-17 18:42:14 INFO [jane.proxy] [jane_android] v2 stage2: cls=DELEGATE_OPUS delegate=True conv_end=False tools=0 resp='Got it, let me review the context again.'
```
```
2026-04-17 18:43:41 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 3 complete in 86518ms (2229 chars, 5 raw events)
```
```
2026-04-17 18:43:41 INFO [jane_web.jane_v2.pipeline] pipeline: stage3 emitted AWAITING marker → topic=preferred_approach
```

---

## Issue 16 [MEDIUM]

**Turn:** 2026-04-17 20:22:30
**User said:** weather request

**Problem:** Weather handler remained slow even after skipping the gate check.

**Root cause:** Stage 1 classified weather High and the dispatcher skipped the gate, but the weather handler itself still took 13694ms, indicating the remaining latency is in weather data retrieval or handler processing.

**Suggested fix:** Instrument weather handler substeps: geocoding, API fetch, parsing, formatting. Cache location and recent forecast data, and set hard HTTP timeouts.

**Log evidence:**
```
2026-04-17 20:22:30 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: weather:High  (raw=WEATHER conf=1.00 margin=1.00 lat=40ms)
```
```
2026-04-17 20:22:30 INFO [jane_web.jane_v2.stage2_dispatcher] dispatcher: skipping gate check — stage1 conf=High for 'weather'
```
```
2026-04-17 20:22:44 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: stage2 weather handler (13694ms)
```

---

## Issue 17 [MEDIUM]

**Turn:** 2026-04-17 20:27:21
**User said:** do you know the weather next week

**Problem:** Weather Stage 2 declined a valid forecast request and escalated to Stage 3.

**Root cause:** Stage 1 correctly classified weather with High confidence and skipped the gate, but the weather handler returned None for a next-week forecast. Stage 3 then handled it with the weather class protocol, adding 20 seconds of latency.

**Suggested fix:** Extend the weather handler to support forecast horizon phrases like 'next week' when the available API supports daily forecasts; otherwise return a deterministic limitation message instead of declining to Stage 3.

**Log evidence:**
```
2026-04-17 20:27:19 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: weather:High  (raw=WEATHER conf=1.00 margin=1.00 lat=47ms)
```
```
2026-04-17 20:27:20 INFO [jane_web.jane_v2.stage2_dispatcher] dispatcher: handler for 'weather' declined (returned None)
```
```
2026-04-17 20:27:21 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=weather:High voice=False prompt_len=1524 sid_override=True class_protocol=loaded:weather
```
```
2026-04-17 20:27:42 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 4 complete in 20096ms (432 chars, 2 raw events)
```

---

