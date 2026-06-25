# Most Recent Nightly Self-Improvement

- Run started: 2026-06-24 01:00:01
- Report generated: 2026-06-24 02:52:30
- Total runtime: 6748s
- Jobs: 8 total, 8 ok, 0 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260624_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-06-24 01:00:02,440 INFO Committed 11 file(s).
- 2. ✓ Code Auditor (6.6m)
  - Problems: none detected
  - Fixes: none applied
- 3. ✓ Dead Code Auditor (7.3m)
  - Problems:
    - Dead files — review needed: 1.
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 1 flagged, 1 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (17.7m)
  - Problems:
    - Prompts audited: 6.
    - Classification failures: 2.
    - Response failures: 2.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - CRON_JOBS.md missing entry for active cron script: check_income_cache_load_times.py
    - CRON_JOBS.md missing entry for active cron script: nightly_update_current_month_reports.py
- 6. ✓ Transcript Quality Review (1.7m)
  - Problems:
    - Transcript review found 6 issues: 1 critical, 2 low, 3 medium.
    - Stage 1 classifier produced an unsupported intent label, then coerced it to others.
    - Stage 1 classifier produced another unsupported intent label.
  - Fixes:
    - 2026-06-24 01:33:19,666 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (6 issues)
    - 2026-06-24 01:33:19,667 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 3 medium, 2...
- 7. ✓ Memory Janitor (79.1m)
  - Problems:
    - untime:Default, tensorrt_execution_provider.h:92 log] [2026-06-24 06:26:15 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
    - [0;93m2026-06-24 02:32:33.880031447 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-24 06:32:33 WARNING] ModelImporter.cpp:739: Make...
    - [0;93m2026-06-24 02:32:33.880084678 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-24 06:32:33 WARNING] ModelImporter.cpp:739: Make...
  - Fixes:
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 15 stale memories out of 20 checked. Stale memories make J...
- 8. ✓ Auto-Commit + Push (post) (0.0m)
  - Problems:
    - 2026-06-24 02:52:29,788 WARNING git push failed: fatal: could not read Username for 'https://github.com': No such device or address
  - Fixes:
    - 2026-06-24 02:52:29,504 INFO Committed 7 file(s).

**Top follow-ups:**

- Constrain Stage 1 decoding to the supported enum or add an explicit postprocessor mapping unsupported stage3-style labels to others without warning noise.
- Update the classifier prompt/schema so it cannot emit meta-labels like 'force stage3'; use a fixed enum or validated JSON schema.

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

- 2026-06-24 01:00:02,440 INFO Committed 11 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 395s (6.6 min)

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
- Duration: 437s (7.3 min)

### What It Did

- Scanned the codebase for dead files, unreferenced functions, and duplicate function bodies.

### Problems It Found

- Dead files — review needed: 1.
- Possibly-dead functions: 1.
- Duplicate function bodies: 10 groups.

### Improvements It Made

- [dead-code] Done — 0 auto-deleted, 1 flagged, 1 dead funcs, 10 dup groups

### Evidence Files

- /home/chieh/ambient/vessence/configs/dead_code_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_dead_code_auditor.log

## Stage 4: Pipeline Audit (30 prompts)

- Status: `ok`
- Duration: 1060s (17.7 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 6.
- Classification failures: 2.
- Response failures: 2.
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help pay it, but I need the bill details first.[/ACK]
- **use the source code as your guide** (todo list/stage3): Understood, Chieh. I’ll treat the source code as the authority and verify behavior against it before making claims or changes.

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
- CRON_JOBS.md missing entry for active cron script: check_income_cache_load_times.py
- CRON_JOBS.md missing entry for active cron script: nightly_update_current_month_reports.py
- CRON_JOBS.md missing entry for active cron script: nutricost_deal_monitor.py
- CRON_JOBS.md claims run_kathia_schedule.py is active but no matching cron entry exists
- v2_3stage_pipeline.md missing class row: BUILD_APK
- v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- v2_3stage_pipeline.md missing class row: DELETE_EMAIL

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/doc_drift_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_doc_drift_auditor.log

## Stage 6: Transcript Quality Review

- Status: `ok`
- Duration: 103s (1.7 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 6 issues: 1 critical, 2 low, 3 medium.
- Stage 1 classifier produced an unsupported intent label, then coerced it to others.
- Stage 1 classifier produced another unsupported intent label.
- Stage 1 took 14 seconds on a short follow-up utterance.
- Stage 3 follow-up context appears fragile because each OpenAI stream is logged with history=0.

### Improvements It Made

- 2026-06-24 01:33:19,666 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (6 issues)
- 2026-06-24 01:33:19,667 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 1 critical, 3 medium, 2 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Constrain Stage 1 decoding to the supported enum or add an explicit postprocessor mapping unsupported stage3-style labels to others without warning noise.
- Update the classifier prompt/schema so it cannot emit meta-labels like 'force stage3'; use a fixed enum or validated JSON schema.
- Add a short classifier deadline, for example 1500-2500ms, and escalate to Stage 3 on timeout for non-fast-path text.
- Verify sid_override actually binds to a persistent Stage 3 session; if not, pass recent conversation history into stream_message or persist it server-side by conversation id.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 4748s (79.1 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- untime:Default, tensorrt_execution_provider.h:92 log] [2026-06-24 06:26:15 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-24 02:32:33.880031447 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-24 06:32:33 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-06-24 02:32:33.880084678 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-24 06:32:33 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m
- [0;93m2026-06-24 02:32:33.880099036 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-24 06:32:33 WARNING] ModelImporter.cpp:739: Make sure input token_type_ids has Int64 binding.[m
- [0;93m2026-06-24 02:32:34.108699981 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-06-24 06:32:34 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m

### Improvements It Made

- INFO:agent_skills.self_improve_log:self_improve_log: recorded [medium] Memory Verification — Found 15 stale memories out of 20 checked. Stale memories make Jane give wrong answers about her own

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_janitor_memory.log

## Stage 8: Auto-Commit + Push (post)

- Status: `ok`
- Duration: 1s (0.0 min)

### What It Did

- Committed and pushed generated fixes and reports after the run.

### Problems It Found

- 2026-06-24 02:52:29,788 WARNING git push failed: fatal: could not read Username for 'https://github.com': No such device or address

### Improvements It Made

- 2026-06-24 02:52:29,504 INFO Committed 7 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
