# Most Recent Nightly Self-Improvement

- Run started: 2026-06-11 01:00:02
- Report generated: 2026-06-11 02:32:59
- Total runtime: 5577s
- Jobs: 8 total, 8 ok, 0 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260611_010002.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-06-11 01:00:02,326 INFO Committed 3 file(s).
- 2. ✓ Code Auditor (7.4m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (6.0m)
  - Problems:
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 2 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (19.8m)
  - Problems:
    - Prompts audited: 6.
    - Classification failures: 2.
    - Response failures: 3.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: BUILD_APK
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (2.1m)
  - Problems:
    - Transcript review found 7 issues: 1 critical, 4 low, 2 medium.
    - Stage 1 emitted an unsupported intent label before falling back to others.
    - Stage 1 emitted an unsupported 'force stage3' label.
  - Fixes:
    - 2026-06-11 01:35:18,591 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (7 issues)
    - 2026-06-11 01:35:18,592 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 2 medium, 4...
- 7. ✓ Memory Janitor (57.6m)
  - Problems:
    - [0;93m2026-06-11 02:08:06.023302257 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-11 06:08:06 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-11 02:08:06.023345854 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-11 06:08:06 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-11 02:08:06.023358017 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-11 06:08:06 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 10 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-06-11 02:32:59,067 INFO Pushed successfully.

**Top follow-ups:**

- Constrain the classifier output to the allowed intent enum with strict parsing, or add a supported code/project-work intent that intentionally routes to Stage 3.
- Teach the classifier that escalation is represented by the supported 'others' intent plus low confidence, not by inventing a 'force stage3' class.

## Executive Summary

- All stages exited cleanly.
- 6 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-11 01:00:02,326 INFO Committed 3 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 443s (7.4 min)

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
- Duration: 359s (6.0 min)

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
- Duration: 1189s (19.8 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 6.
- Classification failures: 2.
- Response failures: 3.
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help, but I need to know what we’re paying first.[/ACK]
- **right now, you are using the same codex process for each prompt instead of spawn** (others/stage3): [ACK]Chieh, I’ll verify the current Stage 3 brain launch path quickly.[/ACK]I found the relevant implementation: Stage 3 has a dedicated `standing_cod
- **currently, the waterlily site is web only meant for browsers on laptops and comp** (others/stage3): [ACK]Chieh, I’ll inspect the Waterlily and education projects first, then adapt the Waterlily UI for mobile across the site; this will take a bit.[/AC

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
- Duration: 124s (2.1 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 7 issues: 1 critical, 4 low, 2 medium.
- Stage 1 emitted an unsupported intent label before falling back to others.
- Stage 1 emitted an unsupported 'force stage3' label.
- Context-dependent follow-up was sent to Stage 3 with no conversation history.
- Stage 3 latency was very high for a short project-familiarization request.

### Improvements It Made

- 2026-06-11 01:35:18,591 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (7 issues)
- 2026-06-11 01:35:18,592 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 2 medium, 4 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Constrain the classifier output to the allowed intent enum with strict parsing, or add a supported code/project-work intent that intentionally routes to Stage 3.
- Teach the classifier that escalation is represented by the supported 'others' intent plus low confidence, not by inventing a 'force stage3' class.
- Persist and pass session history into Stage 3 calls, or have Stage 3 set a pending_action when asking for source-code confirmation so pending_action_resolver routes the next reply without reclassification.
- Run long codebase exploration as an async job with progress updates, or stream Stage 3 tool/activity status so the user is not left waiting silently.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 3458s (57.6 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-06-11 02:08:06.023302257 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-11 06:08:06 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-11 02:08:06.023345854 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-11 06:08:06 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-11 02:08:06.023358017 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-11 06:08:06 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-11 02:08:06.194036813 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-11 06:08:06 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-11 02:08:06.194077767 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-11 06:08:06 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 10 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

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

- 2026-06-11 02:32:59,067 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
