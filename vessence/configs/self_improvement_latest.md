# Most Recent Nightly Self-Improvement

- Run started: 2026-06-09 01:00:01
- Report generated: 2026-06-09 03:20:01
- Total runtime: 8399s
- Jobs: 8 total, 7 ok, 1 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260609_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-06-09 01:00:01,739 INFO Committed 2 file(s).
- 2. ✓ Code Auditor (12.1m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (6.1m)
  - Problems:
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 2 dead funcs, 10 dup groups
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
- 6. ✓ Transcript Quality Review (1.1m)
  - Problems:
    - Transcript review found 9 issues: 1 critical, 3 low, 5 medium.
    - Classifier produced an out-of-schema intent label before falling back to others.
    - Stage 3 received no conversation history for a contextual follow-up question.
  - Fixes:
    - 2026-06-09 01:39:22,300 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (9 issues)
    - 2026-06-09 01:39:22,301 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 5 medium, 3...
- 7. ✓ Memory Janitor (100.6m)
  - Problems:
    - [0;93m2026-06-09 02:55:05.389114106 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-09 06:55:05 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-09 02:55:05.389167529 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-09 06:55:05 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-09 02:55:05.389183842 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-09 06:55:05 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 17 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-06-09 03:20:01,312 INFO Pushed successfully.

**Top follow-ups:**

- Constrain the Stage 1 classifier output to the allowed enum at decode/parse time, and add an explicit mapping or prompt examples for project/codebase-access questions to route directly to Stage 3 without warning.
- Persist and pass recent conversation history for the sid/audit session into stream_message, or ensure sid_override resolves to the existing session history before Stage 3 invocation.

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

- 2026-06-09 01:00:01,739 INFO Committed 2 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 726s (12.1 min)

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
- Duration: 368s (6.1 min)

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
- Duration: 65s (1.1 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 9 issues: 1 critical, 3 low, 5 medium.
- Classifier produced an out-of-schema intent label before falling back to others.
- Stage 3 received no conversation history for a contextual follow-up question.
- Classifier produced an out-of-schema intent label before falling back to others.
- Stage 3 received no conversation history for an instruction that only makes sense as a follow-up.

### Improvements It Made

- 2026-06-09 01:39:22,300 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (9 issues)
- 2026-06-09 01:39:22,301 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 5 medium, 3 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Constrain the Stage 1 classifier output to the allowed enum at decode/parse time, and add an explicit mapping or prompt examples for project/codebase-access questions to route directly to Stage 3 without warning.
- Persist and pass recent conversation history for the sid/audit session into stream_message, or ensure sid_override resolves to the existing session history before Stage 3 invocation.
- Make the classifier parser reject or repair labels to the canonical enum, and update the classifier prompt so meta/system questions map to others or a supported Stage 3 escalation category.
- Attach session history to Stage 3 calls for the same conversation id, especially when sid_override=True, and add a regression test for short follow-up commands after a long Stage 3 answer.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 6037s (100.6 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-06-09 02:55:05.389114106 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-09 06:55:05 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-09 02:55:05.389167529 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-09 06:55:05 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-09 02:55:05.389183842 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-09 06:55:05 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-09 02:55:05.586718926 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-09 06:55:05 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-09 02:55:05.586758541 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-09 06:55:05 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 17 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

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

- 2026-06-09 03:20:01,312 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
