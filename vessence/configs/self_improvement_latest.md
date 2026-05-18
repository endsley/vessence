# Most Recent Nightly Self-Improvement

- Run started: 2026-05-17 01:00:01
- Report generated: 2026-05-17 01:48:08
- Total runtime: 2886s
- Jobs: 8 total, 6 ok, 1 timeout, 1 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260517_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-17 01:00:01,528 INFO Committed 2 file(s).
- 2. ✗ Code Auditor (0.1m)
  - Problems:
    - 2026-05-17 01:00:04,959 [WARNING] Test generation failed
- 3. ✓ Dead Code Auditor (6.0m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (1.4m)
  - Problems:
    - Prompts audited: 7.
    - Classification failures: 4.
    - Response failures: 7.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (1.1m)
  - Problems:
    - Transcript review found 9 issues: 5 critical, 4 medium.
    - Follow-up reply was not routed through pending_action_resolver and instead went through Stage 1/Stage 3.
    - Prompt-injected class_protocol text was classified as a real greeting and caused the greeting protocol to be loaded.
  - Fixes:
    - 2026-05-17 01:08:37,653 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (9 issues)
    - 2026-05-17 01:08:37,654 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 5 critical, 4 medium iss...
- 7. ✓ Memory Janitor (37.5m)
  - Problems:
    - WARNING:memory.v1.conversation_manager:Thematic archival failed: [Errno 7] Argument list too long: 'claude'
    - WARNING:memory_janitor:Claude Opus janitor call failed: CLI failed (exit 1): You've hit your limit · resets 2am (America/New_York), trying Gemini fallback...
    - WARNING:memory_janitor:Claude Opus janitor call failed: CLI failed (exit 1): You've hit your limit · resets 2am (America/New_York), trying Gemini fallback...
  - Fixes:
    - INFO:memory.v1.conversation_manager:Session 'session_1773577035' closed and cleaned up.
    - INFO:memory.v1.conversation_manager:Session 'session_1773607728' closed and cleaned up.
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [info] Memory Verification — Verified 20 code-related memories one at a time. Skipped 24 recent...
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-05-17 01:46:08,419 INFO Committed 6 file(s).

**Top follow-ups:**

- Persist pending_action state with the conversation/session id and add resolver entry/exit logging before Stage 1, including explicit 'no pending action' reason.
- Strip or escape user-supplied class_protocol/XML-like blocks before classification, and only load class protocols from server-side registry decisions, never from raw user text.

## Executive Summary

- 2 stage(s) need attention because they timed out or exited non-zero.
- 8 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-05-17 01:00:01,528 INFO Committed 2 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `exit-1`
- Duration: 3s (0.1 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- Job ended with status `exit-1`.
- 2026-05-17 01:00:04,959 [WARNING] Test generation failed

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 363s (6.0 min)

### What It Did

- Scanned the codebase for dead files, unreferenced functions, and duplicate function bodies.

### Problems It Found

- Possibly-dead functions: 1.
- Duplicate function bodies: 10 groups.

### Improvements It Made

- [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups

### Evidence Files

- /home/chieh/ambient/vessence/configs/dead_code_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_dead_code_auditor.log

## Stage 4: Pipeline Audit (30 prompts)

- Status: `ok`
- Duration: 83s (1.4 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 7.
- Classification failures: 4.
- Response failures: 7.
- **yes those articles and maybe just two days** (others/stage3): You've hit your limit · resets 2am (America/New_York)
- **currently how does your short-term memory work** (others/stage3): You've hit your limit · resets 2am (America/New_York)
- **how about** (greeting/stage3): You've hit your limit · resets 2am (America/New_York)
- **it seems to me that you are no longing making any sounds when speech to text is ** (others/stage3): You've hit your limit · resets 2am (America/New_York)

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/pipeline_audit_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_pipeline_audit_100.log

## Stage 5: Doc Drift Auditor

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Compared source-of-truth docs against live cron, class, and file state to catch stale documentation.

### Problems It Found

- CRON_JOBS.md missing entry for active cron script: auto_pull.sh
- v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/doc_drift_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_doc_drift_auditor.log

## Stage 6: Transcript Quality Review

- Status: `ok`
- Duration: 65s (1.1 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 9 issues: 5 critical, 4 medium.
- Follow-up reply was not routed through pending_action_resolver and instead went through Stage 1/Stage 3.
- Prompt-injected class_protocol text was classified as a real greeting and caused the greeting protocol to be loaded.
- Greeting Stage 2 handler returned an invalid response shape and forced Stage 3 escalation.
- User reported an Android audio/STT regression, but no Android diagnostic events were present to audit client-side execution.

### Improvements It Made

- 2026-05-17 01:08:37,653 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (9 issues)
- 2026-05-17 01:08:37,654 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 5 critical, 4 medium issues. The most urgent was: Foll

### Follow-Up Fixes Recommended

- Persist pending_action state with the conversation/session id and add resolver entry/exit logging before Stage 1, including explicit 'no pending action' reason.
- Strip or escape user-supplied class_protocol/XML-like blocks before classification, and only load class protocols from server-side registry decisions, never from raw user text.
- Update the greeting handler to return the v3 handler schema consistently, and add a unit test asserting the exact output shape accepted by jane_v3.pipeline.
- Emit structured Android voice_flow diagnostics for STT restart, audio cue request, audio focus state, playback result, and failure reason on every voice turn.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 2250s (37.5 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- WARNING:memory.v1.conversation_manager:Thematic archival failed: [Errno 7] Argument list too long: 'claude'
- WARNING:memory_janitor:Claude Opus janitor call failed: CLI failed (exit 1): You've hit your limit · resets 2am (America/New_York), trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: CLI failed (exit 1): You've hit your limit · resets 2am (America/New_York), trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: CLI failed (exit 1): You've hit your limit · resets 2am (America/New_York), trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: CLI failed (exit 1): You've hit your limit · resets 2am (America/New_York), trying Gemini fallback...

### Improvements It Made

- INFO:memory.v1.conversation_manager:Session 'session_1773577035' closed and cleaned up.
- INFO:memory.v1.conversation_manager:Session 'session_1773607728' closed and cleaned up.
- INFO:agent_skills.self_improve_log:self_improve_log: recorded [info] Memory Verification — Verified 20 code-related memories one at a time. Skipped 24 recently verified entries. All checked o

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_janitor_memory.log

## Stage 8: Auto-Commit + Push (post)

- Status: `timeout`
- Duration: 120s (2.0 min)

### What It Did

- Committed and pushed generated fixes and reports after the run.

### Problems It Found

- Job ended with status `timeout`.

### Improvements It Made

- 2026-05-17 01:46:08,419 INFO Committed 6 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
