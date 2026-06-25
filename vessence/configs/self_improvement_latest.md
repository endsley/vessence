# Most Recent Nightly Self-Improvement

- Run started: 2026-06-25 01:00:01
- Report generated: 2026-06-25 03:30:12
- Total runtime: 9011s
- Jobs: 8 total, 7 ok, 0 timeout, 1 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260625_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-06-25 01:00:02,719 INFO Committed 2 file(s).
- 2. ✗ Code Auditor (2.0m)
  - Problems:
    - 2026-06-25 01:02:04,492 [ERROR] Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for vault_web/recent_turns.py', '--no-verify']' retu...
- 3. ✓ Dead Code Auditor (7.3m)
  - Problems:
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 2 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (17.9m)
  - Problems:
    - Prompts audited: 6.
    - Classification failures: 3.
    - Response failures: 1.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - CRON_JOBS.md missing entry for active cron script: check_income_cache_load_times.py
    - CRON_JOBS.md missing entry for active cron script: nightly_update_current_month_reports.py
- 6. ✓ Transcript Quality Review (2.5m)
  - Problems:
    - Transcript review found 6 issues: 2 critical, 2 low, 2 medium.
    - Stage 1 produced an out-of-schema intent label before falling back to others.
    - Stage 1 produced an out-of-schema intent label and took over 6 seconds before fallback.
  - Fixes:
    - 2026-06-25 01:29:46,428 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (6 issues)
    - 2026-06-25 01:29:46,429 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 2 medium, 2...
- 7. ✓ Memory Janitor (120.4m)
  - Problems:
    - [0;93m2026-06-25 02:48:09.181779130 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-25 06:48:09 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-25 02:48:09.181825216 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-25 06:48:09 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-25 02:48:09.181837246 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-25 06:48:09 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 14 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-06-25 03:30:12,670 INFO Pushed successfully.

**Top follow-ups:**

- Constrain Stage 1 decoding to the allowed intent enum, or retry once when the model returns an unknown label before coercing to others.
- Add strict enum validation for classifier output and a fast rule-based Stage 3 route for architecture/source-code questions.

## Executive Summary

- 1 stage(s) need attention because they timed out or exited non-zero.
- 6 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 1s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-25 01:00:02,719 INFO Committed 2 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `exit-2`
- Duration: 122s (2.0 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- Job ended with status `exit-2`.
- 2026-06-25 01:02:04,492 [ERROR] Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for vault_web/recent_turns.py', '--no-verify']' returned non-zero exit status 1.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 439s (7.3 min)

### What It Did

- Scanned the codebase for dead files, unreferenced functions, and duplicate function bodies.

### Problems It Found

- Possibly-dead functions: 2.
- Duplicate function bodies: 10 groups.

### Improvements It Made

- [dead-code] Done — 0 auto-deleted, 0 flagged, 2 dead funcs, 10 dup groups

### Evidence Files

- /home/chieh/ambient/vessence/configs/dead_code_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_dead_code_auditor.log

## Stage 4: Pipeline Audit (30 prompts)

- Status: `ok`
- Duration: 1072s (17.9 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

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
- Duration: 149s (2.5 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 6 issues: 2 critical, 2 low, 2 medium.
- Stage 1 produced an out-of-schema intent label before falling back to others.
- Stage 1 produced an out-of-schema intent label and took over 6 seconds before fallback.
- Stage 3 follow-up context was dropped for a context-dependent reply.
- Stage 3 kept the turn open for over 3 minutes.

### Improvements It Made

- 2026-06-25 01:29:46,428 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (6 issues)
- 2026-06-25 01:29:46,429 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 2 medium, 2 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Constrain Stage 1 decoding to the allowed intent enum, or retry once when the model returns an unknown label before coercing to others.
- Add strict enum validation for classifier output and a fast rule-based Stage 3 route for architecture/source-code questions.
- Load prior turns by session id before Stage 3 escalation, or create a Stage 3 follow-up context record so short replies like this include the previous request.
- For repo-familiarization tasks, return a quick acknowledgement and run the project scan asynchronously with progress events instead of blocking the conversation turn.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 7223s (120.4 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-06-25 02:48:09.181779130 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-25 06:48:09 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-25 02:48:09.181825216 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-25 06:48:09 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-25 02:48:09.181837246 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-25 06:48:09 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-25 02:48:09.360064483 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-25 06:48:09 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-25 02:48:09.360106156 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-25 06:48:09 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 14 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

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

- 2026-06-25 03:30:12,670 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
