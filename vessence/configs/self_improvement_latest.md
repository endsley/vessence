# Most Recent Nightly Self-Improvement

- Run started: 2026-06-10 01:00:01
- Report generated: 2026-06-10 02:40:04
- Total runtime: 6002s
- Jobs: 8 total, 8 ok, 0 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260610_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-06-10 01:00:01,939 INFO Committed 2 file(s).
- 2. ✓ Code Auditor (7.6m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (5.9m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (16.3m)
  - Problems:
    - Prompts audited: 6.
    - Classification failures: 2.
    - Response failures: 3.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: BUILD_APK
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (0.9m)
  - Problems:
    - Transcript review found 8 issues: 1 critical, 4 low, 3 medium.
    - Stage 1 emitted an unsupported intent label before coercing to others.
    - Stage 3 did not receive conversation history for a follow-up question.
  - Fixes:
    - 2026-06-10 01:30:45,820 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (8 issues)
    - 2026-06-10 01:30:45,821 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 3 medium, 4...
- 7. ✓ Memory Janitor (69.2m)
  - Problems:
    - [0;93m2026-06-10 02:19:01.235390511 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-10 06:19:01 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-10 02:19:01.235434960 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-10 06:19:01 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-10 02:19:01.235450186 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-10 06:19:01 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 13 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-06-10 02:40:02,035 INFO Committed 7 file(s).
    - 2026-06-10 02:40:03,618 INFO Pushed successfully.

**Top follow-ups:**

- Constrain the classifier prompt/output parser to the exact enum, or map 'web automation' and similar project/code requests explicitly to others without warning.
- Fix session history lookup/persistence for sid_override sessions so stream_message receives prior turns for the same conversation id.

## Executive Summary

- All stages exited cleanly.
- 7 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-10 01:00:01,939 INFO Committed 2 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 456s (7.6 min)

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
- Duration: 355s (5.9 min)

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
- Duration: 977s (16.3 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 6.
- Classification failures: 2.
- Response failures: 3.
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help with the payment once I know which bill this is.[/ACK]
- **right now, you are using the same codex process for each prompt instead of spawn** (others/stage3): [ACK]Chieh, I’ll verify the Stage 3 brain process model from the runtime code quickly.[/ACK]I found two relevant paths: the v2 Stage 3 wrapper delegat
- **currently, the waterlily site is web only meant for browsers on laptops and comp** (others/stage3): [ACK]Chieh, I’ll compare the education project’s mobile patterns against Waterlily and then implement responsive mobile UIs across the site; this will

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
- Duration: 54s (0.9 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 8 issues: 1 critical, 4 low, 3 medium.
- Stage 1 emitted an unsupported intent label before coercing to others.
- Stage 3 did not receive conversation history for a follow-up question.
- Stage 1 emitted an unsupported intent label before coercing to others.
- Stage 3 did not receive prior conversation context for an explicitly contextual instruction.

### Improvements It Made

- 2026-06-10 01:30:45,820 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (8 issues)
- 2026-06-10 01:30:45,821 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 3 medium, 4 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Constrain the classifier prompt/output parser to the exact enum, or map 'web automation' and similar project/code requests explicitly to others without warning.
- Fix session history lookup/persistence for sid_override sessions so stream_message receives prior turns for the same conversation id.
- Update the classifier prompt/parser to reject non-enum labels, and normalize meta-routing labels like 'force stage3' to others internally.
- Ensure conversation history is appended before each Stage 3 call and retrieved by session id, including web/non-voice audit sessions.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 4155s (69.2 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-06-10 02:19:01.235390511 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-10 06:19:01 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-10 02:19:01.235434960 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-10 06:19:01 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-10 02:19:01.235450186 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-10 06:19:01 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-10 02:19:01.426297160 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-10 06:19:01 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-10 02:19:01.426338912 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-10 06:19:01 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

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

- 2026-06-10 02:40:02,035 INFO Committed 7 file(s).
- 2026-06-10 02:40:03,618 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
