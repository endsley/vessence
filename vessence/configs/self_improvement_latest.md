# Most Recent Nightly Self-Improvement

- Run started: 2026-04-24 01:00:01
- Report generated: 2026-04-24 01:59:05
- Total runtime: 3544s
- Jobs: 8 total, 5 ok, 3 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260424_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-04-24 01:00:01,988 INFO Committed 42 file(s).
- 2. ✓ Code Auditor (0.0m)
  - Problems:
    - 2026-04-24 01:00:02,110 [WARNING] Working tree has uncommitted changes — skipping audit.
- 3. ⏱ Dead Code Auditor (15.0m)
  - Problems:
    - Dead files — review needed: 1.
    - Possibly-dead functions: 13.
    - Duplicate function bodies: 9 groups.
- 4. ✓ Pipeline Audit (30 prompts) (8.0m)
  - Problems:
    - Prompts audited: 20.
    - Classification failures: 7.
    - Response failures: 16.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md claims run_marketplace_cron.sh is active but no matching cron entry exists
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (4.1m)
  - Problems:
    - Transcript review found 7 issues: 2 critical, 5 medium.
    - Stage 1 misclassified a clear to-do-list request as `others`, so the fast-path to-do handler never ran.
    - Follow-up routing failed: the user's category answer was not sent directly to the pending to-do flow.
  - Fixes:
    - 2026-04-24 01:27:05,240 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (7 issues)
    - 2026-04-24 01:27:05,241 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 5 medium iss...
- 7. ⏱ Memory Janitor (30.0m)
  - Problems:
    - e/session/provider_bridge_ort.cc:1952 onnxruntime::Provider& onnxruntime::ProviderLibrary::Get() [ONNXRuntimeError] : 1 : FAIL : Failed to load library /home...
    - WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
    - WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
  - Fixes:
    - INFO:memory_janitor:verify_code_memories: [3/122] 6fdf22fa-f9b — When finishing a task, explicitly say 'done' and state what
    - INFO:memory_janitor:verify_code_memories: UPDATED 6fdf22fa-f9b — Verified AGENTS.md, CLAUDE.md, GEMINI.md: none require literally saying 'done'.
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-04-24 01:57:05,500 INFO Committed 5 file(s).

**Top follow-ups:**

- Add lexical/rule fallback for `to do`, `to-do`, and `todo list` phrases before `others`, and retrain the Stage 1 examples so list-reading requests map to `todo list` reliably.
- When Stage 2 or Stage 3 asks a constrained follow-up like a to-do category, persist a pending action and bypass Stage 1 entirely on the next user turn.

## Executive Summary

- 3 stage(s) need attention because they timed out or exited non-zero.
- 6 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-04-24 01:00:01,988 INFO Committed 42 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- 2026-04-24 01:00:02,110 [WARNING] Working tree has uncommitted changes — skipping audit.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `timeout`
- Duration: 900s (15.0 min)

### What It Did

- Scanned the codebase for dead files, unreferenced functions, and duplicate function bodies.

### Problems It Found

- Job ended with status `timeout`.
- Dead files — review needed: 1.
- Possibly-dead functions: 13.
- Duplicate function bodies: 9 groups.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/dead_code_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_dead_code_auditor.log

## Stage 4: Pipeline Audit (30 prompts)

- Status: `ok`
- Duration: 477s (8.0 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 20.
- Classification failures: 7.
- Response failures: 16.
- **user: the home
- **user: how about for the clinic
- ****Summary:**
- ****Summary:**

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

- CRON_JOBS.md claims run_marketplace_cron.sh is active but no matching cron entry exists
- v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/doc_drift_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_doc_drift_auditor.log

## Stage 6: Transcript Quality Review

- Status: `ok`
- Duration: 245s (4.1 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 7 issues: 2 critical, 5 medium.
- Stage 1 misclassified a clear to-do-list request as `others`, so the fast-path to-do handler never ran.
- Follow-up routing failed: the user's category answer was not sent directly to the pending to-do flow.
- Jane returned an incorrect clinic to-do list count and duplicated one item.
- Stage 1 misclassified a straightforward weather request as `others`, bypassing the weather fast path.

### Improvements It Made

- 2026-04-24 01:27:05,240 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (7 issues)
- 2026-04-24 01:27:05,241 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 5 medium issues. The most urgent was: A si

### Follow-Up Fixes Recommended

- Add lexical/rule fallback for `to do`, `to-do`, and `todo list` phrases before `others`, and retrain the Stage 1 examples so list-reading requests map to `todo list` reliably.
- When Stage 2 or Stage 3 asks a constrained follow-up like a to-do category, persist a pending action and bypass Stage 1 entirely on the next user turn.
- Force all to-do reads, including Stage 3 fallbacks, through the same `todo_list_cache.json` reader/deduper used by Stage 2, and deduplicate items before rendering speech.
- Expand Stage 1 weather training/examples for phrasings like `what's the weather like tomorrow` and add a keyword fallback for `weather`, `forecast`, `tomorrow`, and `rain` patterns.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `timeout`
- Duration: 1800s (30.0 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- Job ended with status `timeout`.
- e/session/provider_bridge_ort.cc:1952 onnxruntime::Provider& onnxruntime::ProviderLibrary::Get() [ONNXRuntimeError] : 1 : FAIL : Failed to load library /home/chieh/google-adk-env/adk-venv/lib/python3.13/site-packages/onnxruntime/capi/libonnxruntime_providers_tensorrt.so with error: libnvinfer.so.10: cannot open shared object file: No such file or directory
- WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
- [1;31m2026-04-24 01:33:59.324098221 [E:onnxruntime:Default, provider_bridge_ort.cc:2331 TryGetProviderInfo_TensorRT] /onnxruntime_src/onnxruntime/core/session/provider_bridge_ort.cc:1952 onnxruntime::Provider& onnxruntime::ProviderLibrary::Get() [ONNXRuntimeError] : 1 : FAIL : Failed to load library /home/chieh/google-adk-env/adk-venv/lib/python3.13/site-packages/onnxruntime/capi/libonnxruntime_providers_tensorrt.so with error: libnvinfer.so.10: cannot open shared object file: No such file or directory

### Improvements It Made

- INFO:memory_janitor:verify_code_memories: [3/122] 6fdf22fa-f9b — When finishing a task, explicitly say 'done' and state what
- INFO:memory_janitor:verify_code_memories: UPDATED 6fdf22fa-f9b — Verified AGENTS.md, CLAUDE.md, GEMINI.md: none require literally saying 'done'.

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

- 2026-04-24 01:57:05,500 INFO Committed 5 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
