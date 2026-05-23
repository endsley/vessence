# Most Recent Nightly Self-Improvement

- Run started: 2026-05-22 01:00:01
- Report generated: 2026-05-22 02:38:48
- Total runtime: 5926s
- Jobs: 8 total, 8 ok, 0 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260522_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-22 01:00:03,879 INFO Committed 12 file(s).
- 2. ✓ Code Auditor (5.0m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (6.7m)
  - Problems:
    - Dead files — review needed: 1.
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 1 flagged, 2 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (11.8m)
  - Problems:
    - Prompts audited: 11.
    - Classification failures: 3.
    - Response failures: 7.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (2.2m)
  - Problems:
    - Transcript review found 12 issues: 9 critical, 3 medium.
    - Follow-up reply was not routed by the pending_action_resolver and then produced no final response.
    - Stage 3 failed for a normal informational request and returned no answer.
  - Fixes:
    - 2026-05-22 01:25:52,385 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (12 issues)
    - 2026-05-22 01:25:52,386 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 9 critical, 3 medium iss...
- 7. ✓ Memory Janitor (72.8m)
  - Problems:
    - [0;93m2026-05-22 02:21:09.971899464 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-22 06:21:09 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-22 02:21:09.971956198 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-22 06:21:09 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-22 02:21:09.971970477 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-22 06:21:09 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 19 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.1m)
  - Fixes:
    - 2026-05-22 02:38:44,329 INFO Committed 8 file(s).
    - 2026-05-22 02:38:48,461 INFO Pushed successfully.

**Top follow-ups:**

- Persist pending_action state by session before the next user turn and add a resolver miss diagnostic when a pending action is absent or expired; also make Stage 3 return a user-visible fallback on stream failure.
- Fix the OpenAI streaming backend exception path and include exception type/stack in jane.proxy logs; return a deterministic apology/error response when Stage 3 fails.

## Executive Summary

- All stages exited cleanly.
- 7 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 2s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-05-22 01:00:03,879 INFO Committed 12 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 300s (5.0 min)

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
- Duration: 403s (6.7 min)

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

- Status: `ok`
- Duration: 708s (11.8 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 11.
- Classification failures: 3.
- Response failures: 7.
- **yes those articles and maybe just two days** (others/stage3): [ACK]Chieh, I’m missing the specific article context, so this should be quick once you point me at it.[/ACK]
- **currently how does your short-term memory work** (others/stage3): [ACK]Chieh, quick explanation of my current memory model.[/ACK]
- **how about** (greeting/stage3): Chieh, what are you proposing? Give me the option or wording you want me to evaluate. [[AWAITING:what_option
- **it seems to me that you are no longing making any sounds when speech to text is ** (others/stage3): Chieh, I found the issue and patched it.

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
- Duration: 135s (2.2 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 12 issues: 9 critical, 3 medium.
- Follow-up reply was not routed by the pending_action_resolver and then produced no final response.
- Stage 3 failed for a normal informational request and returned no answer.
- User-supplied class_protocol markup was treated as a real greeting signal, and the greeting handler returned an invalid shape.
- Stage 3 failed for a bug report about Android speech relaunch audio.

### Improvements It Made

- 2026-05-22 01:25:52,385 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (12 issues)
- 2026-05-22 01:25:52,386 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 9 critical, 3 medium issues. The most urgent was: Foll

### Follow-Up Fixes Recommended

- Persist pending_action state by session before the next user turn and add a resolver miss diagnostic when a pending action is absent or expired; also make Stage 3 return a user-visible fallback on stream failure.
- Fix the OpenAI streaming backend exception path and include exception type/stack in jane.proxy logs; return a deterministic apology/error response when Stage 3 fails.
- Escape or strip reserved runtime-control tags from user text before classification, reject user-originated class_protocol envelopes, and make the greeting handler always return the normalized Stage2 response schema.
- Repair Stage 3 streaming failure handling and add a fallback response path so diagnostic requests do not disappear when the brain backend errors.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 4367s (72.8 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-05-22 02:21:09.971899464 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-22 06:21:09 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-22 02:21:09.971956198 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-22 06:21:09 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-05-22 02:21:09.971970477 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-22 06:21:09 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-05-22 02:21:10.160273017 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-22 06:21:10 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-22 02:21:10.160314567 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-22 06:21:10 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 19 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_janitor_memory.log

## Stage 8: Auto-Commit + Push (post)

- Status: `ok`
- Duration: 8s (0.1 min)

### What It Did

- Committed and pushed generated fixes and reports after the run.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-05-22 02:38:44,329 INFO Committed 8 file(s).
- 2026-05-22 02:38:48,461 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
