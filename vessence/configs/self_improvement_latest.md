# Most Recent Nightly Self-Improvement

- Run started: 2026-04-30 01:00:01
- Report generated: 2026-04-30 02:10:30
- Total runtime: 4228s
- Jobs: 8 total, 4 ok, 4 timeout, 0 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260430_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-04-30 01:00:03,331 INFO Committed 51 file(s).
- 2. ✓ Code Auditor (0.0m)
  - Problems:
    - 2026-04-30 01:00:03,460 [WARNING] Working tree has uncommitted changes — skipping audit.
- 3. ⏱ Dead Code Auditor (15.0m)
  - Problems:
    - Dead files — review needed: 1.
    - Possibly-dead functions: 13.
    - Duplicate function bodies: 9 groups.
- 4. ⏱ Pipeline Audit (30 prompts) (20.0m)
  - Problems:
    - Prompts audited: 18.
    - Classification failures: 3.
    - Response failures: 12.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (3.4m)
  - Problems:
    - Transcript review found 6 issues: 2 critical, 1 low, 3 medium.
    - Memory/thematic persistence failed on the same turn the user asked about short-term memory.
    - Internal class-protocol text leaked into the recorded user turn, and the greeting fast path failed.
  - Fixes:
    - 2026-04-30 01:38:29,863 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (6 issues)
    - 2026-04-30 01:38:29,864 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 3 medium, 1...
- 7. ⏱ Memory Janitor (30.0m)
  - Problems:
    - WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
    - WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
    - WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-04-30 02:08:30,577 INFO Committed 5 file(s).

**Top follow-ups:**

- Remove the hard dependency on the external `claude` executable for thematic classification/summary. Use the configured provider API directly, or detect the missing binary at startup and fall back cleanly.
- Keep raw user text separate from Stage 3 prompt scaffolding in persistence/history/TTS, and add schema-contract tests so the greeting handler always returns a valid Stage 2 response.

## Executive Summary

- 4 stage(s) need attention because they timed out or exited non-zero.
- 4 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 1s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-04-30 01:00:03,331 INFO Committed 51 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- 2026-04-30 01:00:03,460 [WARNING] Working tree has uncommitted changes — skipping audit.

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

- Status: `timeout`
- Duration: 1200s (20.0 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Job ended with status `timeout`.
- Prompts audited: 18.
- Classification failures: 3.
- Response failures: 12.
- ****Class Protocol: Read Calendar**
- ****Class Protocol: Read Calendar**
- **I need clarification. The "new turn" you provided is class protocol metadata (de** (others/stage3):
- ****Class Protocol: Read Calendar**

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
- Duration: 206s (3.4 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 6 issues: 2 critical, 1 low, 3 medium.
- Memory/thematic persistence failed on the same turn the user asked about short-term memory.
- Internal class-protocol text leaked into the recorded user turn, and the greeting fast path failed.
- The classifier emitted an out-of-schema label (`force stage3`) instead of a registered intent.
- A technical/product-debugging request was misclassified as `send message`, sending the turn into the SMS flow.

### Improvements It Made

- 2026-04-30 01:38:29,863 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (6 issues)
- 2026-04-30 01:38:29,864 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 2 critical, 3 medium, 1 minor issues. The most urgent

### Follow-Up Fixes Recommended

- Remove the hard dependency on the external `claude` executable for thematic classification/summary. Use the configured provider API directly, or detect the missing binary at startup and fall back cleanly.
- Keep raw user text separate from Stage 3 prompt scaffolding in persistence/history/TTS, and add schema-contract tests so the greeting handler always returns a valid Stage 2 response.
- Constrain classifier decoding to the allowed label set, or add a parser that translates control labels like `force stage3` before scoring/logging them.
- Tighten `send message` intent gating so it requires an explicit messaging verb plus a plausible contact/recipient, and down-rank it when the utterance refers to system behavior or follows a technical discussion. Also make the handler return a structured clarify/escalate object instead of `invalid shape`.

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
- WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: Expecting value: line 1 column 1 (char 0), trying Gemini fallback...
- [0;93m2026-04-30 01:48:49.262595600 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-04-30 05:48:49 WARNING] ModelImporter.cpp:739: Make sure input input_ids has Int64 binding.[m
- [0;93m2026-04-30 01:48:49.262639974 [W:onnxruntime:Default, tensorrt_execution_provider.h:92 log] [2026-04-30 05:48:49 WARNING] ModelImporter.cpp:739: Make sure input attention_mask has Int64 binding.[m

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

- 2026-04-30 02:08:30,577 INFO Committed 5 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
