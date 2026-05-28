# Most Recent Nightly Self-Improvement

- Run started: 2026-05-27 01:00:01
- Report generated: 2026-05-27 03:01:23
- Total runtime: 7282s
- Jobs: 8 total, 8 ok, 0 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260527_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-27 01:00:01,499 INFO Committed 3 file(s).
- 2. ✓ Code Auditor (11.8m)
  - Problems:
    - 2026-05-27 01:10:01,641 [WARNING] Primary LLM failed: CLI timed out after 600s... Attempting fallback.
- 3. ✓ Dead Code Auditor (6.1m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (17.2m)
  - Problems:
    - Prompts audited: 10.
    - Classification failures: 3.
    - Response failures: 2.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (2.8m)
  - Problems:
    - Transcript review found 5 issues: 1 critical, 1 low, 3 medium.
    - Stage 3 follow-up context was not preserved for the audit web session.
    - Stage 1 emitted an invalid intent label before falling back to others.
  - Fixes:
    - 2026-05-27 01:38:02,756 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (5 issues)
    - 2026-05-27 01:38:02,758 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 3 medium, 1...
- 7. ✓ Memory Janitor (83.3m)
  - Problems:
    - [0;93m2026-05-27 02:31:27.134994177 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-27 06:31:27 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-27 02:31:27.135038263 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-27 06:31:27 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-27 02:31:27.135051085 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-27 06:31:27 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 14 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-05-27 03:01:23,319 INFO Pushed successfully.

**Top follow-ups:**

- Make sid_override sessions use the same persistent conversation-history key as normal sessions, and add a regression test that repeated turns on one sid produce history > 0.
- Constrain Stage 1 output to a strict enum or normalize escalation synonyms such as 'force stage3' to the supported escalation/others path before logging a warning.

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

- 2026-05-27 01:00:01,499 INFO Committed 3 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 710s (11.8 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- 2026-05-27 01:10:01,641 [WARNING] Primary LLM failed: CLI timed out after 600s... Attempting fallback.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 366s (6.1 min)

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
- Duration: 1034s (17.2 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 10.
- Classification failures: 3.
- Response failures: 2.
- **codex timing** (others/stage3): [ACK]Chieh, I need one clarification on what Codex timing you mean.[/ACK]
- **also, for each question please write a hint section that's helpful fo the studen** (todo list/stage3): [ACK]Chieh, I can add hint sections, but I need the target questions or file first.[/ACK]

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
- Duration: 169s (2.8 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 5 issues: 1 critical, 1 low, 3 medium.
- Stage 3 follow-up context was not preserved for the audit web session.
- Stage 1 emitted an invalid intent label before falling back to others.
- Android voice turns were treated as non-voice by the server Stage 3 path.
- Android/background requests hit API rate limits immediately after the voice interaction.

### Improvements It Made

- 2026-05-27 01:38:02,756 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (5 issues)
- 2026-05-27 01:38:02,758 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 3 medium, 1 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Make sid_override sessions use the same persistent conversation-history key as normal sessions, and add a regression test that repeated turns on one sid produce history > 0.
- Constrain Stage 1 output to a strict enum or normalize escalation synonyms such as 'force stage3' to the supported escalation/others path before logging a warning.
- Propagate the Android fromVoice flag into the backend pipeline voice boolean and add an integration test covering Android STT-to-Stage3 routing.
- Add client-side request coalescing, caching, and exponential backoff for briefing assets and announcements; tune route-specific rate limits so background media fetches do not interfere with assistant use.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 4998s (83.3 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-05-27 02:31:27.134994177 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-27 06:31:27 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-27 02:31:27.135038263 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-27 06:31:27 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-05-27 02:31:27.135051085 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-27 06:31:27 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-05-27 02:31:27.317471068 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-27 06:31:27 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-27 02:31:27.317526527 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-27 06:31:27 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 14 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

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

- 2026-05-27 03:01:23,319 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
