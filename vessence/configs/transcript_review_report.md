# Transcript Quality Review — 2026-05-09

Generated: 2026-05-10 01:34:59

## Issue 1 [CRITICAL]

**Turn:** 2026-05-09 01:07:08
**User said:** yes those articles and maybe just two days

**Problem:** Pending follow-up was not resolved; a contextual reply fragment went through normal classification

**Root cause:** The pre-classifier pending_action_resolver did not intercept a reply that plainly depends on the previous turn. Stage 1 still ran and downgraded the fragment to `others`, which means no pending action was active or the bypass path failed.

**Suggested fix:** Persist pending_action whenever Stage 2 or Stage 3 asks a follow-up question, run the resolver before classification on every turn, and add tests for short contextual answers like `yes ... two days`.

**Log evidence:**
```
2026-05-09 01:07:07 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1105ms) params={}
```
```
2026-05-09 01:07:08 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=42 sid_override=True class_protocol=n/a
```

---

## Issue 2 [CRITICAL]

**Turn:** 2026-05-09 01:07:20
**User said:** <class_protocol name="greeting"> These are runtime instructions for handling a

**Problem:** User-supplied protocol text was treated as a real `greeting` intent, and the greeting fast-path then failed schema validation

**Root cause:** Stage 1 classified the pasted `<class_protocol ...>` block as `greeting` with Very High confidence instead of treating it as arbitrary user text. After that misroute, the greeting handler returned an invalid shape, forcing Stage 3 to run with the greeting class protocol loaded.

**Suggested fix:** Sanitize or neutralize control-looking markup before classification, classify from semantic intent rather than literal label mentions, and add contract tests that fail any handler response not matching the expected schema.

**Log evidence:**
```
2026-05-09 01:07:18 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 greeting:Very High (786ms) params={}
```
```
2026-05-09 01:07:19 INFO [jane_web.jane_v3.pipeline] jane_v3: handler 'greeting' returned invalid shape → Stage 3
```
```
2026-05-09 01:07:19 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=greeting:Very High voice=False prompt_len=1142 sid_override=True class_protocol=loaded:greeting
```

---

## Issue 3 [MEDIUM]

**Turn:** 2026-05-09 01:07:31
**User said:** can you look at the short-term memory to see if this whole thing is actually bei

**Problem:** Short-term-memory introspection was degraded because the extractor was failing on every turn

**Root cause:** The short-term memory extractor repeatedly failed with a quota error, so the system could not reliably update or inspect short-term memory during the same conversation in which the user was asking about it.

**Suggested fix:** Take the remote LLM extractor out of the hot path or add a local fallback, add a circuit breaker after repeated failures, and expose a degraded-memory status to Stage 3 so it does not imply live memory inspection succeeded.

**Log evidence:**
```
2026-05-09 01:07:31 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI failed (exit 1): You've hit your limit · resets May 31, 8pm (America/New_York)
```
```
2026-05-09 01:07:37 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI failed (exit 1): You've hit your limit · resets May 31, 8pm (America/New_York)
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-05-09 01:07:43
**User said:** hey Jane, can you take a look at the ~/code/waterlily project for me

**Problem:** A codebase-inspection request reached Stage 3 without any file context even though the user gave an explicit path

**Root cause:** The proxy forwarded the request with `file_ctx=False`, so Stage 3 was not given project files for `~/code/waterlily`. The file-context detector did not recognize or expand the tilde path.

**Suggested fix:** Expand `~` before path parsing, detect filesystem paths in utterances, and auto-attach repo or file context before escalating code-inspection requests to Stage 3.

**Log evidence:**
```
2026-05-09 01:07:42 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (2102ms) params={}
```
```
2026-05-09 01:07:43 INFO [jane.proxy] [audit-177830] stream_message brain=Claude history=0 msg_len=68 file_ctx=False
```

---

## Issue 5 [MEDIUM]

**Turn:** 2026-05-09 01:07:48
**User said:** I'm currently are you able to see that the website Jane version is not working

**Problem:** Stage 1 emitted unsupported internal labels (`restart server`, `force stage3`) and silently downcast them to `others`

**Root cause:** The classifier was not constrained to the registered intent enum, so it hallucinated out-of-schema labels that look like internal control intents. The pipeline then coerced them to `others`, losing routing fidelity and confidence.

**Suggested fix:** Use structured decoding against the allowed class list, retry or hard-fail invalid labels instead of silently coercing them, and remove any internal control labels from the classifier prompt or few-shot examples.

**Log evidence:**
```
2026-05-09 01:07:47 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'restart server' → others
```
```
2026-05-09 01:07:53 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-05-09 01:07:58 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```

---

## Issue 6 [MEDIUM]

**Turn:** 2026-05-09 01:07:54
**User said:** is stage 3 brain back up by now

**Problem:** The 'persistent' Stage 3 brain was being restarted on each turn, adding latency and undermining continuity

**Root cause:** For Stage 3 turns, the server detected that the standing brain had been spawned locked, restarted it, and then injected only recent history. That defeats true session persistence and adds about 3 seconds end-to-end per turn.

**Suggested fix:** Reinitialize or unlock the standing brain once when vault state changes, preserve the same persistent session across turns, and only fall back to recent-history injection when the session is genuinely lost.

**Log evidence:**
```
2026-05-09 01:07:54 INFO [jane.proxy] [audit-177830] Standing brain turn 1 — injected recent history only
```
```
2026-05-09 01:07:54 INFO [jane.standing_brain] Vault is now unlocked but brain was spawned locked. Restarting brain [claude-opus-4-6]...
```
```
2026-05-09 01:07:56 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (2975ms)
```

---

