# Transcript Quality Review — 2026-04-16

Generated: 2026-04-17 01:38:46

## Issue 1 [MEDIUM]

**Turn:** 2026-04-16 20:50:59
**User said:** can you set a timer for

**Problem:** Incomplete timer request escalated to Stage 3 instead of using a Stage 2 clarification path

**Root cause:** Stage 1 correctly classified timer, and Stage 2 correctly failed to parse a duration, but the timer handler returned None, causing Stage 3 escalation. A deterministic timer handler should ask for the missing duration and set a timer pending_action instead of involving Opus.

**Suggested fix:** Change the timer handler so duration_ms=0 creates a pending timer action awaiting duration, with a canned clarification like 'For how long?', rather than returning None to the dispatcher.

**Log evidence:**
```
2026-04-16 20:50:54 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: stage1 timer:High (58ms)
```
```
2026-04-16 20:50:54 INFO [jane_web.jane_v2.classes.timer.handler] timer handler: SET parse → duration_ms=0 from prompt='can you set a timer for'
```
```
2026-04-16 20:50:54 INFO [jane_web.jane_v2.classes.timer.handler] timer handler: couldn't parse duration — escalating
```
```
2026-04-16 20:50:55 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=timer:High voice=False prompt_len=151 sid_override=True class_protocol=missing:timer
```

---

## Issue 2 [LOW]

**Turn:** 2026-04-16 20:51:17
**User said:** 5 Seconds

**Problem:** Timer handler asked for a label before starting a simple 5-second timer

**Root cause:** Stage 1 correctly classified the duration-only follow-up as timer and Stage 2 parsed duration_ms=5000, but the handler treated missing label as required. This added an unnecessary follow-up before firing the timer.

**Suggested fix:** Make timer labels optional. If duration is present and no explicit label is provided, immediately create the timer with an empty/default label instead of asking.

**Log evidence:**
```
2026-04-16 20:51:17 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: timer:High  (raw=TIMER conf=1.00 margin=1.00 lat=39ms)
```
```
2026-04-16 20:51:17 INFO [jane_web.jane_v2.classes.timer.handler] timer handler: SET parse → duration_ms=5000 from prompt='5 Seconds'
```
```
2026-04-16 20:51:17 INFO [jane_web.jane_v2.classes.timer.handler] timer handler: duration=5000 but no label → ask
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-04-16 20:51:25
**User said:** timer label follow-up

**Problem:** Android diagnostic and announcement requests were rate limited during the timer flow

**Root cause:** The Android client appears to have sent repeated diagnostics/announcement polling bursts around the timer interaction. Server rate limiting rejected multiple /api/device-diagnostics and /api/jane/announcements requests, reducing observability and potentially affecting client-side confirmation/debugging.

**Suggested fix:** Throttle Android diagnostics and announcement polling client-side, and exempt or separately bucket low-cost diagnostics so a burst cannot hide timer/tool execution evidence.

**Log evidence:**
```
2026-04-16 20:51:25 WARNING [jane.web] Rate limited 172.56.198.152 on /api/device-diagnostics (api)
```
```
2026-04-16 20:51:30 WARNING [jane.web] Rate limited 172.56.198.152 on /api/jane/announcements (api)
```
```
2026-04-16 20:51:31 WARNING [jane.web] Rate limited 172.56.198.152 on /api/device-diagnostics (api)
```

---

## Issue 4 [CRITICAL]

**Turn:** 2026-04-16 21:13:53
**User said:** can you tell my wife that she is a cutie

**Problem:** SMS request was swallowed by a stale todo-list pending_action and routed to Stage 3 with todo context

**Root cause:** A prior todo-list pending_action was still awaiting category. The resolver first routed the SMS request to the todo handler, which abandoned the pending action, but the pipeline then escalated directly to Stage 3 as reason=todo list:High with a 5069-character todo prompt instead of reclassifying the actual user request as send_message.

**Suggested fix:** When a pending-action handler abandons because the reply is clearly unrelated, clear the pending action and run Stage 1 on the raw user utterance. Add an interruption detector for high-confidence new intents like send_message, timer, weather, and get_time.

**Log evidence:**
```
2026-04-16 21:13:23 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → todo list (awaiting=category)
```
```
2026-04-16 21:13:40 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → todo list (awaiting=category)
```
```
2026-04-16 21:13:40 INFO [jane_web.jane_v2.pipeline] pipeline: handler abandoned pending → Stage 3
```
```
2026-04-16 21:13:40 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=todo list:High voice=False prompt_len=5069 sid_override=True class_protocol=loaded:todo_list
```
```
2026-04-16 21:13:53 INFO [intent_classifier.v1.gemma_stage2] stage2: ollama timeout (12.0s)
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-04-16 21:13:53
**User said:** can you tell my wife that she is a cutie

**Problem:** Stage 3 failed to execute the SMS tool path for an explicit text-message request

**Root cause:** Because the turn reached Stage 3 with todo-list context rather than send-message context, the proxy reported tools=0 and Opus took 68.9 seconds. The expected SMS draft/direct-send marker was never emitted.

**Suggested fix:** Add Stage 3 guardrails that detect explicit SMS intents even when inherited context is wrong, inject SMS protocol, and require an SMS tool marker or clarification. Also fix the resolver issue so Stage 3 receives the correct class_protocol.

**Log evidence:**
```
2026-04-16 21:13:41 INFO [jane.proxy] [jane_android] stream_message brain=Claude history=0 msg_len=5069 file_ctx=False
```
```
2026-04-16 21:13:53 INFO [jane.proxy] [jane_android] v2 stage2: cls=DELEGATE_OPUS delegate=True conv_end=False tools=0 resp='On it...'
```
```
2026-04-16 21:15:02 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 1 complete in 68867ms (249 chars, 3 raw events)
```

---

## Issue 6 [MEDIUM]

**Turn:** 2026-04-16 21:54:07
**User said:** how's it going

**Problem:** Greeting fast path was slow despite correct classification

**Root cause:** Stage 1 classified greeting correctly, but the Stage 2 greeting handler took 7203ms. A greeting handler should be deterministic/canned and complete in milliseconds, not seconds.

**Suggested fix:** Replace the greeting Stage 2 implementation with a canned response path, or enforce a strict sub-200ms timeout and fallback canned response if any model-backed greeting generation is still used.

**Log evidence:**
```
2026-04-16 21:54:07 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: greeting:High  (raw=GREETING conf=1.00 margin=1.00 lat=255ms)
```
```
2026-04-16 21:54:07 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: stage1 greeting:High (277ms)
```
```
2026-04-16 21:54:14 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: stage2 greeting handler (7203ms)
```

---

## Issue 7 [MEDIUM]

**Turn:** 2026-04-16 21:54:38
**User said:** the last message when I asked you how's it going it took you a while can you explain why

**Problem:** Stage 1 falsely classified a latency-debug question as read_messages

**Root cause:** The phrase 'last message' triggered READ_MESSAGES even though the user was asking for performance analysis, not asking Jane to read SMS. The low-confidence classification still loaded read_messages protocol and escalated to Stage 3.

**Suggested fix:** Tighten read_messages classification to require explicit unread/SMS/text-message reading intent, and add negative examples for 'last message took a while', 'the last message', and debugging/performance questions.

**Log evidence:**
```
2026-04-16 21:54:30 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: read messages:Low  (raw=READ_MESSAGES conf=0.80 margin=0.60 lat=501ms)
```
```
2026-04-16 21:54:32 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=read messages:Low voice=False prompt_len=551 sid_override=True class_protocol=loaded:read_messages
```
```
2026-04-16 21:55:27 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 1 complete in 49591ms (853 chars, 3 raw events)
```

---

## Issue 8 [MEDIUM]

**Turn:** 2026-04-16 21:56:42
**User said:** are you just guessing or what you're telling me you know for sure

**Problem:** Stage 1 latency spiked to 4.15 seconds for a simple meta-question

**Root cause:** The classifier reported 1280ms internal latency, but the pipeline recorded 4150ms for Stage 1. This indicates extra overhead around classification, likely contention or timeout pressure from concurrent memory/broadcast jobs.

**Suggested fix:** Instrument Stage 1 wrapper timing into queue wait, model call, and post-processing. Move memory/theme/broadcast work off the request path or lower its priority so classifier latency is isolated.

**Log evidence:**
```
2026-04-16 21:56:31 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: others:Low  (raw=DELEGATE_OPUS conf=0.40 margin=0.20 lat=1280ms)
```
```
2026-04-16 21:56:31 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: stage1 others:Low (4150ms)
```
```
2026-04-16 21:56:15 WARNING [memory.v1.conversation_manager] Theme classification LLM failed: CLI timed out after 45s
```
```
2026-04-16 21:57:09 WARNING [jane.broadcast] Broadcast summary failed: Command '['claude', '--model', 'haiku', '--print']' timed out after 10 seconds
```

---

## Issue 9 [CRITICAL]

**Turn:** 2026-04-16 22:17:56
**User said:** okay can you tell me other stuff such as my shopping list

**Problem:** Shopping-list request was misclassified as todo list and later escalated unnecessarily

**Root cause:** Stage 1 mapped shopping list to TODO_LIST. The todo handler asked for/kept a category pending, then later abandoned and escalated to Stage 3 with todo_list protocol. This made a simple list query take 68 seconds and produced a follow-up instead of the requested data.

**Suggested fix:** Add a shopping_list intent or explicit shopping-list branch in the todo/list handler. Do not treat 'shopping list' as a generic todo category prompt when the user asks to see it.

**Log evidence:**
```
2026-04-16 22:17:27 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: todo list:High  (raw=TODO_LIST conf=1.00 margin=1.00 lat=209ms)
```
```
2026-04-16 22:17:52 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → todo list (awaiting=category)
```
```
2026-04-16 22:17:52 INFO [jane_web.jane_v2.pipeline] pipeline: handler abandoned pending → Stage 3
```
```
2026-04-16 22:17:53 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=todo list:High voice=False prompt_len=5086 sid_override=True class_protocol=loaded:todo_list
```
```
2026-04-16 22:19:04 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 5 complete in 68390ms (702 chars, 2 raw events)
```

---

## Issue 10 [MEDIUM]

**Turn:** 2026-04-16 22:20:01
**User said:** no I want to find out why we went to stage 3 to answer such a simple question

**Problem:** Follow-up resolver correctly routed to Stage 3, but Stage 3 remained slow and evidence path hit database lock

**Root cause:** The pending Stage 3 topic todo_detail was valid, but the response took 52.9 seconds while memory/theme jobs were timing out and /api/jane/announcements hit 'database is locked'. This suggests background persistence/summary work was contending with interactive turns.

**Suggested fix:** Separate interactive request handling from memory/theme summarization and announcement persistence. Use short SQLite busy timeouts, WAL mode if not enabled, and a single background writer queue.

**Log evidence:**
```
2026-04-16 22:19:58 INFO [jane_web.jane_v2.pending_action_resolver] resolver: stage3_followup (awaiting=todo_detail)
```
```
2026-04-16 22:20:48 WARNING [memory.v1.conversation_manager] Theme summary LLM failed: CLI timed out after 45s
```
```
2026-04-16 22:20:53 ERROR [jane.web] Unhandled error in GET /api/jane/announcements after 5014ms: database is locked
```
```
2026-04-16 22:20:54 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 6 complete in 52947ms (1143 chars, 2 raw events)
```

---

## Issue 11 [LOW]

**Turn:** 2026-04-16 23:01:24
**User said:** I have another question for you

**Problem:** Stage 3 emitted an unnecessary pending_action for a placeholder utterance

**Root cause:** The user had not asked the actual question yet. Stage 1 correctly delegated as others:Low, but Stage 3 responded with an AWAITING marker topic=next_question. This can cause the next unrelated turn to bypass Stage 1 unnecessarily.

**Suggested fix:** For placeholder utterances like 'I have another question', answer with a simple prompt and avoid setting an AWAITING marker unless a concrete task has started.

**Log evidence:**
```
2026-04-16 23:01:19 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: others:Low  (raw=DELEGATE_OPUS conf=0.40 margin=0.20 lat=39ms)
```
```
2026-04-16 23:01:36 INFO [jane_web.jane_v2.pipeline] pipeline: stage3 emitted AWAITING marker → topic=next_question
```
```
2026-04-16 23:02:01 WARNING [memory.v1.conversation_manager] Unparseable theme classification: You're right — I can't categorize a turn that doesn't contain the actual question yet.
```

---

## Issue 12 [MEDIUM]

**Turn:** 2026-04-16 23:18:39
**User said:** right after text to speech there was a lag for speech to text to come back on

**Problem:** Stage 3 follow-up was delayed by five seconds before escalation began

**Root cause:** The resolver identified the pending wait_time_topic at 23:19:11, but Stage 3 escalation did not start until 23:19:18. Rate-limited diagnostics/announcements and memory classification warnings occur in the same window, suggesting request-path contention or blocking pre-escalation work.

**Suggested fix:** Add timing spans between resolver exit and stage3_escalate start. Move diagnostics, announcements, and memory classification off the synchronous path for Stage 3 follow-ups.

**Log evidence:**
```
2026-04-16 23:19:11 INFO [jane_web.jane_v2.pending_action_resolver] resolver: stage3_followup (awaiting=wait_time_topic)
```
```
2026-04-16 23:19:11 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: resolver → stage3_followup (awaiting=wait_time_topic)
```
```
2026-04-16 23:19:11 WARNING [memory.v1.conversation_manager] Unparseable theme classification: I need to verify the actual conversation state before answering. The prompt shows `[CURRENT CONVERSA
```
```
2026-04-16 23:19:18 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=stage3_followup:High voice=False prompt_len=366 sid_override=True class_protocol=missing:stage3_followup
```

---

## Issue 13 [CRITICAL]

**Turn:** 2026-04-16 23:20:47
**User said:** yes please

**Problem:** Approved Stage 3 follow-up took 111 seconds

**Root cause:** The resolver correctly routed yes/please to the pending confirm_stt_prewarming topic, but Opus took 111223ms to complete only 329 characters. This is a severe Stage 3 performance failure for an approval turn.

**Suggested fix:** Handle simple approvals for known pending implementation tasks deterministically where possible, or run the actual implementation outside the voice response path and immediately acknowledge. Add a hard voice-turn timeout with progress updates.

**Log evidence:**
```
2026-04-16 23:20:44 INFO [jane_web.jane_v2.pending_action_resolver] resolver: stage3_followup (awaiting=confirm_stt_prewarming)
```
```
2026-04-16 23:20:45 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=stage3_followup:High voice=False prompt_len=315 sid_override=True class_protocol=missing:stage3_followup
```
```
2026-04-16 23:20:46 INFO [jane.proxy] [jane_android] v2 stage2: cls=DELEGATE_OPUS delegate=True conv_end=False tools=0 resp='Got it, looking into it...'
```
```
2026-04-16 23:22:38 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 3 complete in 111223ms (329 chars, 2 raw events)
```

---

## Issue 14 [CRITICAL]

**Turn:** 2026-04-16 23:23:16
**User said:** okay can you rebuild the APK for me

**Problem:** APK rebuild request was classified as restart_server/others and sent to Stage 3, then took nearly three minutes

**Root cause:** Stage 1 raw label was RESTART_SERVER with low confidence, normalized to others. There is no deterministic build/APK intent, so Stage 3 handled it and took 176892ms.

**Suggested fix:** Add a BUILD_APK or ANDROID_BUILD intent and Stage 2 handler that invokes the approved bump/build script or asks for confirmation according to policy. Add classifier examples for 'rebuild the APK'.

**Log evidence:**
```
2026-04-16 23:23:03 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: others:Low  (raw=RESTART_SERVER conf=0.60 margin=0.20 lat=82ms)
```
```
2026-04-16 23:23:11 WARNING [jane_web.jane_v2.pipeline] ack generation failed () — using fallback
```
```
2026-04-16 23:23:11 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=174 sid_override=True class_protocol=n/a
```
```
2026-04-16 23:26:13 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 4 complete in 176892ms (200 chars, 2 raw events)
```

---

## Issue 15 [MEDIUM]

**Turn:** 2026-04-16 23:31:19
**User said:** weather / air quality question

**Problem:** Weather Stage 2 handler became very slow due to gate-check failures

**Root cause:** Stage 1 correctly classified weather, but Stage 2 weather handler took 15.6s and 19.0s on repeated turns. Dispatcher gate checks failed and 'failed open', adding long delays before the handler completed.

**Suggested fix:** Make dispatcher gate checks bounded and nonblocking, with a short timeout under 200ms. Cache weather eligibility decisions and skip gate checks for high-confidence weather intents.

**Log evidence:**
```
2026-04-16 23:31:19 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: weather:High  (raw=WEATHER conf=1.00 margin=1.00 lat=37ms)
```
```
2026-04-16 23:31:31 WARNING [jane_web.jane_v2.stage2_dispatcher] dispatcher gate check failed () — failing open
```
```
2026-04-16 23:31:35 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: stage2 weather handler (15609ms)
```
```
2026-04-16 23:31:53 WARNING [jane_web.jane_v2.stage2_dispatcher] dispatcher gate check failed () — failing open
```
```
2026-04-16 23:32:00 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: stage2 weather handler (18956ms)
```

---

## Issue 16 [MEDIUM]

**Turn:** 2026-04-16 23:32:25
**User said:** can you do a online search and tell me what is causing the air quality to be bad

**Problem:** Weather handler declined after 9.4 seconds and only then escalated to Stage 3

**Root cause:** The query required online/current air-quality research. Stage 1 classified weather correctly, but Stage 2 spent 9438ms before declining. Escalation to Stage 3 was correct, but it should have happened immediately for online-search wording.

**Suggested fix:** Add early detection for 'online search', 'look up', and causal/current-events weather questions so Stage 2 weather declines immediately or routes directly to Stage 3 with weather protocol.

**Log evidence:**
```
2026-04-16 23:32:14 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: weather:High  (raw=WEATHER conf=1.00 margin=1.00 lat=44ms)
```
```
2026-04-16 23:32:23 INFO [jane_web.jane_v2.stage2_dispatcher] dispatcher: handler for 'weather' declined (returned None)
```
```
2026-04-16 23:32:23 INFO [jane_web.jane_v2.pipeline] jane_v2 pipeline: stage2 weather declined (9438ms)
```
```
2026-04-16 23:32:24 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=weather:High voice=False prompt_len=1531 sid_override=True class_protocol=loaded:weather
```

---

## Issue 17 [MEDIUM]

**Turn:** 2026-04-16 23:55:49
**User said:** I have another question basically I want to give Jane a new ability of like automating web

**Problem:** Stale todo-list pending_action interfered before the web-automation request reached Stage 3

**Root cause:** A previous todo-list pending_action was still active. The resolver repeatedly routed unrelated turns to todo list and fell through. The actual web-automation request eventually reached Stage 3 only after pending handler abandonment and a FORCE_STAGE3/others classification.

**Suggested fix:** Expire pending actions after a short inactivity window or after repeated abandonment. When abandoning, clear the pending action before reclassification and log the raw utterance.

**Log evidence:**
```
2026-04-16 23:55:29 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → todo list (awaiting=category)
```
```
2026-04-16 23:55:29 INFO [jane_web.jane_v2.pipeline] pipeline: handler abandoned pending → falling through to Stage 1
```
```
2026-04-16 23:55:47 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → todo list (awaiting=category)
```
```
2026-04-16 23:55:47 INFO [jane_web.jane_v2.pipeline] pipeline: handler abandoned pending → falling through to Stage 1
```
```
2026-04-16 23:55:48 INFO [jane_web.jane_v2.stage1_classifier] stage1_classifier: others:Low  (raw=FORCE_STAGE3 conf=0.60 margin=0.20 lat=48ms)
```

---

## Issue 18 [LOW]

**Turn:** 2026-04-16 23:56:26
**User said:** the first one

**Problem:** Stage 3 follow-up acknowledgement leaked planning text before final brain answer

**Root cause:** The proxy emitted a Stage 2 delegated response saying 'Got it. Let's proceed with web automation for Jane. Can you...' while the real Stage 3 brain was still running. This creates a premature, possibly incomplete response before Opus finishes.

**Suggested fix:** For delegated Stage 3 follow-ups, keep the immediate ack generic and non-substantive, or suppress it when streaming Opus will answer shortly.

**Log evidence:**
```
2026-04-16 23:56:24 INFO [jane_web.jane_v2.pending_action_resolver] resolver: stage3_followup (awaiting=web_automation_scope)
```
```
2026-04-16 23:56:26 INFO [jane.proxy] [jane_android] v2 stage2: cls=DELEGATE_OPUS delegate=True conv_end=False tools=0 resp="Got it. Let's proceed with web automation for Jane. Can you "
```
```
2026-04-16 23:56:59 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 8 complete in 32238ms (904 chars, 2 raw events)
```

---

## Issue 19 [LOW]

**Turn:** 2026-04-16 23:57:54
**User said:** I think I won both

**Problem:** Memory/theme classifier tried to parse Stage 3 response text as an integer

**Root cause:** The conversation_manager theme classification expected an integer-like output but received a long natural-language response about browser automation and AWAITING markers. This indicates missing structured-output enforcement or parser validation.

**Suggested fix:** Constrain theme classification to JSON or a strict numeric schema, validate before int conversion, and discard/repair nonconforming LLM outputs without warning spam.

**Log evidence:**
```
2026-04-16 23:57:30 WARNING [memory.v1.conversation_manager] Theme classification LLM failed: invalid literal for int() with base 10: 'Browser automation is already partially implemented in `agent_skills/browser_skill.py` and `agent_skills/browser_utils.py` using Playwright. The [[AWAITING:web_autom
```
```
2026-04-16 23:57:53 INFO [jane_web.jane_v2.pending_action_resolver] resolver: stage3_followup (awaiting=web_automation_use_cases)
```
```
2026-04-16 23:58:13 INFO [jane_web.jane_v2.pipeline] pipeline: stage3 emitted AWAITING marker → topic=web_auto_next_step
```

---

## Issue 20 [MEDIUM]

**Turn:** 2026-04-16 multiple
**User said:** Stage 3 escalated turns

**Problem:** Stage 3 session import failed on every escalation

**Root cause:** stage3_escalate repeatedly logs 'auth.v1.sessions import failed: attempted relative import with no known parent package'. This likely breaks or degrades session override/history behavior for escalated turns.

**Suggested fix:** Fix stage3_escalate imports to use package-absolute imports under the jane_web package, and add a startup/import test that exercises Stage 3 escalation outside __main__ execution.

**Log evidence:**
```
2026-04-16 20:50:55 ERROR [jane_web.jane_v2.stage3_escalate] stage3_escalate: auth.v1.sessions import failed: attempted relative import with no known parent package
```
```
2026-04-16 21:54:32 ERROR [jane_web.jane_v2.stage3_escalate] stage3_escalate: auth.v1.sessions import failed: attempted relative import with no known parent package
```
```
2026-04-16 23:32:24 ERROR [jane_web.jane_v2.stage3_escalate] stage3_escalate: auth.v1.sessions import failed: attempted relative import with no known parent package
```
```
2026-04-16 23:57:53 ERROR [jane_web.jane_v2.stage3_escalate] stage3_escalate: auth.v1.sessions import failed: attempted relative import with no known parent package
```

---

