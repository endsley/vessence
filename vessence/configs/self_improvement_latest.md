# Most Recent Nightly Self-Improvement

- Run started: 2026-05-11 01:00:01
- Report generated: 2026-05-11 02:41:51
- Total runtime: 6109s
- Jobs: 8 total, 5 ok, 3 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260511_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-11 01:00:02,023 INFO Committed 4 file(s).
- 2. ✓ Code Auditor (9.8m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (7.1m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups
- 4. ⏱ Pipeline Audit (30 prompts) (20.0m)
  - Problems:
    - Prompts audited: 13.
    - Classification failures: 8.
    - Response failures: 13.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (2.9m)
  - Problems:
    - Transcript review found 7 issues: 2 critical, 5 medium.
    - Follow-up answer was routed through Stage 1 instead of the pending_action_resolver
    - Straightforward question incurred extreme Stage 3 latency
  - Fixes:
    - 2026-05-11 01:39:50,314 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (7 issues)
    - 2026-05-11 01:39:50,316 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 5 medium iss...
- 7. ⏱ Memory Janitor (60.0m)
  - Problems:
    - WARNING:memory_janitor:Claude Opus janitor call failed: CLI timed out after 180s, trying Gemini fallback...
    - WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
    - WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
  - Fixes:
    - INFO:memory.v1.conversation_manager:Session 'session_1773577613' closed and cleaned up.
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-05-11 02:39:51,400 INFO Committed 4 file(s).

**Top follow-ups:**

- Gate Stage 1 behind an explicit pending-action lookup keyed by session id, and add resolver hit/miss logs so follow-up routing failures are visible.
- Keep the standing brain usable after vault unlock instead of restarting per turn, and move `short_term_extractor` off the synchronous request path behind a hard latency budget.

## Executive Summary

- 3 stage(s) need attention because they timed out or exited non-zero.
- 6 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-05-11 01:00:02,023 INFO Committed 4 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 585s (9.8 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 426s (7.1 min)

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

- Status: `timeout`
- Duration: 1200s (20.0 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Job ended with status `timeout`.
- Prompts audited: 13.
- Classification failures: 8.
- Response failures: 13.
- **I want them to periodically get the lead after some time** (timer/stage3): You've hit your limit · resets May 31, 8pm (America/New_York)
- **yes those articles and maybe just two days** (others/stage3): You've hit your limit · resets May 31, 8pm (America/New_York)
- **currently how does your short-term memory work** (others/stage3): You've hit your limit · resets May 31, 8pm (America/New_York)
- **how about** (greeting/stage3): You've hit your limit · resets May 31, 8pm (America/New_York)

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
- Duration: 175s (2.9 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 7 issues: 2 critical, 5 medium.
- Follow-up answer was routed through Stage 1 instead of the pending_action_resolver
- Straightforward question incurred extreme Stage 3 latency
- Stage 1 was vulnerable to prompt-like control text and misclassified the message as `greeting`
- The Stage 2 greeting handler returned an invalid payload shape and could not complete the fast path

### Improvements It Made

- 2026-05-11 01:39:50,314 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (7 issues)
- 2026-05-11 01:39:50,316 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 5 medium issues. The most urgent was: Stag

### Follow-Up Fixes Recommended

- Gate Stage 1 behind an explicit pending-action lookup keyed by session id, and add resolver hit/miss logs so follow-up routing failures are visible.
- Keep the standing brain usable after vault unlock instead of restarting per turn, and move `short_term_extractor` off the synchronous request path behind a hard latency budget.
- Sanitize classifier input by stripping or heavily down-weighting XML/control blocks such as `<class_protocol ...>`, and add adversarial tests requiring these inputs to fall back to `others` or a dedicated debug/safety class.
- Validate handler outputs against a typed schema at registration time and add a unit test for the greeting handler's return shape so invalid payloads cannot reach production.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `timeout`
- Duration: 3600s (60.0 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- Job ended with status `timeout`.
- WARNING:memory_janitor:Claude Opus janitor call failed: CLI timed out after 180s, trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: CLI timed out after 180s, trying Gemini fallback...

### Improvements It Made

- INFO:memory.v1.conversation_manager:Session 'session_1773577613' closed and cleaned up.

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

- 2026-05-11 02:39:51,400 INFO Committed 4 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
