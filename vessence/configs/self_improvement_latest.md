# Most Recent Nightly Self-Improvement

- Run started: 2026-07-23 23:30:01
- Report generated: 2026-07-24 01:28:08
- Total runtime: 7085s
- Jobs: 8 total, 6 ok, 2 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260723_233001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-07-23 23:30:02,262 INFO Committed 5 file(s).
- 2. ✓ Code Auditor (0.0m)
  - Problems: none detected
  - Fixes: none applied
- 3. ⏱ Dead Code Auditor (15.0m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 11 groups.
- 4. ⏱ Pipeline Audit (30 prompts) (20.0m)
  - Problems:
    - Prompts audited: 5.
    - Classification failures: 2.
    - Response failures: 4.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: self_healing_repair.py
    - CRON_JOBS.md claims check_for_updates.py is active but no matching cron entry exists
    - CRON_JOBS.md claims generate_code_map.py is active but no matching cron entry exists
- 6. ✓ Transcript Quality Review (0.5m)
  - Fixes:
    - 2026-07-24 00:05:29,864 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (0 issues)
    - 2026-07-24 00:05:29,865 INFO self_improve_log: recorded [info] Transcript Review — I reviewed yesterday's conversations and nothing looked off — all turns ha...
- 7. ✓ Memory Janitor (82.5m)
  - Problems:
    - [0;93m2026-07-24 00:52:15.165397050 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-24 04:52:15 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-07-24 00:52:15.165448920 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-24 04:52:15 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-07-24 00:52:15.165464744 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-24 04:52:15 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 14 stale memories out of 40 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.1m)
  - Fixes:
    - 2026-07-24 01:28:04,496 INFO Committed 5 file(s).
    - 2026-07-24 01:28:07,113 INFO Pushed successfully.

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

- 2026-07-23 23:30:02,262 INFO Committed 5 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 0s (0.0 min)

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

- Status: `timeout`
- Duration: 900s (15.0 min)

### What It Did

- Scanned the codebase for dead files, unreferenced functions, and duplicate function bodies.

### Problems It Found

- Job ended with status `timeout`.
- Possibly-dead functions: 1.
- Duplicate function bodies: 11 groups.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

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
- Prompts audited: 5.
- Classification failures: 2.
- Response failures: 4.
- **currently, the waterlily site is web only meant for browsers on laptops and comp** (others/stage3): You've hit your org's monthly spend limit · run /usage-credits to ask your admin for a higher limit
- **# Task: Self-heal android_crash_report: === VESSENCE CRASH REPORT ===

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

- CRON_JOBS.md missing entry for active cron script: self_healing_repair.py
- CRON_JOBS.md claims check_for_updates.py is active but no matching cron entry exists
- CRON_JOBS.md claims generate_code_map.py is active but no matching cron entry exists
- CRON_JOBS.md claims iterative_refactor_scheduler.py is active but no matching cron entry exists
- CRON_JOBS.md claims notify_updates.py is active but no matching cron entry exists
- CRON_JOBS.md claims usb_sync.py is active but no matching cron entry exists

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/doc_drift_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_doc_drift_auditor.log

## Stage 6: Transcript Quality Review

- Status: `ok`
- Duration: 27s (0.5 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-07-24 00:05:29,864 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (0 issues)
- 2026-07-24 00:05:29,865 INFO self_improve_log: recorded [info] Transcript Review — I reviewed yesterday's conversations and nothing looked off — all turns handled cleanly.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 4953s (82.5 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-07-24 00:52:15.165397050 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-24 04:52:15 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-07-24 00:52:15.165448920 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-24 04:52:15 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-07-24 00:52:15.165464744 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-24 04:52:15 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-07-24 00:52:15.352544126 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-24 04:52:15 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-07-24 00:52:15.352604221 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-24 04:52:15 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 14 stale memories out of 40 checked. Stale memories make Jane give wrong answers about her own

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_janitor_memory.log

## Stage 8: Auto-Commit + Push (post)

- Status: `ok`
- Duration: 3s (0.1 min)

### What It Did

- Committed and pushed generated fixes and reports after the run.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-07-24 01:28:04,496 INFO Committed 5 file(s).
- 2026-07-24 01:28:07,113 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
