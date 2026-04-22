# Transcript Quality Review — 2026-04-21

Generated: 2026-04-22 01:35:17

## Issue 1 [LOW]

**Turn:** 2026-04-21 11:13:22
**User said:** have you compiled a new Android version for me so that I can test the webview updates

**Problem:** Build/APK request was not recognized as a first-class intent and fell through as others.

**Root cause:** The classifier produced an unsupported label, `build apk`, which was mapped to `others:Low`. The turn still escalated to Stage 3, but routing depended on fallback instead of an explicit build/delegate intent.

**Suggested fix:** Add `build apk` / `compile android` / `new Android version` aliases to the classifier schema, mapped to a no-handler Stage 3/delegate class.

**Log evidence:**
```
2026-04-21 11:13:22 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'build apk' → others
```
```
2026-04-21 11:13:22 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (770ms)
```
```
2026-04-21 11:13:23 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=225 sid_override=True class_protocol=n/a
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-04-21 15:23:48
**User said:** I don't think the solution you have for the sunrise now is a good one

**Problem:** Stage 3 lost active conversation context after a standing-brain restart.

**Root cause:** A new standing brain was started at 15:20:26, then the 15:23 turn was sent with `history=0`, even though it was a direct continuation of the summarize-now discussion.

**Suggested fix:** Persist recent conversation history outside the standing-brain process and always inject session history after brain restarts; do not let process restarts reset conversational context.

**Log evidence:**
```
2026-04-21 15:20:26 INFO [jane.standing_brain] Standing brain started: provider=claude model=claude-opus-4-6 pid=2927363
```
```
2026-04-21 15:23:47 INFO [jane.proxy] [jane_android] stream_message brain=Claude history=0 msg_len=209 file_ctx=False
```
```
2026-04-21 15:23:54 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (6345ms)
```

---

## Issue 3 [LOW]

**Turn:** 2026-04-21 15:38:11
**User said:** have you compiled the latest bump of Android version

**Problem:** Build/APK request was again classified as an unknown class and routed through fallback.

**Root cause:** The classifier again emitted unsupported class `build apk`, which became `others:Low`; this caused fallback Stage 3 routing instead of an intentional build/delegate route.

**Suggested fix:** Normalize build-related classifier outputs before schema validation, or add `build apk` as a supported delegate-to-Stage-3 class.

**Log evidence:**
```
2026-04-21 15:38:11 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'build apk' → others
```
```
2026-04-21 15:38:11 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1163ms)
```
```
2026-04-21 15:38:12 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=192 sid_override=True class_protocol=n/a
```

---

## Issue 4 [CRITICAL]

**Turn:** 2026-04-21 16:27:35
**User said:** for the clinic to do list I would like to add that I want to add texting capability

**Problem:** Stage 3 appeared to acknowledge a to-do add without actually using the Stage 2 to-do-list source of truth.

**Root cause:** The explicit add-item request was classified as unknown `delegate_opus` then `others:Low`, so it escalated to Stage 3 with no class protocol. The later user complaint shows the item was not actually added.

**Suggested fix:** Route `add item to clinic to-do list` directly to the todo-list handler, or give Stage 3 a real Google Docs-backed todo tool/protocol and require tool execution before confirming completion.

**Log evidence:**
```
2026-04-21 16:27:34 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'delegate_opus' → others
```
```
2026-04-21 16:27:34 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1055ms)
```
```
2026-04-21 16:27:34 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=230 sid_override=True class_protocol=n/a
```
```
2026-04-21 16:28:48 INFO [jane.proxy] [jane_android] stream_message brain=Claude history=4 msg_len=172 file_ctx=False
```

---

## Issue 5 [MEDIUM]

**Turn:** 2026-04-21 16:28:30
**User said:** I thought I asked you to add a new item

**Problem:** Follow-up complaint was misrouted to the todo-list Stage 2 handler instead of treated as a repair/diagnostic turn.

**Root cause:** The classifier matched `todo list:Very High` and Stage 2 handled it directly, but the user was asking why the previous add failed, not making a clean todo-list query.

**Suggested fix:** Add repair-intent detection for phrases like `I thought I asked`, `why didn't you`, and route them to Stage 3 with recent action logs instead of deterministic handlers.

**Log evidence:**
```
2026-04-21 16:28:30 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 todo list:Very High (967ms)
```
```
2026-04-21 16:28:30 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage2 todo list handler (0ms)
```
```
2026-04-21 16:28:30 INFO [jane.proxy] [jane_android] Persistence worker started stage=stage2 user_chars=38 assistant_chars=161
```

---

## Issue 6 [MEDIUM]

**Turn:** 2026-04-21 17:43:30
**User said:** yes

**Problem:** Pending clinic-schedule follow-up was detected, but the confirmation still escalated to Stage 3 instead of being handled by Stage 2.

**Root cause:** The resolver routed the `yes` follow-up to `clinic schedules info`, but Stage 1 then classified the enriched prompt as `delegate opus:High`, causing unnecessary Stage 3 escalation.

**Suggested fix:** When pending_action_resolver resolves a Stage 2 follow-up, bypass Stage 1 entirely and invoke the target handler with the pending context.

**Log evidence:**
```
2026-04-21 17:43:28 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → clinic schedules info (awaiting=names_for_day_confirm)
```
```
2026-04-21 17:43:29 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 delegate opus:High (1024ms)
```
```
2026-04-21 17:43:29 INFO [jane_web.jane_v3.pipeline] jane_v3: class 'delegate opus' has no handler → Stage 3
```

---

## Issue 7 [CRITICAL]

**Turn:** 2026-04-21 17:44:30
**User said:** what do you mean you lost the thread you have the history of the conversation right

**Problem:** Stage 2 clinic handler returned an invalid response shape, forcing Stage 3 and causing confusing conversation flow.

**Root cause:** The pending follow-up was correctly associated with `clinic schedules info`, but the handler produced an invalid shape. The pipeline escalated to Stage 3 with the clinic protocol instead of returning the expected deterministic response.

**Suggested fix:** Fix the clinic-schedules handler return contract for `names_for_day_confirm`/follow-up branches and add schema tests that fail on invalid handler shapes.

**Log evidence:**
```
2026-04-21 17:44:28 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → clinic schedules info (awaiting=names_for_day_confirm)
```
```
2026-04-21 17:44:29 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 clinic schedules info:Very High (873ms)
```
```
2026-04-21 17:44:29 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'clinic schedules info' returned invalid shape → Stage 3
```

---

## Issue 8 [CRITICAL]

**Turn:** 2026-04-21 18:54:07
**User said:** user: what's the clinic schedule look like for Thursday jane: She has 5 active patients

**Problem:** Clinic-schedule follow-up again hit the invalid handler-shape path and escalated to Stage 3.

**Root cause:** The resolver detected `names_for_day_confirm`, Stage 1 classified clinic schedules correctly, but the handler returned an invalid shape. This repeated the same Stage 2 contract bug.

**Suggested fix:** Repair the clinic handler branch that handles affirmative roster requests and validate every handler response against the pipeline schema before release.

**Log evidence:**
```
2026-04-21 18:54:05 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → clinic schedules info (awaiting=names_for_day_confirm)
```
```
2026-04-21 18:54:06 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 clinic schedules info:Very High (845ms)
```
```
2026-04-21 18:54:06 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'clinic schedules info' returned invalid shape → Stage 3
```

---

## Issue 9 [CRITICAL]

**Turn:** 2026-04-21 21:45:05
**User said:** user: what's the clinic schedule for Friday look like jane: She has 5 active patients

**Problem:** Affirmative clinic roster follow-up escalated because the Stage 2 handler returned an invalid shape.

**Root cause:** The pending resolver correctly identified `names_for_day_confirm`, but the Stage 2 clinic handler failed its response contract and the pipeline had to call Stage 3.

**Suggested fix:** Unify the clinic handler response object across normal schedule, roster confirmation, and patient-detail branches; add a regression test for `yes` after `Would you like to know the names?`.

**Log evidence:**
```
2026-04-21 21:45:04 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → clinic schedules info (awaiting=names_for_day_confirm)
```
```
2026-04-21 21:45:05 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 clinic schedules info:Very High (887ms)
```
```
2026-04-21 21:45:05 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'clinic schedules info' returned invalid shape → Stage 3
```

---

## Issue 10 [MEDIUM]

**Turn:** 2026-04-21 21:55:29
**User said:** yes

**Problem:** Android diagnostics and announcement polling were rate limited during an active voice flow.

**Root cause:** The client emitted frequent diagnostics/announcement calls from the same IP while voice relaunch and follow-up STT were active, triggering server rate limits.

**Suggested fix:** Throttle Android diagnostic and announcement polling, batch diagnostics, and exempt authenticated device telemetry from generic web rate limits with a separate quota.

**Log evidence:**
```
2026-04-21 21:55:29 WARNING [jane.web] Rate limited 172.56.197.171 on /api/device-diagnostics (api)
```
```
2026-04-21 21:55:32 WARNING [jane.web] Rate limited 172.56.197.171 on /api/jane/announcements (api)
```
```
2026-04-21T21:55:30.658Z [voice_flow] voice_flow[relaunch_launched] path=sentence_tts
```
```
2026-04-21T21:55:33.344Z [voice_flow] voice_flow[send_message] text_len=3 fromVoice=True
```

---

## Issue 11 [CRITICAL]

**Turn:** 2026-04-21 22:20:14
**User said:** user: what's the clinic schedule for Wednesday look like jane: She has 8 active patients

**Problem:** Patient-detail follow-up from a clinic roster escalated due to invalid Stage 2 handler shape.

**Root cause:** The resolver correctly identified `patient_selection_from_list`, but the clinic schedules handler returned an invalid response shape and Stage 3 handled the turn.

**Suggested fix:** Fix and test the `patient_selection_from_list` branch so patient-number selections return a valid Stage 2 response with the selected patient's details.

**Log evidence:**
```
2026-04-21 22:20:13 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → clinic schedules info (awaiting=patient_selection_from_list)
```
```
2026-04-21 22:20:13 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 clinic schedules info:Very High (847ms)
```
```
2026-04-21 22:20:13 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'clinic schedules info' returned invalid shape → Stage 3
```

---

## Issue 12 [MEDIUM]

**Turn:** 2026-04-21 23:16:28
**User said:** user: okay can you tell me more about patient number two jane: I don't have detail records

**Problem:** Clinic-schedule request was misclassified as `others`, bypassing the clinic Stage 2 handler.

**Root cause:** The turn contained clinic schedule context and patient-number detail intent, but Stage 1 returned `others:Low`, so Stage 3 had to reconstruct context from chat history.

**Suggested fix:** Add classifier examples for transcript-style clinic follow-ups and patient-number detail requests; preserve structured clinic pending context rather than relying on raw conversation text.

**Log evidence:**
```
2026-04-21 23:16:27 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1406ms)
```
```
2026-04-21 23:16:28 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1635 sid_override=True class_protocol=n/a
```

---

## Issue 13 [MEDIUM]

**Turn:** 2026-04-21 23:18:46
**User said:** user: what's this Wednesday schedule look like jane: She has 8 active patients

**Problem:** Clinic schedule summary transcript was misclassified as `others` instead of clinic schedules.

**Root cause:** The classifier did not handle pasted transcript/context-summary prompts that clearly contained a clinic schedule request.

**Suggested fix:** Preprocess transcript-style user messages to extract the latest actual user request, then classify that extracted request.

**Log evidence:**
```
2026-04-21 23:18:45 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (962ms)
```
```
2026-04-21 23:18:46 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=2120 sid_override=True class_protocol=n/a
```

---

## Issue 14 [CRITICAL]

**Turn:** 2026-04-21 23:47:58
**User said:** yes

**Problem:** No-Stage3 safety deflection replaced the expected clinic roster response.

**Root cause:** The resolver identified the pending clinic names confirmation, but the clinic handler returned an invalid shape. Because the class was marked `no_stage3`, the pipeline returned a safe deflection instead of escalating or answering.

**Suggested fix:** Do not mark clinic schedules `no_stage3` until every follow-up handler branch returns a valid response. Keep a controlled Stage 3 fallback for invalid handler output, and fix the handler contract.

**Log evidence:**
```
2026-04-21 23:47:57 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → clinic schedules info (awaiting=names_for_day_confirm)
```
```
2026-04-21 23:47:58 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 clinic schedules info:Very High (823ms)
```
```
2026-04-21 23:47:58 WARNING [jane_web.jane_v3.pipeline] jane_v3: no_stage3 class 'clinic schedules info' — handler returned invalid shape, returning safe deflection
```

---

