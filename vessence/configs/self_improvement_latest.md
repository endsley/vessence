# Most Recent Nightly Self-Improvement

- Run started: 2026-07-02 01:00:01
- Report generated: 2026-07-02 03:00:41
- Total runtime: 7239s
- Jobs: 8 total, 7 ok, 1 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260702_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-07-02 01:00:01,679 INFO Committed 15 file(s).
- 2. ✓ Code Auditor (6.7m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (8.6m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 11 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 11 dup groups
- 4. ⏱ Pipeline Audit (30 prompts) (20.0m)
  - Problems:
    - Prompts audited: 6.
    - Classification failures: 3.
    - Response failures: 4.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md claims iterative_refactor_scheduler.py is active but no matching cron entry exists
- 6. ✓ Transcript Quality Review (4.5m)
  - Problems:
    - Transcript review found 7 issues: 2 critical, 2 low, 3 medium.
    - Stage 1 produced an out-of-taxonomy intent label before falling back to others.
    - A context-dependent follow-up was sent to Stage 3 with no Jane-side conversation history.
  - Fixes:
    - 2026-07-02 01:39:49,748 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (7 issues)
    - 2026-07-02 01:39:49,872 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 3 medium, 2...
- 7. ✓ Memory Janitor (80.8m)
  - Problems:
    - .381593986 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-02 06:38:42 WARNING] ModelImporter.cpp:739: Make sure input input_ids has I...
    - [0;93m2026-07-02 02:38:42.381654190 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-02 06:38:42 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-07-02 02:38:42.381669363 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-02 06:38:42 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 11 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-07-02 03:00:40,533 INFO Pushed successfully.

**Top follow-ups:**

- Constrain classifier output to the allowed intent enum with schema/grammar decoding and add a regression test for invalid labels.
- Pass the last N session messages or a compact turn summary into Stage 3 for same-session follow-ups, or log and verify persistent Codex session reuse keyed by sid.

## Executive Summary

- 1 stage(s) need attention because they timed out or exited non-zero.
- 6 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-07-02 01:00:01,679 INFO Committed 15 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 404s (6.7 min)

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
- Duration: 514s (8.6 min)

### What It Did

- Scanned the codebase for dead files, unreferenced functions, and duplicate function bodies.

### Problems It Found

- Possibly-dead functions: 1.
- Duplicate function bodies: 11 groups.

### Improvements It Made

- [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 11 dup groups

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
- Duration: 269s (4.5 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 7 issues: 2 critical, 2 low, 3 medium.
- Stage 1 produced an out-of-taxonomy intent label before falling back to others.
- A context-dependent follow-up was sent to Stage 3 with no Jane-side conversation history.
- Stage 1 again produced an invalid intent label before fallback.
- Stage 3 work was cancelled after the client disconnected, so the requested refactor did not complete.

### Improvements It Made

- 2026-07-02 01:39:49,748 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (7 issues)
- 2026-07-02 01:39:49,872 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 3 medium, 2 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Constrain classifier output to the allowed intent enum with schema/grammar decoding and add a regression test for invalid labels.
- Pass the last N session messages or a compact turn summary into Stage 3 for same-session follow-ups, or log and verify persistent Codex session reuse keyed by sid.
- Update the classifier prompt/schema so code, web, and project-work requests resolve to the canonical complex/others escalation class only.
- Decouple long-running Stage 3 coding tasks from the client stream: continue the brain task in the background, send keepalives, persist the result, and let the client reconnect to status.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 4847s (80.8 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- .381593986 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-02 06:38:42 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-07-02 02:38:42.381654190 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-02 06:38:42 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-07-02 02:38:42.381669363 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-02 06:38:42 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-07-02 02:38:42.583742650 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-02 06:38:42 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-07-02 02:38:42.583783649 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-07-02 06:38:42 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 11 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

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

- 2026-07-02 03:00:40,533 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
