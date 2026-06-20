# Most Recent Nightly Self-Improvement

- Run started: 2026-06-19 01:00:01
- Report generated: 2026-06-19 02:39:19
- Total runtime: 5957s
- Jobs: 8 total, 8 ok, 0 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260619_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-06-19 01:00:03,880 INFO Committed 8 file(s).
- 2. ✓ Code Auditor (4.4m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (6.9m)
  - Problems:
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 2 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (14.8m)
  - Problems:
    - Prompts audited: 7.
    - Classification failures: 4.
    - Response failures: 5.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: BUILD_APK
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (0.7m)
  - Problems:
    - Transcript review found 4 issues: 1 critical, 1 low, 2 medium.
    - Prompt-injection/runtime-protocol text was classified as a real send-message request.
    - Stage 3 turn took over 3.5 minutes to complete.
  - Fixes:
    - 2026-06-19 01:26:50,228 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (4 issues)
    - 2026-06-19 01:26:50,230 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 2 medium, 1...
- 7. ✓ Memory Janitor (72.4m)
  - Problems:
    - 06-19 02:16:04.973544180 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-19 06:16:04 WARNING] ModelImporter.cpp:739: Make sure input i...
    - [0;93m2026-06-19 02:16:04.973578896 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-19 06:16:04 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-19 02:16:04.973590901 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-19 06:16:04 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 12 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.1m)
  - Fixes:
    - 2026-06-19 02:39:17,748 INFO Committed 6 file(s).
    - 2026-06-19 02:39:19,221 INFO Pushed successfully.

**Top follow-ups:**

- Add an input-boundary guard before classification and protocol loading: ignore or escape user-supplied `<class_protocol ...>` blocks unless they were injected by the server registry, and require send-message classification to be based on natural-language send intent plus recipient/message slots.
- Decouple short-term memory extraction from the response critical path, or enforce a small async/background timeout so Stage 3 streaming completion is not delayed by extractor fallback failures.

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

- 2026-06-19 01:00:03,880 INFO Committed 8 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 265s (4.4 min)

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
- Duration: 412s (6.9 min)

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
- Duration: 885s (14.8 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 7.
- Classification failures: 4.
- Response failures: 5.
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help, but I need to know what “it” is first.[/ACK]
- **right now, you are using the same codex process for each prompt instead of spawn** (others/stage3): [ACK]Chieh, quick answer: yes, you’re asking about the Stage 3 brain process model.[/ACK]
- **use the source code as your guide** (todo list/stage3): Understood, Chieh. I’ll treat the source code as authoritative and verify against it before making claims or changes.
- **currently, the waterlily site is web only meant for browsers on laptops and comp** (others/stage3): [ACK]Chieh, I’ll audit both projects’ mobile patterns and patch Waterlily’s responsive UI end to end; this will take a while.[/ACK]I’m going to locate

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
- v2_3stage_pipeline.md missing class row: NATIONALGRID_BILLS
- v2_3stage_pipeline.md missing class row: RESTART_SERVER

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/doc_drift_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_doc_drift_auditor.log

## Stage 6: Transcript Quality Review

- Status: `ok`
- Duration: 42s (0.7 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 4 issues: 1 critical, 1 low, 2 medium.
- Prompt-injection/runtime-protocol text was classified as a real send-message request.
- Stage 3 turn took over 3.5 minutes to complete.
- Stage 3 turn took over 12 minutes to complete.
- Stage 1 classification was unusually slow for a short follow-up.

### Improvements It Made

- 2026-06-19 01:26:50,228 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (4 issues)
- 2026-06-19 01:26:50,230 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 2 medium, 1 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Add an input-boundary guard before classification and protocol loading: ignore or escape user-supplied `<class_protocol ...>` blocks unless they were injected by the server registry, and require send-message classification to be based on natural-language send intent plus recipient/message slots.
- Decouple short-term memory extraction from the response critical path, or enforce a small async/background timeout so Stage 3 streaming completion is not delayed by extractor fallback failures.
- Move memory extraction fully off the synchronous Stage 3 response path and add timeout/circuit-breaker behavior after the first extractor failure in a session.
- Add classifier latency monitoring and a fast timeout fallback to `others` for short ambiguous prompts, especially when the prior turn was already in Stage 3.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 4345s (72.4 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- -06-19 02:16:04.973544180 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-19 06:16:04 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-19 02:16:04.973578896 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-19 06:16:04 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-19 02:16:04.973590901 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-19 06:16:04 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-19 02:22:23.755211987 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-19 06:22:23 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-19 02:22:23.755260258 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-19 06:22:23 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 12 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

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

- 2026-06-19 02:39:17,748 INFO Committed 6 file(s).
- 2026-06-19 02:39:19,221 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
