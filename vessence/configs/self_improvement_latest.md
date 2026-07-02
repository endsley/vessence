# Most Recent Nightly Self-Improvement

- Run started: 2026-07-01 01:00:01
- Report generated: 2026-07-01 02:39:54
- Total runtime: 5992s
- Jobs: 8 total, 7 ok, 1 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260701_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-07-01 01:00:03,408 INFO Committed 48 file(s).
- 2. ✓ Code Auditor (5.7m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (7.0m)
  - Problems:
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 11 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 2 dead funcs, 11 dup groups
- 4. ⏱ Pipeline Audit (30 prompts) (20.0m)
  - Problems:
    - Prompts audited: 6.
    - Classification failures: 3.
    - Response failures: 4.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md claims iterative_refactor_scheduler.py is active but no matching cron entry exists
- 6. ✓ Transcript Quality Review (0.9m)
  - Problems:
    - Transcript review found 6 issues: 3 critical, 1 low, 2 medium.
    - Stage 3 ran far beyond an interactive response window and only finished after about 13 minutes.
    - Stage 3 response was cancelled after the client disconnected, so the task likely produced no usable final answer.
  - Fixes:
    - 2026-07-01 01:33:33,947 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (6 issues)
    - 2026-07-01 01:33:33,948 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 3 critical, 2 medium, 1...
- 7. ✓ Memory Janitor (66.3m)
  - Problems:
    - [0;93m2026-07-01 02:22:36.143412125 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-01 06:22:36 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-07-01 02:22:36.143461044 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-01 06:22:36 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-07-01 02:22:36.143477070 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-01 06:22:36 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 11 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-07-01 02:39:52,058 INFO Committed 7 file(s).
    - 2026-07-01 02:39:53,856 INFO Pushed successfully.

**Top follow-ups:**

- For large coding tasks, route to a background job mode with progress events instead of a normal stream, and make memory extraction non-blocking with a configured working fallback or suppressed retry noise.
- Detach long-running Stage 3 coding jobs from the client stream, persist job state/results, and let the client reconnect or poll instead of cancelling the brain task on disconnect.

## Executive Summary

- 1 stage(s) need attention because they timed out or exited non-zero.
- 7 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 1s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-07-01 01:00:03,408 INFO Committed 48 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 339s (5.7 min)

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
- Duration: 417s (7.0 min)

### What It Did

- Scanned the codebase for dead files, unreferenced functions, and duplicate function bodies.

### Problems It Found

- Possibly-dead functions: 2.
- Duplicate function bodies: 11 groups.

### Improvements It Made

- [dead-code] Done — 0 auto-deleted, 0 flagged, 2 dead funcs, 11 dup groups

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
- Classification failures: 3.
- Response failures: 4.
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help, but I need to know which payment you mean.[/ACK]
- **right now, you are using the same codex process for each prompt instead of spawn** (others/stage3): [ACK]Chieh, I’ll verify the stage 3 brain runtime path in the code before answering; this should be quick.[/ACK]I’m searching the runtime entrypoints
- **use the source code as your guide** (todo list/stage3): Understood, Chieh. I’ll treat the source code as the ground truth and verify behavior against it before making claims.
- **currently, the waterlily site is web only meant for browsers on laptops and comp** (others/stage3): [ACK]Chieh, I’ll inspect Waterlily and the education project mobile patterns first, then implement responsive mobile UIs across the site; this will ta

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

- CRON_JOBS.md claims iterative_refactor_scheduler.py is active but no matching cron entry exists

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/doc_drift_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_doc_drift_auditor.log

## Stage 6: Transcript Quality Review

- Status: `ok`
- Duration: 52s (0.9 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 6 issues: 3 critical, 1 low, 2 medium.
- Stage 3 ran far beyond an interactive response window and only finished after about 13 minutes.
- Stage 3 response was cancelled after the client disconnected, so the task likely produced no usable final answer.
- Stage 3 job was cancelled after a long run when the client disconnected.
- Stage 3 stream failed after about two hours and returned no final response payload.

### Improvements It Made

- 2026-07-01 01:33:33,947 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (6 issues)
- 2026-07-01 01:33:33,948 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 3 critical, 2 medium, 1 minor issues. The most urgent

### Follow-Up Fixes Recommended

- For large coding tasks, route to a background job mode with progress events instead of a normal stream, and make memory extraction non-blocking with a configured working fallback or suppressed retry noise.
- Detach long-running Stage 3 coding jobs from the client stream, persist job state/results, and let the client reconnect or poll instead of cancelling the brain task on disconnect.
- Run queued refactor tasks through a durable background worker rather than a streaming request path tied to client lifetime.
- Add a hard per-job timeout with checkpointed progress and an explicit failure response; surface the underlying exception in structured logs so the root runtime error can be diagnosed.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 3977s (66.3 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-07-01 02:22:36.143412125 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-01 06:22:36 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-07-01 02:22:36.143461044 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-01 06:22:36 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-07-01 02:22:36.143477070 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-01 06:22:36 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-07-01 02:22:36.332283875 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-01 06:22:36 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-07-01 02:22:36.332334668 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-01 06:22:36 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 11 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

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

- 2026-07-01 02:39:52,058 INFO Committed 7 file(s).
- 2026-07-01 02:39:53,856 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
