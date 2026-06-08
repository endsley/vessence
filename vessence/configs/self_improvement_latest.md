# Most Recent Nightly Self-Improvement

- Run started: 2026-06-07 01:00:01
- Report generated: 2026-06-07 02:03:13
- Total runtime: 3790s
- Jobs: 8 total, 7 ok, 1 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260607_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-06-07 01:00:01,544 INFO Committed 8 file(s).
- 2. ✓ Code Auditor (2.5m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (6.1m)
  - Problems:
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] AUTO-DELETED: memory/v1/update_identity.py
    - [dead-code] Done — 1 auto-deleted, 0 flagged, 2 dead funcs, 10 dup groups
- 4. ⏱ Pipeline Audit (30 prompts) (20.0m)
  - Problems:
    - Prompts audited: 6.
    - Classification failures: 2.
    - Response failures: 3.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: BUILD_APK
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (0.6m)
  - Problems:
    - Transcript review found 11 issues: 4 critical, 1 low, 6 medium.
    - Known delegate_opus intent was recognized but no Stage 2 handler was available.
    - Payment/setup intent was classified as `others` due unsupported classifier output.
  - Fixes:
    - 2026-06-07 01:29:09,319 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (11 issues)
    - 2026-06-07 01:29:09,320 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 4 critical, 6 medium, 1...
- 7. ✓ Memory Janitor (34.0m)
  - Problems:
    - 365743839 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-07 05:51:17 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids h...
    - [0;93m2026-06-07 01:51:17.556635708 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-07 05:51:17 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-07 01:51:17.556685630 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-07 05:51:17 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 8 stale memories out of 20 checked. Stale memories make Ja...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-06-07 02:03:12,163 INFO Pushed successfully.

**Top follow-ups:**

- Register a Stage 2 `delegate_opus` handler (and coverage test) so high-confidence matches do not always fall back to Stage3.
- Add/normalize `web automation` and related aliases (payment/setup in browser) into a first-class intent with a Stage2 handler or explicit dispatcher rule.

## Executive Summary

- 1 stage(s) need attention because they timed out or exited non-zero.
- 7 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-07 01:00:01,544 INFO Committed 8 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 147s (2.5 min)

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
- Duration: 365s (6.1 min)

### What It Did

- Scanned the codebase for dead files, unreferenced functions, and duplicate function bodies.

### Problems It Found

- Possibly-dead functions: 2.
- Duplicate function bodies: 10 groups.

### Improvements It Made

- [dead-code] AUTO-DELETED: memory/v1/update_identity.py
- [dead-code] Done — 1 auto-deleted, 0 flagged, 2 dead funcs, 10 dup groups

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
- Prompts audited: 6.
- Classification failures: 2.
- Response failures: 3.
- **what was your result** (greeting/stage3): Chieh, I don’t have a prior result visible in this thread. Which result are you asking about? [[AWAITING:which_result
- **please set up this payment for me on the local browser** (web_automation/stage3): [ACK]Chieh, I can help with the payment setup, but I need one detail first.[/ACK]
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help with the payment, but I need one quick detail first.[/ACK]

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
- v2_3stage_pipeline.md missing class row: BUILD_APK
- v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- v2_3stage_pipeline.md missing class row: DELETE_EMAIL
- v2_3stage_pipeline.md missing class row: DELETE_MESSAGES
- v2_3stage_pipeline.md missing class row: DO_MATH
- v2_3stage_pipeline.md missing class row: RESTART_SERVER
- v2_3stage_pipeline.md missing class row: SEND_EMAIL

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/doc_drift_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_doc_drift_auditor.log

## Stage 6: Transcript Quality Review

- Status: `ok`
- Duration: 34s (0.6 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 11 issues: 4 critical, 1 low, 6 medium.
- Known delegate_opus intent was recognized but no Stage 2 handler was available.
- Payment/setup intent was classified as `others` due unsupported classifier output.
- Access-check intent was also forced to `others`.
- `force stage3` intent was not recognized as its own class.

### Improvements It Made

- 2026-06-07 01:29:09,319 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (11 issues)
- 2026-06-07 01:29:09,320 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 4 critical, 6 medium, 1 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Register a Stage 2 `delegate_opus` handler (and coverage test) so high-confidence matches do not always fall back to Stage3.
- Add/normalize `web automation` and related aliases (payment/setup in browser) into a first-class intent with a Stage2 handler or explicit dispatcher rule.
- Add explicit intent aliases for project/tooling availability checks and map them to a stable class rather than relying on fallback routing.
- Add `force stage3` (and close variants) to the classifier/intent registry, with explicit handling in Stage2 or a direct stage3 override policy.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 2040s (34.0 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- 365743839 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-07 05:51:17 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-07 01:51:17.556635708 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-07 05:51:17 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-07 01:51:17.556685630 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-07 05:51:17 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-07 01:51:17.556700897 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-07 05:51:17 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-07 01:53:45.261352279 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-07 05:53:45 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 8 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_janitor_memory.log

## Stage 8: Auto-Commit + Push (post)

- Status: `ok`
- Duration: 1s (0.0 min)

### What It Did

- Committed and pushed generated fixes and reports after the run.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-07 02:03:12,163 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
