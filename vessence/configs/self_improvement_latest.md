# Most Recent Nightly Self-Improvement

- Run started: 2026-06-29 01:00:01
- Report generated: 2026-06-29 02:47:33
- Total runtime: 6451s
- Jobs: 8 total, 7 ok, 1 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260629_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-06-29 01:00:02,793 INFO Committed 2 file(s).
- 2. ✓ Code Auditor (8.9m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (6.6m)
  - Problems:
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 2 dead funcs, 10 dup groups
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
- 6. ✓ Transcript Quality Review (2.4m)
  - Problems:
    - Transcript review found 7 issues: 2 critical, 3 low, 2 medium.
    - Stage 1 emitted an out-of-schema intent label before falling back to others.
    - Stage 1 emitted an out-of-schema 'force stage3' label.
  - Fixes:
    - 2026-06-29 01:38:00,336 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (7 issues)
    - 2026-06-29 01:38:00,337 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 2 medium, 3...
- 7. ✓ Memory Janitor (69.5m)
  - Problems:
    - 8:40.695967184 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-29 06:18:40 WARNING] ModelImporter.cpp:739: Make sure input input_ids h...
    - [0;93m2026-06-29 02:18:40.696013078 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-29 06:18:40 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-29 02:18:40.696029962 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-29 06:18:40 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 9 stale memories out of 20 checked. Stale memories make Ja...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-06-29 02:47:32,969 INFO Pushed successfully.

**Top follow-ups:**

- In intent_classifier.v3.classifier, enforce a closed enum with retry or deterministic normalization for known aliases such as 'web automation'.
- Tighten the classifier prompt and parser so routing hints like 'force stage3' are represented as metadata or simply mapped to the valid 'others' class without warning.

## Executive Summary

- 1 stage(s) need attention because they timed out or exited non-zero.
- 6 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-29 01:00:02,793 INFO Committed 2 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 535s (8.9 min)

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
- Duration: 394s (6.6 min)

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
- Duration: 145s (2.4 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 7 issues: 2 critical, 3 low, 2 medium.
- Stage 1 emitted an out-of-schema intent label before falling back to others.
- Stage 1 emitted an out-of-schema 'force stage3' label.
- A contextual Stage 3 follow-up was sent without conversation history or file context.
- Stage 3 took about 3 minutes for a short request, with memory extraction failures during the request.

### Improvements It Made

- 2026-06-29 01:38:00,336 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (7 issues)
- 2026-06-29 01:38:00,337 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 2 medium, 3 minor issues. The most urgent

### Follow-Up Fixes Recommended

- In intent_classifier.v3.classifier, enforce a closed enum with retry or deterministic normalization for known aliases such as 'web automation'.
- Tighten the classifier prompt and parser so routing hints like 'force stage3' are represented as metadata or simply mapped to the valid 'others' class without warning.
- Preserve session history for Stage 3 calls keyed by sid/audit id, and attach source-code context or route to the Codex/code adapter when the user asks to use source code.
- Run short-term memory extraction asynchronously after responding, validate configured CLI fallbacks at startup, and remove missing fallback commands such as claude from the runtime path.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 4171s (69.5 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- 8:40.695967184 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-29 06:18:40 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-29 02:18:40.696013078 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-29 06:18:40 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-29 02:18:40.696029962 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-29 06:18:40 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-29 02:18:40.853264715 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-29 06:18:40 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-29 02:18:40.853313444 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-29 06:18:40 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 9 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

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

- 2026-06-29 02:47:32,969 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
