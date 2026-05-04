# Most Recent Nightly Self-Improvement

- Run started: 2026-05-03 01:00:01
- Report generated: 2026-05-03 02:13:00
- Total runtime: 4378s
- Jobs: 8 total, 6 ok, 2 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260503_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-03 01:00:02,575 INFO Committed 6 file(s).
- 2. ✓ Code Auditor (0.0m)
  - Problems:
    - 2026-05-03 01:00:02,680 [WARNING] Working tree has uncommitted changes — skipping audit.
- 3. ✓ Dead Code Auditor (6.0m)
  - Problems:
    - Dead files — review needed: 1.
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 1 flagged, 2 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (0.9m)
  - Problems:
    - Prompts audited: 12.
    - Classification failures: 5.
    - Response failures: 11.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (4.0m)
  - Problems:
    - Transcript review found 19 issues: 14 critical, 1 low, 4 medium.
    - Stage 3 failed and the user received no response
    - Stage 3 failed and the user received no response
  - Fixes:
    - 2026-05-03 01:10:58,646 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (19 issues)
    - 2026-05-03 01:10:58,647 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 14 critical, 4 medium, 1...
- 7. ⏱ Memory Janitor (60.0m)
  - Problems:
    - 05-03 01:46:53.530595477 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-03 05:46:53 WARNING] ModelImporter.cpp:739: Make sure input i...
    - [0;93m2026-05-03 01:46:53.530650216 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-03 05:46:53 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-03 01:46:53.530666819 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-03 05:46:53 WARNING] ModelImporter.cpp:739: Make...
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-05-03 02:11:09,271 INFO Committed 6 file(s).

**Top follow-ups:**

- Add retry and fallback handling in `jane.proxy` for Stage 3 stream failures, and return a user-visible apology/error response when the stream ends without a final payload.
- Add retry and fallback handling in `jane.proxy` for Stage 3 stream failures, and return a user-visible apology/error response when the stream ends without a final payload.

## Executive Summary

- 2 stage(s) need attention because they timed out or exited non-zero.
- 5 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 1s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-05-03 01:00:02,575 INFO Committed 6 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- 2026-05-03 01:00:02,680 [WARNING] Working tree has uncommitted changes — skipping audit.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 361s (6.0 min)

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
- Duration: 54s (0.9 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 12.
- Classification failures: 5.
- Response failures: 11.
- **can you do a search for the Uber website for mCP to work with potentially my AI ** (others/stage3):
- **what I want to know is if we can use Jane to order Uber using this mCP** (others/stage3):
- **so basically Uber has an API just not mCP to order rides** (others/stage3):
- **well I sure my article with the app doesn't** (others/stage3):

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

- v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/doc_drift_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_doc_drift_auditor.log

## Stage 6: Transcript Quality Review

- Status: `ok`
- Duration: 240s (4.0 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 19 issues: 14 critical, 1 low, 4 medium.
- Stage 3 failed and the user received no response
- Stage 3 failed and the user received no response
- Follow-up flow degraded because Stage 3 was invoked with no conversation history
- Stage 3 failed and the user received no response

### Improvements It Made

- 2026-05-03 01:10:58,646 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (19 issues)
- 2026-05-03 01:10:58,647 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 14 critical, 4 medium, 1 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Add retry and fallback handling in `jane.proxy` for Stage 3 stream failures, and return a user-visible apology/error response when the stream ends without a final payload.
- Add retry and fallback handling in `jane.proxy` for Stage 3 stream failures, and return a user-visible apology/error response when the stream ends without a final payload.
- Preserve recent conversation history when escalating repeated turns in the same session, and log/alert when a non-initial Stage 3 turn is sent with `history=0`.
- Add retry and fallback handling in `jane.proxy` for Stage 3 stream failures, and return a user-visible apology/error response when the stream ends without a final payload.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `timeout`
- Duration: 3600s (60.0 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- Job ended with status `timeout`.
- 05-03 01:46:53.530595477 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-03 05:46:53 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-03 01:46:53.530650216 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-03 05:46:53 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-05-03 01:46:53.530666819 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-03 05:46:53 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-05-03 01:46:53.735098259 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-03 05:46:53 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-03 01:46:53.735144809 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-03 05:46:53 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

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

- 2026-05-03 02:11:09,271 INFO Committed 6 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
