# Most Recent Nightly Self-Improvement

- Run started: 2026-06-28 01:00:01
- Report generated: 2026-06-28 02:43:18
- Total runtime: 6197s
- Jobs: 8 total, 7 ok, 1 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260628_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-06-28 01:00:03,157 INFO Committed 19 file(s).
- 2. ✓ Code Auditor (2.7m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (7.3m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups
- 4. ⏱ Pipeline Audit (30 prompts) (20.0m)
  - Problems:
    - Prompts audited: 6.
    - Classification failures: 3.
    - Response failures: 4.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - CRON_JOBS.md missing entry for active cron script: check_income_cache_load_times.py
    - CRON_JOBS.md missing entry for active cron script: nightly_update_current_month_reports.py
- 6. ✓ Transcript Quality Review (4.0m)
  - Problems:
    - Transcript review found 9 issues: 2 critical, 2 low, 5 medium.
    - Very short ambiguous request took the slow Stage 3 path instead of a fast clarification.
    - Stage 1 emitted an out-of-schema intent label.
  - Fixes:
    - 2026-06-28 01:34:08,342 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (9 issues)
    - 2026-06-28 01:34:08,343 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 5 medium, 2...
- 7. ✓ Memory Janitor (69.1m)
  - Problems:
    - [0;93m2026-06-28 02:24:56.299907383 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-28 06:24:56 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-28 02:24:56.299967489 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-28 06:24:56 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-28 02:24:56.299981295 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-28 06:24:56 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 13 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-06-28 02:43:18,752 INFO Pushed successfully.

**Top follow-ups:**

- Add a deterministic clarification response for very short low-confidence others turns, and cap Stage 1 latency with a fast fallback.
- Constrain Stage 1 output to the allowed enum with strict parsing, and add alias handling or examples for project/web-automation requests.

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

- 2026-06-28 01:00:03,157 INFO Committed 19 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 163s (2.7 min)

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
- Duration: 441s (7.3 min)

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
- Response failures: 4.
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help, but I need to know which payment you mean.[/ACK]
- **right now, you are using the same codex process for each prompt instead of spawn** (others/stage3): [ACK]Chieh, I’ll verify the stage 3 brain runtime path in the code before answering; this should be quick.[/ACK]I’m searching the runtime entrypoints
- **use the source code as your guide** (todo list/stage3): Understood, Chieh. I’ll treat the source code as the ground truth and verify behavior against it before making claims.
- **currently, the waterlily site is web only meant for browsers on laptops and comp** (others/stage3): [ACK]Chieh, I’ll inspect Waterlily and the education project mobile patterns first, then implement responsive mobile UIs across the site; this will ta

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
- CRON_JOBS.md missing entry for active cron script: sync_mychart_doctor_appointments.py
- CRON_JOBS.md claims run_kathia_schedule.py is active but no matching cron entry exists
- v2_3stage_pipeline.md missing class row: BUILD_APK
- v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/doc_drift_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_doc_drift_auditor.log

## Stage 6: Transcript Quality Review

- Status: `ok`
- Duration: 238s (4.0 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 9 issues: 2 critical, 2 low, 5 medium.
- Very short ambiguous request took the slow Stage 3 path instead of a fast clarification.
- Stage 1 emitted an out-of-schema intent label.
- Stage 1 emitted an out-of-schema 'force stage3' intent.
- Brain health check endpoint returned 404 during a Stage 3 process-health question.

### Improvements It Made

- 2026-06-28 01:34:08,342 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (9 issues)
- 2026-06-28 01:34:08,343 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 5 medium, 2 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Add a deterministic clarification response for very short low-confidence others turns, and cap Stage 1 latency with a fast fallback.
- Constrain Stage 1 output to the allowed enum with strict parsing, and add alias handling or examples for project/web-automation requests.
- Use strict enum validation with one repair attempt, and add tests that reject meta-routing labels like 'force stage3'.
- Implement /api/jane/brain/health or update the caller to the real health endpoint; include active brain process/session state in the response.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 4148s (69.1 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-06-28 02:24:56.299907383 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-28 06:24:56 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-28 02:24:56.299967489 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-28 06:24:56 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-28 02:24:56.299981295 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-28 06:24:56 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-28 02:24:56.468085706 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-28 06:24:56 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-28 02:24:56.468126520 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-28 06:24:56 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 13 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

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

- 2026-06-28 02:43:18,752 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
