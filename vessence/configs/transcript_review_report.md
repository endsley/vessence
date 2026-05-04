# Transcript Quality Review — 2026-05-03

Generated: 2026-05-04 01:09:31

## Issue 1 [CRITICAL]

**Turn:** 2026-05-03 01:06:07
**User said:** can you do a search for the Uber website for mCP to work with potentially my AI

**Problem:** Repeated Stage 3 outage caused silence on the entire 01:06:07-01:06:55 open-ended conversation.

**Root cause:** Every one of these turns escalated to Stage 3, and every Stage 3 call failed in `jane.proxy` before producing any assistant payload. The logs consistently show `Brain execution failed (stream)` followed by `Stream finished without final response payload`, so the user got no answer at all.

**Suggested fix:** Add a retry and non-stream fallback around Stage 3 calls, and always emit a user-visible failure response when the brain stream dies instead of ending the turn silently.

**Log evidence:**
```
2026-05-03 01:06:07 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=85 sid_override=True class_protocol=n/a
```
```
2026-05-03 01:06:07 ERROR [jane.proxy] [audit-177778] Brain execution failed (stream)
```
```
2026-05-03 01:06:07 WARNING [jane.proxy] [audit-177778] Stream finished without final response payload
```
```
2026-05-03 01:06:27 ERROR [jane.proxy] [audit-177778] Brain execution failed (stream)
```
```
2026-05-03 01:06:30 ERROR [jane.proxy] [audit-177778] Brain execution failed (stream)
```
```
2026-05-03 01:06:33 ERROR [jane.proxy] [audit-177778] Brain execution failed (stream)
```
```
2026-05-03 01:06:35 ERROR [jane.proxy] [audit-177778] Brain execution failed (stream)
```
```
2026-05-03 01:06:38 ERROR [jane.proxy] [audit-177778] Brain execution failed (stream)
```
```
2026-05-03 01:06:41 ERROR [jane.proxy] [audit-177778] Brain execution failed (stream)
```
```
2026-05-03 01:06:43 ERROR [jane.proxy] [audit-177778] Brain execution failed (stream)
```
```
2026-05-03 01:06:46 ERROR [jane.proxy] [audit-177778] Brain execution failed (stream)
```
```
2026-05-03 01:06:50 ERROR [jane.proxy] [audit-177778] Brain execution failed (stream)
```
```
2026-05-03 01:06:52 ERROR [jane.proxy] [audit-177778] Brain execution failed (stream)
```
```
2026-05-03 01:06:55 ERROR [jane.proxy] [audit-177778] Brain execution failed (stream)
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-05-03 01:06:27
**User said:** what I want to know is if we can use Jane to order Uber using this mCP

**Problem:** Follow-up turns lost conversation context; each Stage 3 escalation was sent with `history=0`.

**Root cause:** The user was clearly continuing the same topic across multiple turns, but every `stream_message` call for session `audit-177778` logged `history=0`. That means Stage 3 was not given prior turns, so natural follow-up flow could not work even if the brain had stayed up.

**Suggested fix:** When escalating within the same session, attach prior conversation turns to Stage 3 requests instead of always sending `history=0`; add a regression test for multi-turn same-topic follow-ups.

**Log evidence:**
```
2026-05-03 01:06:27 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=70 sid_override=True class_protocol=n/a
```
```
2026-05-03 01:06:27 INFO [jane.proxy] [audit-177778] stream_message brain=Claude history=0 msg_len=70 file_ctx=False
```
```
2026-05-03 01:06:30 INFO [jane.proxy] [audit-177778] stream_message brain=Claude history=0 msg_len=56 file_ctx=False
```
```
2026-05-03 01:06:38 INFO [jane.proxy] [audit-177778] stream_message brain=Claude history=0 msg_len=56 file_ctx=False
```
```
2026-05-03 01:06:52 INFO [jane.proxy] [audit-177778] stream_message brain=Claude history=0 msg_len=123 file_ctx=False
```

---

## Issue 3 [CRITICAL]

**Turn:** 2026-05-03 01:06:46
**User said:** <class_protocol name="greeting"> These are runtime instructions for handling a 

**Problem:** Stage 1 was prompt-injected and misclassified non-user control text as `greeting:Very High`.

**Root cause:** The input was protocol-like text, not an actual greeting. Stage 1 still labeled it `greeting:Very High`, and the escalation log shows `class_protocol=loaded:greeting`, which means user-supplied control-looking content influenced routing behavior.

**Suggested fix:** Sanitize or neutralize `class_protocol`/XML-like control markup before classification, and never allow raw user text to trigger protocol loading or class-contract behavior.

**Log evidence:**
```
2026-05-03 01:06:45 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 greeting:Very High (820ms) params={}
```
```
2026-05-03 01:06:46 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=greeting:Very High voice=False prompt_len=1142 sid_override=True class_protocol=loaded:greeting
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-05-03 01:06:46
**User said:** <class_protocol name="greeting"> These are runtime instructions for handling a 

**Problem:** The greeting Stage 2 handler returned an invalid payload shape instead of a valid structured response or clean escalation.

**Root cause:** After the bad Stage 1 routing, the pipeline invoked the greeting handler, but `jane_v3` logged `handler 'greeting' returned invalid shape → Stage 3`. That is a Stage 2 contract failure independent of the later Stage 3 outage.

**Suggested fix:** Enforce schema validation on every handler return value and add tests that malformed or adversarial inputs still produce a valid handler result object.

**Log evidence:**
```
2026-05-03 01:06:45 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 greeting:Very High (820ms) params={}
```
```
2026-05-03 01:06:46 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'greeting' returned invalid shape → Stage 3
```
```
2026-05-03 01:06:46 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=greeting:Very High voice=False prompt_len=1142 sid_override=True class_protocol=loaded:greeting
```

---

