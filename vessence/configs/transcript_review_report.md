# Transcript Quality Review — 2026-07-02

Generated: 2026-07-03 01:50:18

## Issue 1 [LOW]

**Turn:** 2026-07-02 01:15:27
**User said:** right now, you are using the same codex process for each prompt instead of spawning

**Problem:** Stage 1 emitted an unsupported classifier label before falling back to Stage 3

**Root cause:** The v3 classifier accepted qwen free-form output, got 'force stage3', failed registry validation, and demoted it to others:Low. The final Stage 3 route was acceptable, but alias handling for explicit escalation labels is broken.

**Suggested fix:** In intent_classifier/v3/classifier.py, canonicalize aliases such as 'force stage3', 'delegate opus', and 'DELEGATE_OPUS' before registry validation, then add a regression test for explicit Stage 3/meta requests.

**Log evidence:**
```
2026-07-02 01:15:22 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'force stage3' → others
```
```
2026-07-02 01:15:22 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (1173ms) params={}
```
```
2026-07-02 01:15:25 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=132 sid_override=True class_protocol=n/a
```

---

## Issue 2 [MEDIUM]

**Turn:** 2026-07-02 01:21:33
**User said:** currently, the waterlily site is web only meant for browsers on laptops and

**Problem:** Stage 1 was slow and rejected a class label because of space/underscore normalization

**Root cause:** qwen returned 'web automation', but the registered class is named 'web_automation'. The exact-match validator demoted it to others:Low after a 19.5s classifier call. The final escalation was usable, but the classifier path added noticeable delay.

**Suggested fix:** Normalize class IDs consistently in intent_classifier/v3/classifier.py by treating spaces and underscores equivalently, or separate display labels from canonical IDs. Add a fast bypass for long code/project prompts that should obviously go to Stage 3.

**Log evidence:**
```
2026-07-02 01:21:32 WARNING [intent_classifier.v3.classifier] v3: qwen returned unknown class 'web automation' → others
```
```
2026-07-02 01:21:32 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (19465ms) params={}
```
```
2026-07-02 01:21:33 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=750 sid_override=True class_protocol=n/a
```

---

## Issue 3 [LOW]

**Turn:** 2026-07-02 01:21:33
**User said:** currently, the waterlily site is web only meant for browsers on laptops and

**Problem:** Short-term memory extraction failed during the Stage 3 workflow

**Root cause:** The memory extractor called the CLI LLM fallback chain; the primary CLI timed out, Gemini timed out, and Claude failed with 401 invalid credentials. The turn could still complete, but memory/writeback for future context was skipped.

**Suggested fix:** Make memory/v1/short_term_extractor.py use the configured available brain/provider, or health-check CLI providers at startup and disable unavailable fallbacks instead of retrying timed-out/auth-broken CLIs.

**Log evidence:**
```
2026-07-02 01:21:53 WARNING [agent_skills.claude_cli_llm] Primary LLM failed: CLI timed out after 45s... Attempting fallback.
```
```
2026-07-02 01:22:38 WARNING [agent_skills.claude_cli_llm] Fallback to gemini failed: CLI timed out after 45s...
```
```
2026-07-02 01:22:45 WARNING [agent_skills.claude_cli_llm] Fallback to claude failed: CLI (claude) failed (exit 1): Failed to authenticate. API Error: 401 Invalid authentication credenti...
```
```
2026-07-02 01:22:45 WARNING [memory.v1.short_term_extractor] short_term_extractor: LLM call failed: CLI (claude) failed (exit 1): Failed to authenticate. API Error: 401 Invalid authentication credentials
```

---

## Issue 4 [MEDIUM]

**Turn:** 2026-07-02 01:29:55
**User said:** # Task: Self-heal android_crash_report: === VESSENCE CRASH REPORT ===

**Problem:** Stage 1 added a 23.1s delay before obvious Stage 3 escalation

**Root cause:** The crash-report/code-repair prompt was always sent through the qwen classifier even though it was clearly too complex for a deterministic handler. The classifier eventually returned others:Low.

**Suggested fix:** In jane_web/jane_v3/pipeline.py, directly route long markdown/log/crash-report/code-edit prompts to Stage 3 before v3_classifier.classify, and keep qwen classification for short actionable voice intents.

**Log evidence:**
```
2026-07-02 01:29:52 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage1 others:Low (23136ms) params={}
```
```
2026-07-02 01:29:53 INFO [jane_web.jane_v2.stage3_escalate] stage3_escalate: reason=others:Low voice=False prompt_len=1622 sid_override=True class_protocol=n/a
```

---

## Issue 5 [CRITICAL]

**Turn:** 2026-07-02 01:29:55
**User said:** # Task: Self-heal android_crash_report: === VESSENCE CRASH REPORT ===

**Problem:** Stage 3 was cancelled after client disconnect and produced no final response payload

**Root cause:** The client disconnected while the brain was still working; the stream task then received CancelledError after 329676ms and finished without a final payload. Source inspection shows the disconnect cleanup awaits wait_for(task) without asyncio.shield, so outer cancellation can still cancel the adapter task despite the intended 'let it finish' behavior.

**Suggested fix:** In jane_web/jane_proxy.py, wrap the adapter task with asyncio.shield inside the disconnect cleanup, persist the eventual final response to session history/job state, and return a resumable job id for long Stage 3 work.

**Log evidence:**
```
2026-07-02 01:35:25 INFO [jane.proxy] [audit-178296] Client disconnected — waiting for adapter task to finish (brain still working)
```
```
2026-07-02 01:35:26 WARNING [jane.proxy] [audit-178296] Brain execution cancelled (stream) after 329676ms — likely client disconnect or timeout. Stack:
```
```
2026-07-02 01:35:26 INFO [jane.proxy] [audit-178296] Jane stream pipeline task finished
```
```
2026-07-02 01:35:26 INFO [jane_web.jane_v3.pipeline] jane_v3 pipeline: stage3 end-to-end (332634ms)
```

---

