# Most Recent Nightly Self-Improvement

- Run started: 2026-06-26 01:00:01
- Report generated: 2026-06-26 03:16:53
- Total runtime: 8211s
- Jobs: 8 total, 6 ok, 1 timeout, 1 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260626_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Problems: none detected
  - Fixes: none applied
- 2. ✗ Code Auditor (4.7m)
  - Problems:
    - 2026-06-26 01:04:44,676 [ERROR] Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for vault_web/recent_turns.py', '--no-verify']' retu...
- 3. ✓ Dead Code Auditor (7.4m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups
- 4. ⏱ Pipeline Audit (30 prompts) (20.0m)
  - Problems:
    - Prompts audited: 6.
    - Classification failures: 3.
    - Response failures: 1.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - CRON_JOBS.md missing entry for active cron script: check_income_cache_load_times.py
    - CRON_JOBS.md missing entry for active cron script: nightly_update_current_month_reports.py
- 6. ✓ Transcript Quality Review (0.8m)
  - Fixes:
    - 2026-06-26 01:32:57,225 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (0 issues)
    - 2026-06-26 01:32:57,227 INFO self_improve_log: recorded [info] Transcript Review — I reviewed yesterday's conversations and nothing looked off — all turns ha...
- 7. ✓ Memory Janitor (103.9m)
  - Problems:
    - 06-26 02:45:26.471488430 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-26 06:45:26 WARNING] ModelImporter.cpp:739: Make sure input i...
    - [0;93m2026-06-26 02:45:26.471540381 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-26 06:45:26 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-26 02:45:26.471556881 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-26 06:45:26 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 11 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-06-26 03:16:51,149 INFO Committed 5 file(s).
    - 2026-06-26 03:16:52,582 INFO Pushed successfully.

## Executive Summary

- 2 stage(s) need attention because they timed out or exited non-zero.
- 6 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `exit-2`
- Duration: 284s (4.7 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- Job ended with status `exit-2`.
- 2026-06-26 01:04:44,676 [ERROR] Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for vault_web/recent_turns.py', '--no-verify']' returned non-zero exit status 1.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 442s (7.4 min)

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
- Prompts audited: 6.
- Classification failures: 3.
- Response failures: 1.
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help pay it, but I need to identify the bill first.[/ACK]

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
- CRON_JOBS.md missing entry for active cron script: check_income_cache_load_times.py
- CRON_JOBS.md missing entry for active cron script: nightly_update_current_month_reports.py
- CRON_JOBS.md missing entry for active cron script: nutricost_deal_monitor.py
- CRON_JOBS.md claims run_kathia_schedule.py is active but no matching cron entry exists
- v2_3stage_pipeline.md missing class row: BUILD_APK
- v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- v2_3stage_pipeline.md missing class row: DELETE_EMAIL

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/doc_drift_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_doc_drift_auditor.log

## Stage 6: Transcript Quality Review

- Status: `ok`
- Duration: 47s (0.8 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-26 01:32:57,225 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (0 issues)
- 2026-06-26 01:32:57,227 INFO self_improve_log: recorded [info] Transcript Review — I reviewed yesterday's conversations and nothing looked off — all turns handled cleanly.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 6232s (103.9 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- -06-26 02:45:26.471488430 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-26 06:45:26 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-26 02:45:26.471540381 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-26 06:45:26 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-26 02:45:26.471556881 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-26 06:45:26 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-26 02:52:09.149142723 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-26 06:52:09 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-26 02:52:09.149196611 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-26 06:52:09 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 11 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_janitor_memory.log

## Stage 8: Auto-Commit + Push (post)

- Status: `ok`
- Duration: 2s (0.0 min)

### What It Did

- Committed and pushed generated fixes and reports after the run.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-26 03:16:51,149 INFO Committed 5 file(s).
- 2026-06-26 03:16:52,582 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
