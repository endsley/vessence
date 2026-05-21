# Most Recent Nightly Self-Improvement

- Run started: 2026-05-21 01:00:01
- Report generated: 2026-05-21 02:12:51
- Total runtime: 4368s
- Jobs: 8 total, 6 ok, 1 timeout, 1 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260521_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-21 01:00:02,808 INFO Committed 15 file(s).
- 2. ✗ Code Auditor (6.2m)
  - Problems:
    - 2026-05-21 01:06:12,942 [WARNING] All fix attempts exhausted, reverting
- 3. ✓ Dead Code Auditor (6.6m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (0.5m)
  - Problems:
    - Prompts audited: 7.
    - Classification failures: 2.
    - Response failures: 7.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (1.1m)
  - Problems:
    - Transcript review found 8 issues: 7 critical, 1 medium.
    - Follow-up reply was not routed through pending_action_resolver and then produced no response.
    - Complex memory question escalated correctly but Stage 3 failed with no response.
  - Fixes:
    - 2026-05-21 01:14:24,140 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (8 issues)
    - 2026-05-21 01:14:24,141 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 7 critical, 1 medium iss...
- 7. ✓ Memory Janitor (56.4m)
  - Problems:
    - [0;93m2026-05-21 01:53:00.649194051 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-21 05:53:00 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-21 01:53:00.649211020 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-21 05:53:00 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-21 01:53:00.854742318 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-21 05:53:00 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 17 stale memories out of 20 checked. Stale memories make J...
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-05-21 02:10:52,096 INFO Committed 6 file(s).

**Top follow-ups:**

- Persist pending_action state across the prior turn and add resolver entry/exit logging before Stage 1. If resolver state is absent for short affirmative/parameter replies, route to a clarification fallback instead of generic Stage 3. Also make stage3_escalate return a user-visible fallback when brain streaming errors.
- Fix the OpenAI brain streaming failure path and add exception detail to jane.proxy logs. stage3_escalate should emit a fallback response instead of ending the stream empty.

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

- 2026-05-21 01:00:02,808 INFO Committed 15 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `exit-1`
- Duration: 370s (6.2 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- Job ended with status `exit-1`.
- 2026-05-21 01:06:12,942 [WARNING] All fix attempts exhausted, reverting

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

- Possibly-dead functions: 1.
- Duplicate function bodies: 10 groups.

### Improvements It Made

- [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups

### Evidence Files

- /home/chieh/ambient/vessence/configs/dead_code_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_dead_code_auditor.log

## Stage 4: Pipeline Audit (30 prompts)

- Status: `ok`
- Duration: 32s (0.5 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 7.
- Classification failures: 2.
- Response failures: 7.
- **yes those articles and maybe just two days** (others/stage3):
- **currently how does your short-term memory work** (others/stage3):
- **how about** (greeting/stage3):
- **it seems to me that you are no longing making any sounds when speech to text is ** (others/stage3):

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
- Duration: 63s (1.1 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 8 issues: 7 critical, 1 medium.
- Follow-up reply was not routed through pending_action_resolver and then produced no response.
- Complex memory question escalated correctly but Stage 3 failed with no response.
- Prompt-injection-looking text was misclassified as greeting and loaded the greeting class protocol.
- Audio/STT diagnostic request escalated correctly but Stage 3 failed with no response.

### Improvements It Made

- 2026-05-21 01:14:24,140 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (8 issues)
- 2026-05-21 01:14:24,141 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 7 critical, 1 medium issues. The most urgent was: Foll

### Follow-Up Fixes Recommended

- Persist pending_action state across the prior turn and add resolver entry/exit logging before Stage 1. If resolver state is absent for short affirmative/parameter replies, route to a clarification fallback instead of generic Stage 3. Also make stage3_escalate return a user-visible fallback when brain streaming errors.
- Fix the OpenAI brain streaming failure path and add exception detail to jane.proxy logs. stage3_escalate should emit a fallback response instead of ending the stream empty.
- Add a pre-classification sanitizer/rule that treats literal '<class_protocol' and similar runtime-instruction tags in user text as untrusted content and blocks class protocol loading. Fix greeting handler to always return the expected response schema.
- Repair Stage 3 streaming and include Android voice_flow/tool_handler diagnostics in the audit log bundle for voice-client issues. Add a deterministic diagnostics handler for STT/audio complaints if this is a common support intent.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 3386s (56.4 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-05-21 01:53:00.649194051 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-21 05:53:00 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-05-21 01:53:00.649211020 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-21 05:53:00 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-05-21 01:53:00.854742318 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-21 05:53:00 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-21 01:53:00.854800631 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-21 05:53:00 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-05-21 01:53:00.854813047 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-21 05:53:00 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 17 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_janitor_memory.log

## Stage 8: Auto-Commit + Push (post)

- Status: `timeout`
- Duration: 120s (2.0 min)

### What It Did

- Committed and pushed generated fixes and reports after the run.

### Problems It Found

- Job ended with status `timeout`.

### Improvements It Made

- 2026-05-21 02:10:52,096 INFO Committed 6 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
