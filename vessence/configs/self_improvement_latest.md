# Most Recent Nightly Self-Improvement

- Run started: 2026-05-29 01:00:01
- Report generated: 2026-05-29 02:08:58
- Total runtime: 4136s
- Jobs: 8 total, 8 ok, 0 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260529_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-29 01:00:02,220 INFO Committed 2 file(s).
- 2. ✓ Code Auditor (7.6m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (6.5m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (4.8m)
  - Problems:
    - Prompts audited: 5.
    - Classification failures: 3.
    - Response failures: 4.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (0.5m)
  - Problems:
    - Transcript review found 2 issues: 1 critical, 1 medium.
    - Stage 3 request took nearly four minutes to complete, causing severe voice-assistant latency.
    - Follow-up turn was routed to Stage 3 without conversational context, so the assistant likely could not know which questions/module the user meant.
  - Fixes:
    - 2026-05-29 01:19:26,539 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (2 issues)
    - 2026-05-29 01:19:26,541 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 1 medium iss...
- 7. ✓ Memory Janitor (49.5m)
  - Problems:
    - [0;93m2026-05-29 01:47:50.423554975 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-29 05:47:50 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-29 01:47:50.423597167 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-29 05:47:50 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-29 01:47:50.423613846 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-29 05:47:50 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 8 stale memories out of 20 checked. Stale memories make Ja...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-05-29 02:08:58,264 INFO Pushed successfully.

**Top follow-ups:**

- Add a dedicated project-edit/task handler or Stage 3 async job mode that immediately acknowledges long-running edits, streams progress, and enforces a voice-safe timeout.
- Persist Stage 3 conversation history for the audit/session id or have Stage 3 set a pending_action for multi-turn project edits; pending_action_resolver should route short follow-ups like 'also...' back to the same task context before Stage 1.

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

- 2026-05-29 01:00:02,220 INFO Committed 2 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 457s (7.6 min)

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
- Duration: 387s (6.5 min)

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
- Duration: 288s (4.8 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 5.
- Classification failures: 3.
- Response failures: 4.
- **I'm currently you are using cold text as the third brain right** (read messages/stage3): Yes, Chieh. If “cold text” means Codex, then right now I’m Jane running through the Codex/standing-brain path, with Vessence memory and instructions l
- **codex timing** (others/stage3): [ACK]Chieh, I need one clarification on what “codex timing” refers to.[/ACK]
- **for the module span_A.q2, I would like you to not mention the augmented matrix s** (others/stage3): Chieh, I verified `span_A.q2`: the visible prompt already omits “augmented,” “Equivalently,” `A \alpha`, and the augmented matrix display. The remaini
- **also, for each question please write a hint section that's helpful fo the studen** (todo list/stage3): Got it, Chieh. Send me the questions or the file path, and I’ll add a concise `Hint` section under each one that guides the approach without giving aw

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
- Duration: 31s (0.5 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 2 issues: 1 critical, 1 medium.
- Stage 3 request took nearly four minutes to complete, causing severe voice-assistant latency.
- Follow-up turn was routed to Stage 3 without conversational context, so the assistant likely could not know which questions/module the user meant.

### Improvements It Made

- 2026-05-29 01:19:26,539 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (2 issues)
- 2026-05-29 01:19:26,541 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 1 medium issues. The most urgent was: Foll

### Follow-Up Fixes Recommended

- Add a dedicated project-edit/task handler or Stage 3 async job mode that immediately acknowledges long-running edits, streams progress, and enforces a voice-safe timeout.
- Persist Stage 3 conversation history for the audit/session id or have Stage 3 set a pending_action for multi-turn project edits; pending_action_resolver should route short follow-ups like 'also...' back to the same task context before Stage 1.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 2970s (49.5 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-05-29 01:47:50.423554975 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-29 05:47:50 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-29 01:47:50.423597167 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-29 05:47:50 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-05-29 01:47:50.423613846 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-29 05:47:50 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-05-29 01:47:50.625993543 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-29 05:47:50 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-29 01:47:50.626033626 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-29 05:47:50 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 8 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

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

- 2026-05-29 02:08:58,264 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
