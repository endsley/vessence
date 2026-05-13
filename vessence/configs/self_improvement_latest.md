# Most Recent Nightly Self-Improvement

- Run started: 2026-05-12 01:00:01
- Report generated: 2026-05-12 02:27:49
- Total runtime: 5260s
- Jobs: 8 total, 6 ok, 2 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260512_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-12 01:00:02,090 INFO Committed 3 file(s).
- 2. ✓ Code Auditor (4.6m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (6.5m)
  - Problems:
    - Dead files — review needed: 1.
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 1 flagged, 2 dead funcs, 10 dup groups
- 4. ⏱ Pipeline Audit (30 prompts) (20.0m)
  - Problems:
    - Prompts audited: 13.
    - Classification failures: 8.
    - Response failures: 13.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (5.0m)
  - Fixes:
    - 2026-05-12 01:36:10,446 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (0 issues)
    - 2026-05-12 01:36:10,447 INFO self_improve_log: recorded [info] Transcript Review — I reviewed yesterday's conversations and nothing looked off — all turns ha...
- 7. ✓ Memory Janitor (49.5m)
  - Problems:
    - WARNING:memory.v1.conversation_manager:Thematic archival failed: [Errno 7] Argument list too long: 'claude'
    - WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
    - WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
  - Fixes:
    - INFO:memory.v1.conversation_manager:Session 'session_1773577035' closed and cleaned up.
    - INFO:memory.v1.conversation_manager:Session 'session_1773598338' closed and cleaned up.
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 10 stale memories out of 20 checked. Stale memories make J...
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-05-12 02:25:41,857 INFO Committed 7 file(s).

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

- 2026-05-12 01:00:02,090 INFO Committed 3 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 275s (4.6 min)

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
- Duration: 392s (6.5 min)

### What It Did

- Scanned the codebase for dead files, unreferenced functions, and duplicate function bodies.

### Problems It Found

- Dead files — review needed: 1.
- Possibly-dead functions: 2.
- Duplicate function bodies: 10 groups.

### Improvements It Made

- [dead-code] Done — 0 auto-deleted, 1 flagged, 2 dead funcs, 10 dup groups

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
- Duration: 300s (5.0 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-05-12 01:36:10,446 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (0 issues)
- 2026-05-12 01:36:10,447 INFO self_improve_log: recorded [info] Transcript Review — I reviewed yesterday's conversations and nothing looked off — all turns handled cleanly.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 2970s (49.5 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- WARNING:memory.v1.conversation_manager:Thematic archival failed: [Errno 7] Argument list too long: 'claude'
- WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...

### Improvements It Made

- INFO:memory.v1.conversation_manager:Session 'session_1773577035' closed and cleaned up.
- INFO:memory.v1.conversation_manager:Session 'session_1773598338' closed and cleaned up.
- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 10 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

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

- 2026-05-12 02:25:41,857 INFO Committed 7 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
