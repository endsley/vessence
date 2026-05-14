# Most Recent Nightly Self-Improvement

- Run started: 2026-05-13 01:00:01
- Report generated: 2026-05-13 01:52:38
- Total runtime: 3157s
- Jobs: 8 total, 6 ok, 1 timeout, 1 failed
- Stable latest report path: `/home/chieh/ambient/vessence/configs/self_improvement_latest.md`
- Archived copy: `/home/chieh/ambient/vessence-data/reports/self_improvement/self_improvement_20260513_010001.md`

## TL;DR

- 1. ✓ Auto-Commit WIP (pre) (0.0m)
  - Fixes:
    - 2026-05-13 01:00:01,999 INFO Committed 4 file(s).
- 2. ✗ Code Auditor (0.1m)
  - Problems:
    - 2026-05-13 01:00:05,537 [ERROR] Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for jane_web/jane_v2/classes/shopping_list/handler.p...
- 3. ✓ Dead Code Auditor (5.9m)
  - Problems:
    - Possibly-dead functions: 1.
    - Duplicate function bodies: 10 groups.
  - Fixes:
    - [dead-code] Done — 0 auto-deleted, 0 flagged, 1 dead funcs, 10 dup groups
- 4. ✓ Pipeline Audit (30 prompts) (1.7m)
  - Problems:
    - Prompts audited: 12.
    - Classification failures: 7.
    - Response failures: 12.
- 5. ✓ Doc Drift Auditor (0.0m)
  - Problems:
    - CRON_JOBS.md missing entry for active cron script: auto_pull.sh
    - v2_3stage_pipeline.md missing class row: CLINIC_SCHEDULES_INFO
- 6. ✓ Transcript Quality Review (3.6m)
  - Problems:
    - Transcript review found 5 issues: 3 critical, 2 medium.
    - Follow-up answer was not routed through the pending_action_resolver and got reclassified from scratch
    - Raw `<class_protocol>` text was misclassified as a real greeting, and the greeting handler's WRONG_CLASS path degraded into an invalid-shape Stage 3 escalation
  - Fixes:
    - 2026-05-13 01:11:17,920 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (5 issues)
    - 2026-05-13 01:11:17,921 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 3 critical, 2 medium iss...
- 7. ✓ Memory Janitor (39.3m)
  - Problems:
    - WARNING:memory.v1.conversation_manager:Thematic archival failed: [Errno 7] Argument list too long: 'claude'
    - WARNING:memory_janitor:Claude Opus janitor call failed: CLI failed (exit 1): You've hit your limit · resets 10pm (America/New_York), trying Gemini fallback...
    - WARNING:memory_janitor:Claude Opus janitor call failed: CLI failed (exit 1): You've hit your limit · resets 10pm (America/New_York), trying Gemini fallback...
  - Fixes:
    - INFO:memory.v1.conversation_manager:Session 'session_1773577035' closed and cleaned up.
    - INFO:memory.v1.conversation_manager:Session 'session_1773599090' closed and cleaned up.
    - INFO:agent_skills.self_improve_log:self_improve_log: recorded [info] Memory Verification — Verified 20 code-related memories one at a time. Skipped 21 recent...
- 8. ⏱ Auto-Commit + Push (post) (2.0m)
  - Fixes:
    - 2026-05-13 01:50:39,025 INFO Committed 6 file(s).

**Top follow-ups:**

- In `jane_web/jane_v3/pipeline.py`, resolve active pending actions before `maybe_idle_flush()`, or exempt unresolved `pending_action` state from the 30s idle flush. Add an explicit log when an idle flush discards a pending follow-up.
- Sanitize `<class_protocol>...</class_protocol>` and other Stage 3 injection blocks before v3 classification, reusing the v2 stripping logic. In `jane_web/jane_v3/pipeline.py`, check `result.get("wrong_class")` before the `'text'` shape gate, or change `jane_web/jane_v2/classes/greeting/handler.py` to return `None` on WRONG_CLASS.

## Executive Summary

- 2 stage(s) need attention because they timed out or exited non-zero.
- 8 concrete improvement/fix signals were found in logs or reports.

## Stage 1: Auto-Commit WIP (pre)

- Status: `ok`
- Duration: 0s (0.0 min)

### What It Did

- Captured any existing local work before the auditors ran, so nightly changes start from a recoverable baseline.

### Problems It Found

- No problems were detected in the available logs/reports.

### Improvements It Made

- 2026-05-13 01:00:01,999 INFO Committed 4 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log

## Stage 2: Code Auditor

- Status: `exit-2`
- Duration: 3s (0.1 min)

### What It Did

- Picked a whitelisted module for deeper test generation and repair.

### Problems It Found

- Job ended with status `exit-2`.
- 2026-05-13 01:00:05,537 [ERROR] Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for jane_web/jane_v2/classes/shopping_list/handler.py', '--no-verify']' returned non-zero exit status 1.

### Improvements It Made

- No concrete improvement was recorded in the available logs/reports.

### Evidence Files

- /home/chieh/ambient/vessence/configs/auto_audit_log.md
- /home/chieh/ambient/vessence/configs/audit_failures.md
- /home/chieh/ambient/vessence-data/logs/self_improve_nightly_code_auditor.log

## Stage 3: Dead Code Auditor

- Status: `ok`
- Duration: 355s (5.9 min)

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
- Duration: 102s (1.7 min)

### What It Did

- Replayed recent real prompts through Stage 1, Stage 2, and Stage 3 to catch routing and response failures. Runs report-only during nightly self-improvement; classifier exemplar auto-fixes require a separate manual --apply-fixes run.

### Problems It Found

- Prompts audited: 12.
- Classification failures: 7.
- Response failures: 12.
- **yes those articles and maybe just two days** (others/stage3): You've hit your limit · resets 10pm (America/New_York)
- **currently how does your short-term memory work** (others/stage3): You've hit your limit · resets 10pm (America/New_York)
- **how about** (greeting/stage3): You've hit your limit · resets 10pm (America/New_York)
- **it seems to me that you are no longing making any sounds when speech to text is ** (others/stage3): You've hit your limit · resets 10pm (America/New_York)

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
- Duration: 214s (3.6 min)

### What It Did

- Read real user transcripts plus server/client logs to identify stage-by-stage failures Jane actually experienced. Runs report-only during nightly self-improvement; code fixes require a separate manual --apply-fixes run.

### Problems It Found

- Transcript review found 5 issues: 3 critical, 2 medium.
- Follow-up answer was not routed through the pending_action_resolver and got reclassified from scratch
- Raw `<class_protocol>` text was misclassified as a real greeting, and the greeting handler's WRONG_CLASS path degraded into an invalid-shape Stage 3 escalation
- A voice/STT bug report took 5.6 minutes to answer, and the client-side behavior could not be verified from the available Android diagnostics
- The user asked to inspect short-term memory while the short-term extractor was repeatedly failing

### Improvements It Made

- 2026-05-13 01:11:17,920 INFO Report written to /home/chieh/ambient/vessence/configs/transcript_review_report.md (5 issues)
- 2026-05-13 01:11:17,921 INFO self_improve_log: recorded [critical] Transcript Review — Reviewing yesterday's conversations I spotted 3 critical, 2 medium issues. The most urgent was: Raw

### Follow-Up Fixes Recommended

- In `jane_web/jane_v3/pipeline.py`, resolve active pending actions before `maybe_idle_flush()`, or exempt unresolved `pending_action` state from the 30s idle flush. Add an explicit log when an idle flush discards a pending follow-up.
- Sanitize `<class_protocol>...</class_protocol>` and other Stage 3 injection blocks before v3 classification, reusing the v2 stripping logic. In `jane_web/jane_v3/pipeline.py`, check `result.get("wrong_class")` before the `'text'` shape gate, or change `jane_web/jane_v2/classes/greeting/handler.py` to return `None` on WRONG_CLASS.
- Add a hard latency budget and smaller-model fallback for meta/diagnostic turns in Stage 3, stop restarting the standing brain on every vault-unlock mismatch, and emit Android `voice_flow` telemetry for TTS end, STT relaunch, beep playback, and relaunch-skipped reasons with the session id.
- Make `memory.v1.short_term_extractor` fail fast to a heuristic fallback instead of waiting 45s, queue extraction fully out-of-band, and surface an explicit `short_term_memory_write_failed` flag to Stage 3 so memory-inspection answers can report degraded state honestly.

### Evidence Files

- /home/chieh/ambient/vessence/configs/transcript_review_report.md
- /home/chieh/ambient/vessence-data/logs/self_improve_transcript_quality_review.log

## Stage 7: Memory Janitor

- Status: `ok`
- Duration: 2360s (39.3 min)

### What It Did

- Cleaned and verified Jane's Chroma memory stores.

### Problems It Found

- WARNING:memory.v1.conversation_manager:Thematic archival failed: [Errno 7] Argument list too long: 'claude'
- WARNING:memory_janitor:Claude Opus janitor call failed: CLI failed (exit 1): You've hit your limit · resets 10pm (America/New_York), trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: CLI failed (exit 1): You've hit your limit · resets 10pm (America/New_York), trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: CLI failed (exit 1): You've hit your limit · resets 10pm (America/New_York), trying Gemini fallback...
- WARNING:memory_janitor:Claude Opus janitor call failed: CLI failed (exit 1): You've hit your limit · resets 10pm (America/New_York), trying Gemini fallback...

### Improvements It Made

- INFO:memory.v1.conversation_manager:Session 'session_1773577035' closed and cleaned up.
- INFO:memory.v1.conversation_manager:Session 'session_1773599090' closed and cleaned up.
- INFO:agent_skills.self_improve_log:self_improve_log: recorded [info] Memory Verification — Verified 20 code-related memories one at a time. Skipped 21 recently verified entries. All checked o

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

- 2026-05-13 01:50:39,025 INFO Committed 6 file(s).

### Evidence Files

- /home/chieh/ambient/vessence-data/logs/self_improve_auto_commit_wip.log
