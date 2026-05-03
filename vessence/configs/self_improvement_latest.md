# Most Recent Nightly Self-Improvement

- Run started: 2026-05-02 01:00:01
- Report generated: 2026-05-02 02:08:29
- Total runtime: 4107s
- Jobs: 8 total, 6 ok, 2 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260502_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-02 01:00:01,600 INFO Committed 7 file(s).
- 2. ✓ Code Auditor (0.0m)
  - Problems:
    - 2026-05-02 01:00:01,731 [WARNING] Working tree has uncommitted changes — skipping audit.
- 3. ✓ Dead Code Auditor (5.7m)
  - Problems:
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 0 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (0.7m)
  - Problems:
    - Prompts audited: 12.
    - Classification failures: 4.
    - Response failures: 11.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (0.0m)
  - Problems:
    - Transcript review found 7 issues: 5 critical, 2 medium.
    - Internal class protocol text was recorded as a user turn.
    - Delete-email turn was replaced in the transcript by internal protocol content.
- 7. ⏱ Memory Janitor (60.0m)
  - Problems:
    - der.h:92 log] [2026-05-02 05:38:15 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
    - [0;93m2026-05-02 01:38:15.567075388 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-02 05:38:15 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-05-02 01:38:15.760427453 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-02 05:38:15 WARNING] ModelImporter.cpp:739: Make...
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-05-02 02:06:32,720 INFO Committed 4 file(s).

**Top follow-ups:**

- Keep class protocol content in a non-user/system channel only, and exclude synthetic protocol messages from transcript persistence and future conversation history.
- Separate protocol injection from user-message persistence. Add a guard in transcript/history writing that drops messages tagged as class protocol or synthetic prompt material.

## Executive Summary

- 2 stage(s) need attention because they timed out or exited non-zero.
- 3 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-05-02 01:00:01,600 INFO Committed 7 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- 2026-05-02 01:00:01,731 [WARNING] Working tree has uncommitted changes — skipping audit.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 341s (5.7 min)

### What It Did

- Scanned the codebase for dead files, unreferenced functions, and duplicate function bodies.

### Problems It Found

- Duplicate function bodies: 10 groups.

### Improvements It Made

- [dead-code] Done — 0 auto-deleted, 0 flagged, 0 dead funcs, 10 dup groups

### Evidence Files

- /home/chieh/ambient/vessence/configs/dead_code_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_dead_code_auditor.log

## Stage 4: Pipeline Audit (30 prompts)

- Status: `ok`
- Duration: 43s (0.7 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 12.
- Classification failures: 4.
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
- Duration: 0s (0.0 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 7 issues: 5 critical, 2 medium.
- Internal class protocol text was recorded as a user turn.
- Delete-email turn was replaced in the transcript by internal protocol content.
- Follow-up routing failed; a dependent reply was reclassified as a fresh turn.
- Greeting turn was polluted with internal protocol text in the transcript.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Follow-Up Fixes Recommended

- Keep class protocol content in a non-user/system channel only, and exclude synthetic protocol messages from transcript persistence and future conversation history.
- Separate protocol injection from user-message persistence. Add a guard in transcript/history writing that drops messages tagged as class protocol or synthetic prompt material.
- When Stage 2 or Stage 3 asks a clarifying question, persist a pending action with expected slot(s) and bypass Stage 1 on the next turn until that pending action is resolved or expires.
- Do not write class-protocol prompt material into user-visible or persisted transcript records. Enforce message typing so only real user utterances are stored as user turns.

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
- der.h:92 log] [2026-05-02 05:38:15 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-05-02 01:38:15.567075388 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-02 05:38:15 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-05-02 01:38:15.760427453 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-02 05:38:15 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-05-02 01:38:15.760462022 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-02 05:38:15 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-05-02 01:38:15.760472588 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-05-02 05:38:15 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m

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

- 2026-05-02 02:06:32,720 INFO Committed 4 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
