# Most Recent Nightly Self-Improvement

- Run started: 2026-05-30 01:00:01
- Report generated: 2026-05-30 01:54:22
- Total runtime: 3260s
- Jobs: 8 total, 8 ok, 0 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260530_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-30 01:00:03,771 INFO Committed 3 file(s).
- 2. ✓ Code Auditor (8.1m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (6.4m)
  - Problems:
    - Dead files — review needed: 1.
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 1 flagged, 2 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (4.8m)
  - Problems:
    - Prompts audited: 8.
    - Classification failures: 4.
    - Response failures: 6.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (0.6m)
  - Problems:
    - Transcript review found 3 issues: 3 medium.
    - Extra voice turn was processed as a greeting between two substantive UI-change requests.
    - Stage 3 took nearly 8.3 minutes to complete a follow-up UI edit request.
  - Fixes:
    - 2026-05-30 01:19:59,943 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (3 issues)
    - 2026-05-30 01:19:59,944 INFO self_improve_log: recorded [medium] Transcript Review — Reviewing yesterday's conversations I spotted 3 medium issues. The most...
- 7. ✓ Memory Janitor (34.3m)
  - Problems:
    - [0;93m2026-05-30 01:39:15.601566771 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-30 05:39:15 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-30 01:39:15.601607698 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-30 05:39:15 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-30 01:39:15.601619999 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-30 05:39:15 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:memory.v1.conversation_manager:Session 'janitor-window-archival' closed and cleaned up.
    - INFO:memory_janitor:verify_code_memories: [3/4] e06d26a9-c53 — 2026-05-29: Committed and pushed education repo commit 2f3bd
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 2 stale memories out of 4 checked. Stale memories make Jan...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-05-30 01:54:22,008 INFO Pushed successfully.

**Top follow-ups:**

- Add client-side suppression for very short post-TTS captures unless wakeword or explicit user speech confidence is present, and log the recognized text for all voice sends so audits can verify whether the turn was real.
- For code-edit/project modification intents, route to a dedicated async job handler that immediately acknowledges, streams progress, and keeps the voice client from waiting on the full frontier-brain execution.

## Executive Summary

- All stages exited cleanly.
- 8 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 2s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-05-30 01:00:03,771 INFO Committed 3 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 488s (8.1 min)

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
- Duration: 385s (6.4 min)

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
- Duration: 287s (4.8 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 8.
- Classification failures: 4.
- Response failures: 6.
- **I'm currently you are using cold text as the third brain right** (read messages/stage3): Yes, Chieh. This session is Jane running through the text standing-brain path with memory injected. If you meant “Claude Text” specifically, I’d check
- **codex timing** (others/stage3): [ACK]Chieh, I need one quick clarification on what “codex timing” refers to.[/ACK]
- **also, for each question please write a hint section that's helpful fo the studen** (todo list/stage3): [ACK]Got it, Chieh — I’ll add helpful student-facing hints for each question; quick change.[/ACK]
- **you have access to my education software and I would like you to make some chang** (others/stage3): [ACK]Chieh, I can make the mobile student-view UI changes; I just need the target changes before editing.[/ACK]

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
- Duration: 33s (0.6 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 3 issues: 3 medium.
- Extra voice turn was processed as a greeting between two substantive UI-change requests.
- Stage 3 took nearly 8.3 minutes to complete a follow-up UI edit request.
- Voice follow-up appears truncated or garbled, but was still sent to Stage 3.

### Improvements It Made

- 2026-05-30 01:19:59,943 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (3 issues)
- 2026-05-30 01:19:59,944 INFO self_improve_log: recorded [medium] Transcript Review — Reviewing yesterday's conversations I spotted 3 medium issues. The most urgent was: Extra voice turn

### Follow-Up Fixes Recommended

- Add client-side suppression for very short post-TTS captures unless wakeword or explicit user speech confidence is present, and log the recognized text for all voice sends so audits can verify whether the turn was real.
- For code-edit/project modification intents, route to a dedicated async job handler that immediately acknowledges, streams progress, and keeps the voice client from waiting on the full frontier-brain execution.
- Add a voice-input quality gate for low-confidence, incomplete, or syntactically broken STT results. For code-edit follow-ups, ask a short clarification instead of sending garbled text to Stage 3.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 2060s (34.3 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-05-30 01:39:15.601566771 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-30 05:39:15 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-30 01:39:15.601607698 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-30 05:39:15 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-05-30 01:39:15.601619999 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-30 05:39:15 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-05-30 01:39:15.826016587 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-30 05:39:15 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-30 01:39:15.826055495 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-30 05:39:15 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:memory.v1.conversation_manager:Session 'janitor-window-archival' closed and cleaned up.
- INFO:memory_janitor:verify_code_memories: [3/4] e06d26a9-c53 — 2026-05-29: Committed and pushed education repo commit 2f3bd
- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 2 stale memories out of 4 checked. Stale memories make Jane give wrong answers about her own a

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

- 2026-05-30 01:54:22,008 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
