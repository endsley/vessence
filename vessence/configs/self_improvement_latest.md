# Most Recent Nightly Self-Improvement

- Run started: 2026-06-17 01:00:02
- Report generated: 2026-06-17 01:37:45
- Total runtime: 2263s
- Jobs: 8 total, 7 ok, 0 timeout, 1 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260617_010002.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-06-17 01:00:02,356 INFO Committed 2 file(s).
- 2. ✗ Code Auditor (2.1m)
  - Problems:
    - 2026-06-17 01:02:11,474 [ERROR] Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for jane_web/jane_v2/recent_context.py', '--no-verif...
- 3. ✓ Dead Code Auditor (6.7m)
  - Problems:
    - Possibly-dead functions: 2.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 2 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (18.3m)
  - Problems:
    - Prompts audited: 6.
    - Classification failures: 4.
    - Response failures: 3.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: BUILD_APK
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (0.7m)
  - Problems:
    - Transcript review found 4 issues: 1 critical, 2 low, 1 medium.
    - Stage 1 emitted an out-of-schema intent label before falling back to others.
    - Stage 1 emitted an out-of-schema intent label before falling back to others.
  - Fixes:
    - 2026-06-17 01:27:50,311 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (4 issues)
    - 2026-06-17 01:27:50,312 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 1 medium, 2...
- 7. ✓ Memory Janitor (9.8m)
  - Problems:
    - [0;93m2026-06-17 01:37:11.656050538 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-17 05:37:11 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-17 01:37:11.656091225 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-17 05:37:11 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-17 01:37:11.656106429 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-17 05:37:11 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:memory.v1.conversation_manager:Session 'janitor-window-archival' closed and cleaned up.
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 1 stale memories out of 1 checked. Stale memories make Jan...
- 8. ✓ Auto-Commit + Push (post) (0.1m)
  - Fixes:
    - 2026-06-17 01:37:41,948 INFO Committed 6 file(s).
    - 2026-06-17 01:37:45,192 INFO Pushed successfully.

**Top follow-ups:**

- Constrain the classifier output to the canonical enum and add tests for project/codebase questions so they resolve directly to others/escalate without unknown-label warnings.
- Make Stage 1 reject or normalize only known enum values at the model-output schema level; add a regression case for meta/system architecture questions.

## Executive Summary

- 1 stage(s) need attention because they timed out or exited non-zero.
- 8 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-17 01:00:02,356 INFO Committed 2 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `exit-2`
- Duration: 129s (2.1 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- Job ended with status `exit-2`.
- 2026-06-17 01:02:11,474 [ERROR] Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for jane_web/jane_v2/recent_context.py', '--no-verify']' returned non-zero exit status 1.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 399s (6.7 min)

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
- Duration: 1100s (18.3 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 6.
- Classification failures: 4.
- Response failures: 3.
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help with the payment, but I need one quick detail first.[/ACK]
- **right now, you are using the same codex process for each prompt instead of spawn** (others/stage3): [ACK]Chieh, I’ll verify the current Stage 3 brain code path rather than guessing; this should be a quick check.[/ACK]I found the relevant Stage 3 rout
- **use the source code as your guide** (todo list/stage3): Understood, Chieh. I’ll treat the source code as the authority and verify behavior there before making claims or edits.

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
- Duration: 39s (0.7 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 4 issues: 1 critical, 2 low, 1 medium.
- Stage 1 emitted an out-of-schema intent label before falling back to others.
- Stage 1 emitted an out-of-schema intent label before falling back to others.
- Stage 3 took over three minutes for a repository-familiarization request.
- Stage 3 failed to complete a large implementation request before the client disconnected/cancelled.

### Improvements It Made

- 2026-06-17 01:27:50,311 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (4 issues)
- 2026-06-17 01:27:50,312 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 1 medium, 2 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Constrain the classifier output to the canonical enum and add tests for project/codebase questions so they resolve directly to others/escalate without unknown-label warnings.
- Make Stage 1 reject or normalize only known enum values at the model-output schema level; add a regression case for meta/system architecture questions.
- Add a bounded repo-orientation path for Stage 3: gather key files with a time budget, stream progress, and return a concise status instead of allowing a long unbounded exploration.
- For long code tasks, switch Stage 3 to a durable background job with progress events and resumable results, or reject voice/stream execution into a task mode before starting. Also increase observability around primary/fallback LLM timeout boundaries.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 590s (9.8 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-06-17 01:37:11.656050538 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-17 05:37:11 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-17 01:37:11.656091225 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-17 05:37:11 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-17 01:37:11.656106429 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-17 05:37:11 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-17 01:37:11.874705982 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-17 05:37:11 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-17 01:37:11.874743689 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-17 05:37:11 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:memory.v1.conversation_manager:Session 'janitor-window-archival' closed and cleaned up.
- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 1 stale memories out of 1 checked. Stale memories make Jane give wrong answers about her own a

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_janitor_memory.log

## Stage 8: Auto-Commit + Push (post)

- Status: `ok`
- Duration: 4s (0.1 min)

### What It Did

- Committed and pushed generated fixes and reports after the run.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-17 01:37:41,948 INFO Committed 6 file(s).
- 2026-06-17 01:37:45,192 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
