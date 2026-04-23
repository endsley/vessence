# Most Recent Nightly Self-Improvement

- Run started: 2026-04-22 01:00:01
- Report generated: 2026-04-22 02:07:22
- Total runtime: 4036s
- Jobs: 8 total, 6 ok, 2 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260422_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-04-22 01:00:02,455 INFO Committed 74 file(s).
- 2. ✓ Code Auditor (0.0m)
  - Problems:
    - 2026-04-22 01:00:02,555 [WARNING] Working tree has uncommitted changes — skipping audit.
- 3. ✓ Dead Code Auditor (14.5m)
  - Problems:
    - Dead files — review needed: 1.
    - Possibly-dead functions: 13.
    - Duplicate function bodies: 9 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 1 flagged, 13 dead funcs, 9 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (19.2m)
  - Problems:
    - Prompts audited: 30.
    - Classification failures: 10.
    - Response failures: 23.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems: none detected
  - Fixes: none applied
- 6. ✓ Transcript Quality Review (1.5m)
  - Problems:
    - Transcript review found 14 issues: 6 critical, 2 low, 6 medium.
    - Build/APK request was not recognized as a first-class intent and fell through as others.
    - Stage 3 lost active conversation context after a standing-brain restart.
  - Fixes:
    - 2026-04-22 01:35:17,972 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (14 issues)
    - 2026-04-22 01:35:17,973 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 6 critical, 6 medium, 2...
- 7. ⏱ Memory Janitor (30.0m)
  - Problems:
    - roviderInfo_TensorRT] /onnxruntime_src/onnxruntime/core/session/provider_bridge_ort.cc:1952 onnxruntime::Provider& onnxruntime::ProviderLibrary::Get() [ONNXR...
    - [1;31m2026-04-22 01:58:33.299038799 [E:onnxruntime:Default, provider_bridge_ort.cc:2331 TryGetProviderInfo_TensorRT] /onnxruntime_src/onnxruntime/core/sessi...
    - [1;31m2026-04-22 01:59:49.391762979 [E:onnxruntime:Default, provider_bridge_ort.cc:2331 TryGetProviderInfo_TensorRT] /onnxruntime_src/onnxruntime/core/sessi...
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-04-22 02:05:22,615 INFO Committed 13 file(s).

**Top follow-ups:**

- Add `build apk` / `compile android` / `new Android version` aliases to the classifier schema, mapped to a no-handler Stage 3/delegate class.
- Persist recent conversation history outside the standing-brain process and always inject session history after brain restarts; do not let process restarts reset conversational context.

## Executive Summary

- 2 stage(s) need attention because they timed out or exited non-zero.
- 5 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-04-22 01:00:02,455 INFO Committed 74 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- 2026-04-22 01:00:02,555 [WARNING] Working tree has uncommitted changes — skipping audit.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 868s (14.5 min)

### What It Did

- Scanned the codebase for dead files, unreferenced functions, and duplicate function bodies.

### Problems It Found

- Dead files — review needed: 1.
- Possibly-dead functions: 13.
- Duplicate function bodies: 9 groups.

### Improvements It Made

- [dead-code] Done — 0 auto-deleted, 1 flagged, 13 dead funcs, 9 dup groups

### Evidence Files

- /home/chieh/ambient/vessence/configs/dead_code_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_dead_code_auditor.log

## Stage 4: Pipeline Audit (30 prompts)

- Status: `ok`
- Duration: 1155s (19.2 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 30.
- Classification failures: 10.
- Response failures: 23.
- **yeah** (end conversation/stage2): Ok.
- **yes please** (send message/stage3):
- **I thought I asked you to add a new item** (others/stage3):
- **then what did you not read it when I asked you for it** (read messages/stage3):

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

- No problems were detected in the available logs/reports.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/doc_drift_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_doc_drift_auditor.log

## Stage 6: Transcript Quality Review

- Status: `ok`
- Duration: 91s (1.5 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 14 issues: 6 critical, 2 low, 6 medium.
- Build/APK request was not recognized as a first-class intent and fell through as others.
- Stage 3 lost active conversation context after a standing-brain restart.
- Build/APK request was again classified as an unknown class and routed through fallback.
- Stage 3 appeared to acknowledge a to-do add without actually using the Stage 2 to-do-list source of truth.

### Improvements It Made

- 2026-04-22 01:35:17,972 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (14 issues)
- 2026-04-22 01:35:17,973 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 6 critical, 6 medium, 2 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Add `build apk` / `compile android` / `new Android version` aliases to the classifier schema, mapped to a no-handler Stage 3/delegate class.
- Persist recent conversation history outside the standing-brain process and always inject session history after brain restarts; do not let process restarts reset conversational context.
- Normalize build-related classifier outputs before schema validation, or add `build apk` as a supported delegate-to-Stage-3 class.
- Route `add item to clinic to-do list` directly to the todo-list handler, or give Stage 3 a real Google Docs-backed todo tool/protocol and require tool execution before confirming completion.

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
- roviderInfo_TensorRT] /onnxruntime_src/onnxruntime/core/session/provider_bridge_ort.cc:1952 onnxruntime::Provider& onnxruntime::ProviderLibrary::Get() [ONNXRuntimeError] : 1 : FAIL : Failed to load library /home/chieh/google-adk-env/adk-venv/lib/python3.13/site-packages/onnxruntime/capi/libonnxruntime_providers_tensorrt.so with error: libnvinfer.so.10: cannot open shared object file: No such file or directory
- [1;31m2026-04-22 01:58:33.299038799 [E:onnxruntime:Default, provider_bridge_ort.cc:2331 TryGetProviderInfo_TensorRT] /onnxruntime_src/onnxruntime/core/session/provider_bridge_ort.cc:1952 onnxruntime::Provider& onnxruntime::ProviderLibrary::Get() [ONNXRuntimeError] : 1 : FAIL : Failed to load library /home/chieh/google-adk-env/adk-venv/lib/python3.13/site-packages/onnxruntime/capi/libonnxruntime_providers_tensorrt.so with error: libnvinfer.so.10: cannot open shared object file: No such file or directory
- [1;31m2026-04-22 01:59:49.391762979 [E:onnxruntime:Default, provider_bridge_ort.cc:2331 TryGetProviderInfo_TensorRT] /onnxruntime_src/onnxruntime/core/session/provider_bridge_ort.cc:1952 onnxruntime::Provider& onnxruntime::ProviderLibrary::Get() [ONNXRuntimeError] : 1 : FAIL : Failed to load library /home/chieh/google-adk-env/adk-venv/lib/python3.13/site-packages/onnxruntime/capi/libonnxruntime_providers_tensorrt.so with error: libnvinfer.so.10: cannot open shared object file: No such file or directory
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

- 2026-04-22 02:05:22,615 INFO Committed 13 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
