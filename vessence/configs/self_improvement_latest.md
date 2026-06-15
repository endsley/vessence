# Most Recent Nightly Self-Improvement

- Run started: 2026-06-14 01:00:01
- Report generated: 2026-06-14 02:19:28
- Total runtime: 4766s
- Jobs: 8 total, 8 ok, 0 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260614_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-06-14 01:00:02,550 INFO Committed 2 file(s).
- 2. ✓ Code Auditor (5.5m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (7.1m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (19.4m)
  - Problems:
    - Prompts audited: 6.
    - Classification failures: 2.
    - Response failures: 1.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: BUILD_APK
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (0.9m)
  - Problems:
    - Transcript review found 7 issues: 4 critical, 2 low, 1 medium.
    - Stage 1 emitted an unsupported intent label before falling back to others.
    - Stage 1 emitted an unsupported intent label before falling back to others.
  - Fixes:
    - 2026-06-14 01:32:59,245 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (7 issues)
    - 2026-06-14 01:32:59,247 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 4 critical, 1 medium, 2...
- 7. ✓ Memory Janitor (46.4m)
  - Problems:
    - [0;93m2026-06-14 01:55:44.317197018 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-14 05:55:44 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-14 01:55:44.317246360 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-14 05:55:44 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-14 01:55:44.317262080 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-14 05:55:44 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 8 stale memories out of 20 checked. Stale memories make Ja...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-06-14 02:19:28,247 INFO Pushed successfully.

**Top follow-ups:**

- Constrain the Stage 1 model output to the canonical intent enum, or map 'web automation' explicitly to the intended supported class before logging it as unknown.
- Add strict enum validation at the classifier prompt/API layer and either remove non-canonical labels like 'force stage3' from examples or map them internally without warning.

## Executive Summary

- All stages exited cleanly.
- 6 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 1s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-14 01:00:02,550 INFO Committed 2 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 332s (5.5 min)

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

- Status: `ok`
- Duration: 1161s (19.4 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 6.
- Classification failures: 2.
- Response failures: 1.
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help with the payment, but I need one quick detail.[/ACK]

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
- Duration: 55s (0.9 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 7 issues: 4 critical, 2 low, 1 medium.
- Stage 1 emitted an unsupported intent label before falling back to others.
- Stage 1 emitted an unsupported intent label before falling back to others.
- Stage 3 received no conversation history for a context-dependent follow-up.
- Stage 3 turn took about 230 seconds.

### Improvements It Made

- 2026-06-14 01:32:59,245 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (7 issues)
- 2026-06-14 01:32:59,247 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 4 critical, 1 medium, 2 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Constrain the Stage 1 model output to the canonical intent enum, or map 'web automation' explicitly to the intended supported class before logging it as unknown.
- Add strict enum validation at the classifier prompt/API layer and either remove non-canonical labels like 'force stage3' from examples or map them internally without warning.
- Fix Stage 3 session history plumbing so sid_override sessions load prior turns before calling stream_message; add a regression test where a short follow-up depends on the previous user turn.
- Move short-term memory extraction off the blocking response path or enforce a much smaller timeout with best-effort failure; avoid sequential primary/gemini/claude retries during an active user response.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 2786s (46.4 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-06-14 01:55:44.317197018 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-14 05:55:44 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-14 01:55:44.317246360 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-14 05:55:44 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-14 01:55:44.317262080 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-14 05:55:44 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-14 01:55:44.475794224 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-14 05:55:44 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-14 01:55:44.475844534 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-14 05:55:44 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 8 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

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

- 2026-06-14 02:19:28,247 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
