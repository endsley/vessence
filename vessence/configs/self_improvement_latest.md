# Most Recent Nightly Self-Improvement

- Run started: 2026-05-15 01:00:01
- Report generated: 2026-05-15 02:35:44
- Total runtime: 5742s
- Jobs: 8 total, 6 ok, 2 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260515_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-15 01:00:02,821 INFO Committed 6 file(s).
- 2. ✓ Code Auditor (7.5m)
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
    - Prompts audited: 12.
    - Classification failures: 7.
    - Response failures: 12.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (3.0m)
  - Problems:
    - Transcript review found 8 issues: 3 critical, 5 medium.
    - Follow-up reply was not resolved by the pending-action path and was treated as a fresh `others` turn
    - Stage 1 misclassified user-supplied protocol text as `greeting` with Very High confidence
  - Fixes:
    - 2026-05-15 01:37:38,483 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (8 issues)
    - 2026-05-15 01:37:38,484 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 3 critical, 5 medium iss...
- 7. ✓ Memory Janitor (56.1m)
  - Problems:
    - WARNING:memory.v1.conversation_manager:Thematic archival failed: [Errno 7] Argument list too long: 'claude'
    - WARNING:memory_janitor:Claude Opus janitor call failed: CLI timed out after 180s, trying Gemini fallback...
    - WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
  - Fixes:
    - INFO:memory.v1.conversation_manager:Session 'session_1773577035' closed and cleaned up.
    - INFO:memory.v1.conversation_manager:Session 'session_1773599591' closed and cleaned up.
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [info] Memory Verification — Verified 20 code-related memories one at a time. Skipped 24 recent...
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-05-15 02:33:44,872 INFO Committed 5 file(s).

**Top follow-ups:**

- Run pending-action resolution before Stage 1 on every turn, persist pending-action metadata until consumed, and add explicit resolver hit/miss logs.
- Sanitize or strip control-like markup before classification, add adversarial tests for protocol-looking payloads, and require semantic validation before loading any class protocol.

## Executive Summary

- 2 stage(s) need attention because they timed out or exited non-zero.
- 8 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 1s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-05-15 01:00:02,821 INFO Committed 6 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 450s (7.5 min)

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
- Duration: 427s (7.1 min)

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
- Prompts audited: 12.
- Classification failures: 7.
- Response failures: 12.
- **yes those articles and maybe just two days** (others/stage3): You've hit your limit · resets 10pm (America/New_York)
- **currently how does your short-term memory work** (others/stage3): You've hit your limit · resets 10pm (America/New_York)
- **how about** (greeting/stage3): You've hit your limit · resets 10pm (America/New_York)
- **it seems to me that you are no longing making any sounds when speech to text is ** (others/stage3): You've hit your limit · resets 10pm (America/New_York)

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
- Duration: 177s (3.0 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 8 issues: 3 critical, 5 medium.
- Follow-up reply was not resolved by the pending-action path and was treated as a fresh `others` turn
- Stage 1 misclassified user-supplied protocol text as `greeting` with Very High confidence
- The greeting fast-path handler failed its contract and returned an invalid shape
- Stage 3 took over 5 minutes to answer a runtime problem report

### Improvements It Made

- 2026-05-15 01:37:38,483 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (8 issues)
- 2026-05-15 01:37:38,484 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 3 critical, 5 medium issues. The most urgent was: Stag

### Follow-Up Fixes Recommended

- Run pending-action resolution before Stage 1 on every turn, persist pending-action metadata until consumed, and add explicit resolver hit/miss logs.
- Sanitize or strip control-like markup before classification, add adversarial tests for protocol-looking payloads, and require semantic validation before loading any class protocol.
- Make the greeting handler schema-safe for malformed inputs and fall back to a canned greeting response instead of emitting an invalid handler result.
- Stop respawning the standing brain on routine unlocked turns, move short-term extraction off the critical path, and enforce a hard Stage 3 response SLA with graceful fallback.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 3366s (56.1 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- WARNING:memory.v1.conversation_manager:Thematic archival failed: [Errno 7] Argument list too long: 'claude'
- WARNING:memory_janitor:Claude Opus janitor call failed: CLI timed out after 180s, trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: CLI timed out after 180s, trying Gemini fallback...

### Improvements It Made

- INFO:memory.v1.conversation_manager:Session 'session_1773577035' closed and cleaned up.
- INFO:memory.v1.conversation_manager:Session 'session_1773599591' closed and cleaned up.
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

- 2026-05-15 02:33:44,872 INFO Committed 5 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
