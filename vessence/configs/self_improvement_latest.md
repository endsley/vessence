# Most Recent Nightly Self-Improvement

- Run started: 2026-04-23 01:00:01
- Report generated: 2026-04-23 02:06:30
- Total runtime: 3987s
- Jobs: 8 total, 5 ok, 3 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260423_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-04-23 01:00:02,028 INFO Committed 47 file(s).
- 2. ✓ Code Auditor (0.0m)
  - Problems:
    - 2026-04-23 01:00:02,124 [WARNING] Working tree has uncommitted changes — skipping audit.
- 3. ⏱ Dead Code Auditor (15.0m)
  - Problems:
    - Dead files — review needed: 1.
    - Possibly-dead functions: 13.
    - Duplicate function bodies: 9 groups.
- 4. ✓ Pipeline Audit (30 prompts) (16.8m)
  - Problems:
    - Prompts audited: 30.
    - Classification failures: 6.
    - Response failures: 25.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md claims run_marketplace_cron.sh is active but no matching cron entry exists
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (2.7m)
  - Problems:
    - Transcript review found 21 issues: 6 critical, 15 medium.
    - Live session endpoint was repeatedly crashing.
    - Todo list response repeated the same clinic item twice.
  - Fixes:
    - 2026-04-23 01:34:29,111 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (21 issues)
    - 2026-04-23 01:34:29,112 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 6 critical, 15 medium is...
- 7. ⏱ Memory Janitor (30.0m)
  - Problems:
    - oogle-adk-env/adk-venv/lib/python3.13/site-packages/onnxruntime/capi/libonnxruntime_providers_tensorrt.so with error: libnvinfer.so.10: cannot open shared ob...
    - [1;31m2026-04-23 01:56:13.801181344 [E:onnxruntime:Default, provider_bridge_ort.cc:2331 TryGetProviderInfo_TensorRT] /onnxruntime_src/onnxruntime/core/sessi...
    - [1;31m2026-04-23 01:57:44.476234951 [E:onnxruntime:Default, provider_bridge_ort.cc:2331 TryGetProviderInfo_TensorRT] /onnxruntime_src/onnxruntime/core/sessi...
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-04-23 02:04:29,666 INFO Committed 7 file(s).

**Top follow-ups:**

- Fix the /api/jane/live cleanup path to pass session_id into end_session(), or make end_session accept/derive the active session safely.
- Deduplicate todo items in the Google Doc sync or Stage 2 todo list formatter using normalized text keys before counting and rendering category items.

## Executive Summary

- 3 stage(s) need attention because they timed out or exited non-zero.
- 4 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-04-23 01:00:02,028 INFO Committed 47 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- 2026-04-23 01:00:02,124 [WARNING] Working tree has uncommitted changes — skipping audit.

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
- Duration: 1006s (16.8 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 30.
- Classification failures: 6.
- Response failures: 25.
- ****Updated Summary:**
- ****Updated Summary:**
- ****Updated Summary:**
- ****Updated Summary:**

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
- Duration: 160s (2.7 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 21 issues: 6 critical, 15 medium.
- Live session endpoint was repeatedly crashing.
- Todo list response repeated the same clinic item twice.
- Stage 3 gave an unhelpful clarification response instead of handling the joke request or explaining the singing limitation.
- Calendar query was misclassified as others and routed to slow Stage 3.

### Improvements It Made

- 2026-04-23 01:34:29,111 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (21 issues)
- 2026-04-23 01:34:29,112 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 6 critical, 15 medium issues. The most urgent was: Liv

### Follow-Up Fixes Recommended

- Fix the /api/jane/live cleanup path to pass session_id into end_session(), or make end_session accept/derive the active session safely.
- Deduplicate todo items in the Google Doc sync or Stage 2 todo list formatter using normalized text keys before counting and rendering category items.
- Add Stage 3 instruction for mixed entertainment/audio-modulation requests: comply with text-safe parts like jokes and briefly state unavailable voice effects instead of asking for repetition.
- Constrain classifier outputs to the allowed enum and add a post-processor rule mapping calendar-count/date-range questions to read_calendar before falling back to others.

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
- oogle-adk-env/adk-venv/lib/python3.13/site-packages/onnxruntime/capi/libonnxruntime_providers_tensorrt.so with error: libnvinfer.so.10: cannot open shared object file: No such file or directory
- [1;31m2026-04-23 01:56:13.801181344 [E:onnxruntime:Default, provider_bridge_ort.cc:2331 TryGetProviderInfo_TensorRT] /onnxruntime_src/onnxruntime/core/session/provider_bridge_ort.cc:1952 onnxruntime::Provider& onnxruntime::ProviderLibrary::Get() [ONNXRuntimeError] : 1 : FAIL : Failed to load library /home/chieh/google-adk-env/adk-venv/lib/python3.13/site-packages/onnxruntime/capi/libonnxruntime_providers_tensorrt.so with error: libnvinfer.so.10: cannot open shared object file: No such file or directory
- [1;31m2026-04-23 01:57:44.476234951 [E:onnxruntime:Default, provider_bridge_ort.cc:2331 TryGetProviderInfo_TensorRT] /onnxruntime_src/onnxruntime/core/session/provider_bridge_ort.cc:1952 onnxruntime::Provider& onnxruntime::ProviderLibrary::Get() [ONNXRuntimeError] : 1 : FAIL : Failed to load library /home/chieh/google-adk-env/adk-venv/lib/python3.13/site-packages/onnxruntime/capi/libonnxruntime_providers_tensorrt.so with error: libnvinfer.so.10: cannot open shared object file: No such file or directory
- *************** EP Error ***************
- EP Error /onnxruntime_src/onnxruntime/python/onnxruntime_pybind_state.cc:539 void onnxruntime::python::RegisterTensorRTPluginsAsCustomOps(PySessionOptions&, const onnxruntime::ProviderOptions&) Please install TensorRT libraries as mentioned in the GPU requirements page, make sure they're in the PATH or LD_LIBRARY_PATH, and that your GPU is supported.

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

- 2026-04-23 02:04:29,666 INFO Committed 7 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
