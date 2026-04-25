# Transcript Quality Review — 2026-04-24

Generated: 2026-04-25 01:38:18

## Issue 1 [CRITICAL]

**Turn:** 2026-04-24 09:16:05
**User said:** just that I am testing my text messaging and I love her

**Problem:** Send-message turn was routed to Stage 3 and answered as message reading instead of drafting/sending an SMS.

**Root cause:** The v4 classifier produced the unknown label `send_message`; the pipeline downgraded it to `others`, so the Stage 2 SMS handler never ran. Stage 3 then answered from the wrong conversational context.

**Suggested fix:** Normalize classifier aliases before validation (`send_message` -> `send message`) and add a regression test for SMS utterances that include body text.

**Log evidence:**
```
[2026-04-24 09:16:05] (jane_android) user: just that I am testing my text messaging and I love her
```
```
2026-04-24 09:16:04 WARNING [intent_classifier.v4.classifier] v4: qwen returned unknown class 'send_message' → others
```
```
2026-04-24 09:16:04 INFO [jane_web.jane_v4.pipeline] jane_v4 pipeline: stage1 others:Low (1900ms) params={}
```
```
2026-04-24 09:16:05 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1568 sid_override=True class_protocol=n/a
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-04-24 09:23:20
**User said:** can you tell me what's on my to-do list

**Problem:** Fresh to-do-list request inherited stale category state, causing the Stage 2 todo handler to fail and escalate unnecessarily.

**Root cause:** A pending todo follow-up was still active (`awaiting=category`), and the next top-level request reached Stage 1 with `category='urgent'`. The todo handler then returned an invalid shape and fell back to Stage 3.

**Suggested fix:** Clear todo pending state when a new top-level todo request is detected, and ignore carried category values unless the utterance is only a category reply.

**Log evidence:**
```
[2026-04-24 09:23:20] (jane_android) user: can you tell me what's on my to-do list
```
```
2026-04-24 09:23:15 INFO [jane_web.jane_v2.pending_action_resolver] resolver: followup → todo list (awaiting=category)
```
```
2026-04-24 09:23:17 INFO [jane_web.jane_v4.pipeline] jane_v4 pipeline: stage1 todo list:Very High (1478ms) params={'action': 'read', 'category': 'urgent', 'item': None}
```
```
2026-04-24 09:23:17 INFO [jane_web.jane_v4.pipeline] jane_v4: handler 'todo list' returned invalid shape → Stage 3
```

---

## Issue 3 [CRITICAL]

**Turn:** 2026-04-24 09:24:46
**User said:** can you tell me what's on my to-do list

**Problem:** Clear todo-list request was misclassified as `others`, forcing a 113-second Stage 3 path.

**Root cause:** Stage 1 returned `others:Low` instead of `todo list`, so the deterministic todo handler was skipped and Opus handled the turn with very high latency.

**Suggested fix:** Add lexical fallback rules for `todo list`/`to-do list` before `others`, and retrain the classifier with more direct todo-list examples.

**Log evidence:**
```
[2026-04-24 09:24:46] (jane_android) user: can you tell me what's on my to-do list
```
```
2026-04-24 09:24:45 INFO [jane_web.jane_v4.pipeline] jane_v4 pipeline: stage1 others:Low (1353ms) params={}
```
```
2026-04-24 09:24:46 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1526 sid_override=True class_protocol=n/a
```
```
2026-04-24 09:26:39 INFO [jane_web.jane_v4.pipeline] jane_v4 pipeline: stage3 end-to-end (113539ms)
```

---

## Issue 4 [CRITICAL]

**Turn:** 2026-04-24 09:27:45
**User said:** the Urgent stuff

**Problem:** A simple category follow-up was not resolved by pending_action and instead went through slow Stage 3.

**Root cause:** After Jane asked which todo category to read, the next reply should have bypassed classification. Instead Stage 1 labeled it `others:Low`, so follow-up routing failed and the user waited 104 seconds.

**Suggested fix:** When `awaiting=category`, route category-only replies directly to the todo handler and skip Stage 1 classification entirely.

**Log evidence:**
```
[2026-04-24 09:27:45] (jane_android) user: the Urgent stuff
```
```
2026-04-24 09:27:44 INFO [jane_web.jane_v4.pipeline] jane_v4 pipeline: stage1 others:Low (1292ms) params={}
```
```
2026-04-24 09:27:44 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1903 sid_override=True class_protocol=n/a
```
```
2026-04-24 09:29:29 INFO [jane_web.jane_v4.pipeline] jane_v4 pipeline: stage3 end-to-end (104590ms)
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-04-24 09:31:28
**User said:** are we still doing

**Problem:** Jane answered an unrelated question with stale clinic todo items.

**Root cause:** The turn was classified as `others:Low` and escalated with recent-history context right after a clinic todo read, so Stage 3 reused stale clinic context instead of answering the current utterance. Pending follow-up state was not cleared aggressively enough.

**Suggested fix:** Expire/clear todo follow-up state after a completed category read, and strip stale follow-up context from Stage 3 escalation when the new utterance does not match an expected category reply.

**Log evidence:**
```
[2026-04-24 09:31:28] (jane_android) user: are we still doing
```
```
[2026-04-24 09:31:28] (jane_android) jane: <spoken>3 items for the clinic. Curtain rods at kathia’s clinic; The wooden block for the door at the clinic; and finally, Put mirrors up.</spoken>
```
```
2026-04-24 09:31:06 INFO [jane_web.jane_v4.pipeline] jane_v4 pipeline: stage1 todo list:Very High (1315ms) params={'action': 'read', 'category': 'clinic', 'item': None}
```
```
2026-04-24 09:31:26 INFO [jane_web.jane_v4.pipeline] jane_v4 pipeline: stage1 others:Low (1228ms) params={}
```

---

## Issue 6 [CRITICAL]

**Turn:** 2026-04-24 22:58:32
**User said:** math is hard

**Problem:** Fallback to Stage 3 crashed with a server error, so the user got no answer.

**Root cause:** The `others` path used the synchronous Claude call, which invoked `ClaudePersistentManager.get()` without the required `session_id` argument.

**Suggested fix:** Fix the sync Stage 3 call signature to always pass `session_id`, and add an integration test for `others` turns on `/api/jane/chat`.

**Log evidence:**
```
[2026-04-24 22:58:32] (e226290043e5) math is hard
```
```
2026-04-24 22:58:29 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (662ms) params={}
```
```
2026-04-24 22:58:31 INFO [jane.proxy] [e226290043e5] send_message (sync) brain=Claude history=0 msg_len=12 file_ctx=False
```
```
2026-04-24 22:58:32 ERROR [jane.web] Unhandled error in POST /api/jane/chat after 5063ms: ClaudePersistentManager.get() missing 1 required positional argument: 'session_id'
```

---

## Issue 7 [CRITICAL]

**Turn:** 2026-04-24 22:58:36
**User said:** 234 times 567

**Problem:** Basic arithmetic request was misclassified and then crashed in fallback instead of using the math handler.

**Root cause:** Stage 1 labeled the utterance `others:Low` rather than `do math`, and the fallback sync Claude path then failed because `session_id` was not passed to `ClaudePersistentManager.get()`.

**Suggested fix:** Add regression tests for multiplication phrasing like `X times Y`, and fix the sync fallback session handling.

**Log evidence:**
```
[2026-04-24 22:58:36] (3cda7277e332) 234 times 567
```
```
2026-04-24 22:58:34 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (725ms) params={}
```
```
2026-04-24 22:58:35 INFO [jane.proxy] [3cda7277e332] send_message (sync) brain=Claude history=0 msg_len=13 file_ctx=False
```
```
2026-04-24 22:58:36 ERROR [jane.web] Unhandled error in POST /api/jane/chat after 2599ms: ClaudePersistentManager.get() missing 1 required positional argument: 'session_id'
```

---

## Issue 8 [CRITICAL]

**Turn:** 2026-04-24 22:59:30
**User said:** 234 times 567

**Problem:** Repeated arithmetic retry failed the same way: misclassified, then crashed in Stage 3 fallback.

**Root cause:** The classifier again returned `others:Low` for a math utterance, and the same broken sync Claude path raised `missing 1 required positional argument: 'session_id'`.

**Suggested fix:** Fix both the math-intent classification gap and the sync fallback bug; add a retry-path regression test so repeated failures are caught.

**Log evidence:**
```
[2026-04-24 22:59:30] (c02eaa7b97e2) 234 times 567
```
```
2026-04-24 22:59:29 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (719ms) params={}
```
```
2026-04-24 22:59:30 INFO [jane.proxy] [c02eaa7b97e2] send_message (sync) brain=Claude history=0 msg_len=13 file_ctx=False
```
```
2026-04-24 22:59:30 ERROR [jane.web] Unhandled error in POST /api/jane/chat after 1968ms: ClaudePersistentManager.get() missing 1 required positional argument: 'session_id'
```

---

## Issue 9 [CRITICAL]

**Turn:** 2026-04-24 23:07:51
**User said:** what is 789 divided by 3

**Problem:** Division query was misclassified and then crashed before any answer was returned.

**Root cause:** Stage 1 again fell through to `others:Low` instead of `do math`, and the fallback sync Claude request used the broken `ClaudePersistentManager.get()` call without `session_id`.

**Suggested fix:** Broaden Stage 1 math coverage for division phrasing and add end-to-end tests that verify `others` fallback does not crash.

**Log evidence:**
```
[2026-04-24 23:07:51] (791516a9eb4d) what is 789 divided by 3
```
```
2026-04-24 23:07:50 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (713ms) params={}
```
```
2026-04-24 23:07:51 INFO [jane.proxy] [791516a9eb4d] send_message (sync) brain=Claude history=0 msg_len=24 file_ctx=False
```
```
2026-04-24 23:07:51 ERROR [jane.web] Unhandled error in POST /api/jane/chat after 2175ms: ClaudePersistentManager.get() missing 1 required positional argument: 'session_id'
```

---

## Issue 10 [CRITICAL]

**Turn:** 2026-04-24 23:07:54
**User said:** math is hard

**Problem:** Another `others` turn hit the same Stage 3 crash and returned nothing to the user.

**Root cause:** The synchronous Claude fallback path was still broken and called `ClaudePersistentManager.get()` without a `session_id`.

**Suggested fix:** Repair the sync fallback once and add a smoke test for ordinary `others` chat messages.

**Log evidence:**
```
[2026-04-24 23:07:54] (5ca207b5f5c5) math is hard
```
```
2026-04-24 23:07:53 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1179ms) params={}
```
```
2026-04-24 23:07:54 INFO [jane.proxy] [5ca207b5f5c5] send_message (sync) brain=Claude history=0 msg_len=12 file_ctx=False
```
```
2026-04-24 23:07:54 ERROR [jane.web] Unhandled error in POST /api/jane/chat after 2413ms: ClaudePersistentManager.get() missing 1 required positional argument: 'session_id'
```

---

## Issue 11 [CRITICAL]

**Turn:** 2026-04-24 23:10:19
**User said:** calculate 88 minus 19

**Problem:** Subtraction request was not handled by the math fast path and then crashed in fallback.

**Root cause:** Stage 1 returned `others:Low` for a straightforward math utterance, and the fallback sync Claude call again failed because `session_id` was omitted.

**Suggested fix:** Add subtraction phrasing to the math classifier tests and fix the sync Claude fallback API call.

**Log evidence:**
```
[2026-04-24 23:10:19] (68a97ad3fc28) calculate 88 minus 19
```
```
2026-04-24 23:10:18 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (656ms) params={}
```
```
2026-04-24 23:10:19 INFO [jane.proxy] [68a97ad3fc28] send_message (sync) brain=Claude history=0 msg_len=21 file_ctx=False
```
```
2026-04-24 23:10:19 ERROR [jane.web] Unhandled error in POST /api/jane/chat after 1732ms: ClaudePersistentManager.get() missing 1 required positional argument: 'session_id'
```

---

