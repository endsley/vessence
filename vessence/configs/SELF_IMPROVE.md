# Nightly Self-Improvement System

Jane runs a pipeline of self-improvement jobs every night at **1:00 AM** via the
`nightly_self_improve.py` orchestrator. This document describes what each job
does, where its artifacts live, and how Jane surfaces the results to the user.

## Cron Entry

```
0 1 * * * /home/chieh/google-adk-env/adk-venv/bin/python \
    $VESSENCE_HOME/agent_skills/nightly_self_improve.py \
    >> $VESSENCE_DATA_HOME/logs/self_improve_orchestrator.log 2>&1
```

## Jobs (ordered, each with a timeout)

| # | Job | Script | Timeout |
|---|-----|--------|---------|
| 1 | Dead Code Auditor | `agent_skills/dead_code_auditor.py` | 15 min |
| 2 | Code Auditor | `agent_skills/nightly_code_auditor.py` | 30 min |
| 3 | Pipeline Audit (30 prompts) | `agent_skills/pipeline_audit_100.py --n 30` | 20 min |
| 4 | Doc Drift Auditor | `agent_skills/doc_drift_auditor.py` | 5 min |
| 5 | Transcript Quality Review | `agent_skills/transcript_quality_review.py` | 20 min |

### What each one does

- **Dead Code Auditor** — Scans `agent_skills/`, `jane_web/`, etc. for
  orphan files / unreachable functions. Removes obvious dead code; flags
  ambiguous cases in `configs/dead_code_report.md`.
- **Code Auditor** — Rotates through the whitelist in
  `configs/auditable_modules.md`, picks one module per night, generates
  stress tests via Claude Opus, runs them, commits fixes on a branch.
  Safety gate: only runs when the working tree is clean *except* for
  expected nightly report files.
- **Pipeline Audit** — Replays the last 30 user prompts through the v2
  3-stage pipeline, uses a local LLM as judge, auto-corrects obvious
  misclassifications by adding exemplars to ChromaDB. Harder issues go to
  `configs/pipeline_audit_report.md`.
- **Doc Drift Auditor** — Compares `configs/*.md` (cron registry,
  pipeline class map, SKILLS_REGISTRY, etc.) against reality (crontab,
  `_CLASS_MAP`, `agent_skills/*.py`). Auto-fixes safe drift, flags rest
  in `configs/doc_drift_report.md`.
- **Transcript Quality Review** — Two stage:
  1. Codex reads yesterday's conversations + pipeline/client logs,
     evaluates each stage (Gemma classifier → handler → Opus → client),
     and writes `configs/transcript_review_report.md`.
  2. Claude validates each issue against the code, implements the fix,
     and writes a unit test for each fix (so regressions can't recur).

## Artifacts

### Logs
- `$VESSENCE_DATA_HOME/logs/self_improve_orchestrator.log` — per-job
  start/done/timeout.
- `$VESSENCE_DATA_HOME/logs/self_improve_<script_stem>.log` — stdout +
  stderr from each job.

### Reports
- `configs/dead_code_report.md`
- `configs/pipeline_audit_report.md`
- `configs/doc_drift_report.md`
- `configs/transcript_review_report.md`
- `configs/self_improve_log.md` — summary of each orchestrator run.
- `configs/auto_audit_log.md` — Code Auditor module-by-module history.
- `configs/audit_failures.md` — Code Auditor runs that couldn't complete.

### Vocal summary log (TTS-friendly — for Jane to answer the user)

**`$VESSENCE_DATA_HOME/self_improve_vocal_log.jsonl`**

JSONL, one entry per logged event:

```json
{
  "timestamp": "2026-04-16T01:15:00Z",
  "job": "Transcript Review",
  "severity": "medium",
  "summary": "I reviewed yesterday's conversations and spotted 3 medium issues...",
  "what_was_wrong": "...",
  "why_it_mattered": "...",
  "what_was_done": "..."
}
```

Each entry's `summary` is a pre-composed 1-3 sentence spoken-style
paragraph — no code, no jargon, no symbols that sound awkward aloud.
Every self-improve job calls `agent_skills/self_improve_log.log_vocal_summary()`
when it does meaningful work (successful fix, finding, failure).

## How Jane answers the user

When the user asks "what did you fix last night?" or similar, the flow is:

1. **Stage 1 classifier** tags the intent as `self improvement` (exemplars
   in `jane_web/jane_v2/classes/self_improvement/metadata.py`).
2. **Stage 2 handler** in `jane_web/jane_v2/classes/self_improvement/handler.py`
   declines immediately — this class is designed for Stage 3.
3. **Pipeline** injects a `[SELF IMPROVEMENT CONTEXT]` block into Opus's
   prompt containing the vocal-summary log path and the last ~20 entries
   from the past 14 days.
4. **Stage 3 (Opus)** picks the 1-3 most relevant summaries and speaks
   them conversationally. For older or specific runs not in the injected
   context, Opus reads the JSONL file directly.

## Adding a new self-improve job

1. Write the script in `agent_skills/`. Make it accept a timeout via its
   own arg parser if needed, and a `--force` override if it has a
   sleep-window check.
2. At the end of the script's main, call
   `agent_skills.self_improve_log.log_vocal_summary(...)` with a short
   TTS-friendly summary of what the job did.
3. Append an entry to the `JOBS` list in
   `agent_skills/nightly_self_improve.py` — `(name, script, args, timeout_min)`.
4. Add a row to this document's table above.

## Operational notes

- **Git-clean gate**: `nightly_code_auditor.py` branches off master, so it
  requires a clean working tree. Nightly report files from earlier jobs
  in the same run are auto-stashed (not treated as WIP) so the auditor
  can proceed. See `is_clean_working_tree()` in the auditor for the list
  of expected transient outputs.
- **Sleep window**: Code Auditor only runs 1-7 AM (uses Opus, which is
  expensive + slow). Use `--force` to bypass for manual runs.
- **Stash roll-up**: the orchestrator stashes any pre-existing WIP at
  the start of the run and tries to `stash pop` at the end. If pop
  fails (conflict with report files), the stash is preserved for
  manual recovery — check `git stash list`.
