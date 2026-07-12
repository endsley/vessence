# Transcript Quality Review — 2026-07-10

Generated: 2026-07-11 23:48:40

## Issue 1 [LOW]

**Turn:** 2026-07-10 23:45:10
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 1 classifier emitted an unsupported class label before falling back to others.

**Root cause:** The classifier returned 'force stage3', which is not in the accepted intent enum. The pipeline converted it to others:Low, which still escalated correctly, so the user-facing behavior was not broken.

**Suggested fix:** Add 'force stage3' as an explicit alias for the Stage 3 escalation path, or tighten the classifier prompt/output schema so it only returns supported labels.

**Log evidence:**
```
2026-07-10 23:45:08 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-07-10 23:45:08 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (4278ms) params={}
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-07-10 23:45:10
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 3 response latency was very high for a straightforward source-code question.

**Root cause:** The turn escalated to Claude and completed only after about 202 seconds. No handler fast path applied, and no intermediate client-side/progress events are shown.

**Suggested fix:** Add a timeout/progress policy for Stage 3 turns and consider a deterministic source-inspection handler for questions about Jane's own runtime configuration.

**Log evidence:**
```
2026-07-10 23:45:09 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=132 sid_override=True class_protocol=n/a
```
```
2026-07-10 23:48:31 INFO [jane.standing_brain] Brain [claude-sonnet-5] turn 1 complete in 201065ms (1116 chars, 1 raw events)
```
```
2026-07-10 23:48:31 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (202151ms)
```

---

## Issue 3 [CRITICAL]

**Turn:** 2026-07-10 23:48:39
**User said:** use the source code as your guide

**Problem:** Stage 3 follow-up took over 10 minutes and had an LLM timeout/fallback during the turn.

**Root cause:** The follow-up was routed to Stage 3 with injected recent history, but the primary LLM timed out after 45 seconds and the standing brain did not finish until about 633 seconds later. Heartbeat pings also failed repeatedly during the long-running turn.

**Suggested fix:** Enforce hard wall-clock limits around Stage 3/fallback execution, surface a partial/progress response before long source scans, and investigate why the fallback path blocked heartbeat handling.

**Log evidence:**
```
2026-07-10 23:48:38 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=33 sid_override=True class_protocol=n/a
```
```
2026-07-10 23:48:39 INFO [jane.proxy] [audit-178374] Standing brain turn 1 — injected recent history only
```
```
2026-07-10 23:49:17 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-07-10 23:56:32 WARNING [jane.web] heartbeat ping failed (11 in a row):
```
```
2026-07-10 23:59:12 INFO [jane.standing_brain] Brain [claude-sonnet-5] turn 2 complete in 632818ms (1231 chars, 1 raw events)
```
```
2026-07-10 23:59:15 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (636753ms)
```

---

