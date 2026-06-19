# Most Recent Nightly Self-Improvement

- Run started: 2026-06-18 01:00:01
- Report generated: 2026-06-18 01:52:45
- Total runtime: 3162s
- Jobs: 8 total, 7 ok, 0 timeout, 1 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260618_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.1m)
  - Fixes:
    - 2026-06-18 01:00:05,194 INFO Committed 33 file(s).
- 2. ✗ Code Auditor (2.3m)
  - Problems:
    - 2026-06-18 01:02:22,059 [ERROR] Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for jane_web/jane_v2/recent_context.py', '--no-verif...
- 3. ✓ Dead Code Auditor (6.9m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (19.6m)
  - Problems:
    - Prompts audited: 7.
    - Classification failures: 4.
    - Response failures: 4.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: BUILD_APK
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (3.0m)
  - Problems:
    - Transcript review found 15 issues: 9 critical, 3 low, 3 medium.
    - Stage 1 emitted an unsupported class label before falling back to others.
    - Stage 1 emitted another unsupported class label before falling back to others.
  - Fixes:
    - 2026-06-18 01:31:54,927 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (15 issues)
    - 2026-06-18 01:31:54,928 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 9 critical, 3 medium, 3...
- 7. ✓ Memory Janitor (20.8m)
  - Problems:
    - [0;93m2026-06-18 01:36:49.242592254 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-18 05:36:49 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-18 01:36:49.242635792 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-18 05:36:49 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-18 01:36:49.242648720 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-18 05:36:49 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:memory.v1.conversation_manager:Session 'janitor-window-archival' closed and cleaned up.
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 3 stale memories out of 6 checked. Stale memories make Jan...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Fixes:
    - 2026-06-18 01:52:42,400 INFO Committed 6 file(s).
    - 2026-06-18 01:52:44,178 INFO Pushed successfully.

**Top follow-ups:**

- Constrain classifier output with an enum/JSON schema or add deterministic post-processing tests that reject unknown labels before release.
- Make the Stage 1 decoder validate against the registry enum and log the original model output as a metric; tune examples so meta/system questions classify as others directly.

## Executive Summary

- 1 stage(s) need attention because they timed out or exited non-zero.
- 8 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 3s (0.1 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-06-18 01:00:05,194 INFO Committed 33 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `exit-2`
- Duration: 137s (2.3 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- Job ended with status `exit-2`.
- 2026-06-18 01:02:22,059 [ERROR] Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for jane_web/jane_v2/recent_context.py', '--no-verify']' returned non-zero exit status 1.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 415s (6.9 min)

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
- Duration: 1174s (19.6 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 7.
- Classification failures: 4.
- Response failures: 4.
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help, but I need to know what “it” is first.[/ACK]
- **right now, you are using the same codex process for each prompt instead of spawn** (others/stage3): [ACK]Chieh, I’ll verify the current stage 3 brain process behavior from the runtime code quickly.[/ACK]I found the routing switch: stage 3 uses the st
- **use the source code as your guide** (todo list/stage3): [ACK]Got it, Chieh — I’ll treat the source code as the primary reference.[/ACK]
- **how about the one before that** (end conversation/stage3): [ACK]Chieh, I need one clarification on which previous option you mean.[/ACK]

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
- Duration: 182s (3.0 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 15 issues: 9 critical, 3 low, 3 medium.
- Stage 1 emitted an unsupported class label before falling back to others.
- Stage 1 emitted another unsupported class label before falling back to others.
- Stage 3 received no conversation history for a context-dependent follow-up.
- Stage 1 classification took 34 seconds.

### Improvements It Made

- 2026-06-18 01:31:54,927 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (15 issues)
- 2026-06-18 01:31:54,928 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 9 critical, 3 medium, 3 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Constrain classifier output with an enum/JSON schema or add deterministic post-processing tests that reject unknown labels before release.
- Make the Stage 1 decoder validate against the registry enum and log the original model output as a metric; tune examples so meta/system questions classify as others directly.
- Fix stage3_escalate/session plumbing so sid_override preserves and loads the conversation history; add a regression test where a same-session follow-up reaches Stage 3 with nonzero history.
- Add a hard Stage 1 timeout around the local classifier, fall back to others immediately on timeout, and emit model health metrics.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 1246s (20.8 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- [0;93m2026-06-18 01:36:49.242592254 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-18 05:36:49 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-18 01:36:49.242635792 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-18 05:36:49 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-18 01:36:49.242648720 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-18 05:36:49 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-18 01:36:49.491418361 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-18 05:36:49 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-18 01:36:49.491456228 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-18 05:36:49 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

### Improvements It Made

- INFO:memory.v1.conversation_manager:Session 'janitor-window-archival' closed and cleaned up.
- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 3 stale memories out of 6 checked. Stale memories make Jane give wrong answers about her own a

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

- 2026-06-18 01:52:42,400 INFO Committed 6 file(s).
- 2026-06-18 01:52:44,178 INFO Pushed successfully.

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
