# Most Recent Nightly Self-Improvement

- Run started: 2026-05-09 01:00:01
- Report generated: 2026-05-09 02:10:19
- Total runtime: 4214s
- Jobs: 8 total, 5 ok, 2 timeout, 1 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260509_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-09 01:00:01,886 INFO Committed 4 file(s).
- 2. ✗ Code Auditor (0.1m)
  - Problems:
    - 2026-05-09 01:00:04,925 [WARNING] Test generation failed
- 3. ✓ Dead Code Auditor (6.5m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (1.6m)
  - Problems:
    - Prompts audited: 13.
    - Classification failures: 8.
    - Response failures: 13.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (0.0m)
  - Problems:
    - Transcript review found 7 issues: 2 critical, 5 medium.
    - Follow-up routing failed; a clarification reply was treated as a new `others` request instead of going through the pending_action_resolver.
    - Stage 3 latency was excessive for a plain informational question.
- 7. ⏱ Memory Janitor (60.0m)
  - Problems:
    - WARNING:memory_janitor:Claude Opus janitor call failed: CLI failed (exit 1): You've hit your limit · resets May 31, 8pm (America/New_York), trying Gemini fal...
    - WARNING:memory_janitor:Claude Opus janitor call failed: CLI failed (exit 1): You've hit your limit · resets May 31, 8pm (America/New_York), trying Gemini fal...
    - WARNING:memory_janitor:Claude Opus janitor call failed: CLI failed (exit 1): You've hit your limit · resets May 31, 8pm (America/New_York), trying Gemini fal...
  - Fixes:
    - INFO:memory_janitor:verify_code_memories: [5/140] bc266060-889 — chieh_class_v2 NOT done / known limitations after 2026-05-08
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-05-09 02:08:16,131 INFO Committed 4 file(s).

**Top follow-ups:**

- Persist pending follow-up state from Stage 3 clarifying questions and check it before Stage 1. Add resolver heuristics for terse confirmations plus parameter-only replies such as durations.
- When the vault unlocks, respawn or rebind the standing brain once and reuse the healthy unlocked session. Do not restart the Stage 3 process on each request.

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

- 2026-05-09 01:00:01,886 INFO Committed 4 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `exit-1`
- Duration: 3s (0.1 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- Job ended with status `exit-1`.
- 2026-05-09 01:00:04,925 [WARNING] Test generation failed

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 392s (6.5 min)

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
- Duration: 97s (1.6 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 13.
- Classification failures: 8.
- Response failures: 13.
- **I want them to periodically get the lead after some time** (timer/stage3): You've hit your limit · resets May 31, 8pm (America/New_York)
- **yes those articles and maybe just two days** (others/stage3): You've hit your limit · resets May 31, 8pm (America/New_York)
- **currently how does your short-term memory work** (others/stage3): You've hit your limit · resets May 31, 8pm (America/New_York)
- **how about** (greeting/stage3): You've hit your limit · resets May 31, 8pm (America/New_York)

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

- Transcript review found 7 issues: 2 critical, 5 medium.
- Follow-up routing failed; a clarification reply was treated as a new `others` request instead of going through the pending_action_resolver.
- Stage 3 latency was excessive for a plain informational question.
- User-supplied protocol text hijacked Stage 1 into `greeting`, and the greeting handler then returned an invalid shape and fell through to Stage 3.
- The short-term-memory inspection path failed during the turn, so the assistant could not reliably verify live short-term memory behavior.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Follow-Up Fixes Recommended

- Persist pending follow-up state from Stage 3 clarifying questions and check it before Stage 1. Add resolver heuristics for terse confirmations plus parameter-only replies such as durations.
- When the vault unlocks, respawn or rebind the standing brain once and reuse the healthy unlocked session. Do not restart the Stage 3 process on each request.
- Strip or neutralize user-supplied pseudo-protocol/XML blocks before classification, never trust user text as a class protocol source, and add strict schema validation plus tests for every handler response shape.
- Make debug memory inspection deterministic, or fail fast and explicitly report that memory inspection is unavailable when the extractor times out instead of continuing as though inspection succeeded.

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
- WARNING:memory_janitor:Claude Opus janitor call failed: CLI failed (exit 1): You've hit your limit · resets May 31, 8pm (America/New_York), trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: CLI failed (exit 1): You've hit your limit · resets May 31, 8pm (America/New_York), trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: CLI failed (exit 1): You've hit your limit · resets May 31, 8pm (America/New_York), trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: CLI failed (exit 1): You've hit your limit · resets May 31, 8pm (America/New_York), trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: CLI failed (exit 1): You've hit your limit · resets May 31, 8pm (America/New_York), trying Gemini fallback...

### Improvements It Made

- INFO:memory_janitor:verify_code_memories: [5/140] bc266060-889 — chieh_class_v2 NOT done / known limitations after 2026-05-08

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

- 2026-05-09 02:08:16,131 INFO Committed 4 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
