# Transcript Quality Review — 2026-05-10

Generated: 2026-05-11 01:39:50

## Issue 1 [MEDIUM]

**Turn:** 2026-05-10 01:11:32
**User said:** yes those articles and maybe just two days

**Problem:** Follow-up answer was routed through Stage 1 instead of the pending_action_resolver

**Root cause:** This utterance is a context-dependent follow-up, but the logs show it went directly into `stage1 others:Low` and then Stage 3. Because the resolver is supposed to run before Stage 1, the pending action was either not persisted or not checked on this turn. Stage 3 then had to recover context from injected recent history instead of the intended direct handler path.

**Suggested fix:** Gate Stage 1 behind an explicit pending-action lookup keyed by session id, and add resolver hit/miss logs so follow-up routing failures are visible.

**Log evidence:**
```
[2026-05-10 01:11:32] (audit-177838) yes those articles and maybe just two days
```
```
2026-05-10 01:11:30 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1275ms) params={}
```
```
2026-05-10 01:11:31 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=42 sid_override=True class_protocol=n/a
```
```
2026-05-10 01:11:32 INFO [jane.proxy] [audit-177838] Standing brain turn 1 — injected recent history only
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-05-10 01:13:16
**User said:** currently how does your short-term memory work

**Problem:** Straightforward question incurred extreme Stage 3 latency

**Root cause:** The request immediately escalated to Stage 3, the standing brain restarted because it had been spawned with the vault locked, `short_term_extractor` timed out after 45 seconds, and the final Stage 3 turn still ran for 262275ms end-to-end. The logs show a slow-path stack for a simple explanatory question.

**Suggested fix:** Keep the standing brain usable after vault unlock instead of restarting per turn, and move `short_term_extractor` off the synchronous request path behind a hard latency budget.

**Log evidence:**
```
[2026-05-10 01:13:16] (audit-177838) currently how does your short-term memory work
```
```
2026-05-10 01:13:16 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (788ms) params={}
```
```
2026-05-10 01:13:16 INFO [jane.standing_brain] Vault is now unlocked but brain was spawned locked. Restarting brain [claude-opus-4-6]...
```
```
2026-05-10 01:13:20 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```
```
2026-05-10 01:17:40 INFO [jane.standing_brain] Brain [claude-opus-4-6] turn 1 complete in 262275ms (1552 chars, 6 raw events)
```
```
2026-05-10 01:17:40 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (263652ms)
```

---

## Issue 3 [CRITICAL]

**Turn:** 2026-05-10 01:17:43
**User said:** <class_protocol name="greeting"> These are runtime instructions for handling a gr

**Problem:** Stage 1 was vulnerable to prompt-like control text and misclassified the message as `greeting`

**Root cause:** The user message was not a normal greeting; it was raw protocol/instruction text beginning with `<class_protocol name="greeting">`. The classifier still returned `greeting:Very High`, and Stage 3 was invoked with `class_protocol=loaded:greeting`, showing the injected control text influenced routing.

**Suggested fix:** Sanitize classifier input by stripping or heavily down-weighting XML/control blocks such as `<class_protocol ...>`, and add adversarial tests requiring these inputs to fall back to `others` or a dedicated debug/safety class.

**Log evidence:**
```
[2026-05-10 01:17:43] (audit-177838) <class_protocol name="greeting">
```
```
2026-05-10 01:17:42 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 greeting:Very High (855ms) params={}
```
```
2026-05-10 01:17:43 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=greeting:Very High voice=False prompt_len=1142 sid_override=True class_protocol=loaded:greeting
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-05-10 01:17:43
**User said:** <class_protocol name="greeting"> These are runtime instructions for handling a gr

**Problem:** The Stage 2 greeting handler returned an invalid payload shape and could not complete the fast path

**Root cause:** After high-confidence greeting classification, the pipeline explicitly logged `handler 'greeting' returned invalid shape → Stage 3`. That is a deterministic handler contract failure, not an LLM issue.

**Suggested fix:** Validate handler outputs against a typed schema at registration time and add a unit test for the greeting handler's return shape so invalid payloads cannot reach production.

**Log evidence:**
```
2026-05-10 01:17:42 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 greeting:Very High (855ms) params={}
```
```
2026-05-10 01:17:42 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'greeting' returned invalid shape → Stage 3
```
```
2026-05-10 01:17:43 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=greeting:Very High voice=False prompt_len=1142 sid_override=True class_protocol=loaded:greeting
```

---

## Issue 5 [MEDIUM]

**Turn:** 2026-05-10 01:18:41
**User said:** it seems to me that you are no longing making any sounds when speech to text is t

**Problem:** Client-side STT/chime behavior cannot be verified from the available Android diagnostics

**Root cause:** The user reported a client audio regression, but the supplied Android diagnostics contain only wakeword model-load events and no `voice_flow` or `tool_handler` events around this session. The client execution path for STT relaunch and audio cue playback is therefore not observable in the logs provided.

**Suggested fix:** Emit structured Android `voice_flow` events for STT stop/start, beep or chime playback, and post-response mic relaunch, tagged with the conversation/session id.

**Log evidence:**
```
[2026-05-10 01:18:41] (audit-177838) it seems to me that you are no longing making any sounds when speech to text is turned back on
```
```
2026-05-10T07:54:22.229Z [wakeword] Model loaded: hey_jane.onnx
```
```
2026-05-10T08:14:59.780Z [wakeword] Model loaded: hey_jane.onnx
```

---

## Issue 6 [MEDIUM]

**Turn:** 2026-05-10 01:24:35
**User said:** can you look at the short-term memory to see if this whole thing is actually bein

**Problem:** The system could not reliably inspect short-term memory during the very turn asking about it

**Root cause:** While handling this request, `short_term_extractor` failed with a 45-second timeout. The logs prove the subsystem responsible for short-term memory extraction was failing during the inspection request itself, so any answer about observing the current turn's short-term memory would not have been backed by a successful extractor run.

**Suggested fix:** Add a deterministic debug handler that reads live short-term-memory state directly from storage instead of asking Stage 3 to infer it, and surface extractor failures explicitly to the user.

**Log evidence:**
```
[2026-05-10 01:24:35] (audit-177838) can you look at the short-term memory to see if this whole thing is actually being done observe it through our current turn
```
```
2026-05-10 01:24:34 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=123 sid_override=True class_protocol=n/a
```
```
2026-05-10 01:25:17 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI timed out after 45s
```
```
2026-05-10 01:27:07 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (152900ms)
```

---

## Issue 7 [CRITICAL]

**Turn:** 2026-05-10 01:30:56
**User said:** hey Jane, can you take a look at the ~/code/waterlily project for me

**Problem:** Stage 3 request was cancelled before completion because the client disconnected

**Root cause:** The project-review request escalated to Stage 3, but before the model finished, the server logged `Client disconnected` and then `Brain execution cancelled (stream) after 40250ms`. This is a user-facing failure: no completed answer was delivered.

**Suggested fix:** Send an immediate acknowledgement and periodic keepalive output for long-running Stage 3 tasks, or increase the client stream timeout so code-inspection requests are not cancelled before first content.

**Log evidence:**
```
[2026-05-10 01:30:56] (audit-177838) hey Jane, can you take a look at the ~/code/waterlily project for me
```
```
2026-05-10 01:30:56 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=68 sid_override=True class_protocol=n/a
```
```
2026-05-10 01:31:36 INFO [jane.proxy] [audit-177838] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-05-10 01:31:37 WARNING [jane.proxy] [audit-177838] Brain execution cancelled (stream) after 40250ms — likely client disconnect or timeout. Stack:
```
```
2026-05-10 01:31:37 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (40708ms)
```

---

