# Job: Self-Healing Nightly Audit — Auto-Fix Issues Found During Audit

Status: complete
Priority: 1
Created: 2026-03-22

## Objective
Transform the nightly audit from a read-only diagnostic into a self-healing system. When the audit identifies problems, Jane should automatically fix them in the same run, then write defensive code to prevent the same class of issue from recurring.

## Context
The current nightly audit (`agent_skills/nightly_audit.py`, runs at 1 AM) does three things:
1. Gathers system state (crontab, skill files, architecture docs)
2. Sends it to an LLM to produce an audit report (code vs docs alignment, code quality)
3. Saves the report to `logs/audits/audit_YYYY-MM-DD.md`

The problem: **it stops at diagnosis.** The report lists real issues (stale docs, wrong paths, undocumented crons, dead code) but nobody acts on them. The March 22 audit found 5 actionable issues — none were fixed automatically.

This violates a core mandate from Chieh: "When Jane discovers a bug or problem, she must IMMEDIATELY and AUTOMATICALLY: 1) Identify the permanent root-cause solution, 2) Implement the fix, 3) Write defensive code to prevent the same class of bug from recurring."

## Design

### Phase 1: Audit → Fix Pipeline

Change the audit flow from:
```
gather state → LLM diagnoses → save report → done
```
To:
```
gather state → LLM diagnoses → categorize issues → auto-fix safe issues → verify fixes → save report with fix log → done
```

### Issue Categories and Auto-Fix Rules

**Category A — Auto-fix immediately (no human approval needed):**
- Documentation out of sync with code (stale paths, missing cron entries, wrong descriptions)
- Dead/vestigial env vars in crontab
- Undocumented cron jobs (add them to CRON_JOBS.md)
- Stale file references in config docs

**Category B — Auto-fix with verification:**
- Cron ordering issues (reorder and verify no side effects)
- Dead migration scripts (move to archive, verify nothing imports them)
- Config inconsistencies (fix and restart affected services)

**Category C — Flag for human review (do NOT auto-fix):**
- Security issues
- Architecture changes
- Anything that would change user-facing behavior
- Anything that requires deleting user data

### Implementation Steps

#### 1. Restructure the audit prompt
Instead of asking for a free-text report, ask the LLM to return **structured JSON**:
```json
{
  "health_summary": "...",
  "issues": [
    {
      "id": "DOC_PATH_STALE",
      "category": "A",
      "severity": "medium",
      "description": "CRON_JOBS.md references /home/chieh/vessence/ but actual path is /home/chieh/ambient/vessence/",
      "file": "configs/CRON_JOBS.md",
      "fix_action": "replace_path",
      "fix_details": {"old": "/home/chieh/vessence/", "new": "/home/chieh/ambient/vessence/"}
    }
  ]
}
```

#### 2. Build a fix executor
A function that takes an issue JSON and executes the fix based on `fix_action`:
- `replace_path` — sed-style replacement in the target file
- `add_cron_doc_entry` — append a new entry to CRON_JOBS.md
- `remove_env_var` — remove a line from crontab env block
- `move_file` — move dead scripts to archive directory
- `reorder_cron` — adjust cron schedule times

Each fix action must:
1. Back up the file before modifying
2. Apply the change
3. Verify the change (re-read and confirm)
4. Log what was done

#### 3. Build a verification pass
After all Category A and B fixes are applied, re-run a lighter audit prompt to confirm:
- Fixed issues no longer appear
- No new issues were introduced

#### 4. Build defensive guards
For each class of fix, add a **permanent check** that prevents the issue from recurring:

- **Path drift** — add a startup/cron check that verifies all paths in config docs match the env vars. If mismatch detected, auto-fix and log.
- **Undocumented crons** — after any crontab modification, auto-run a sync that updates CRON_JOBS.md.
- **Dead code accumulation** — track migration scripts with a manifest; flag any that are older than 30 days and still in agent_skills/.

#### 5. Report format
The saved report should now include:
```markdown
# Nightly Audit — YYYY-MM-DD

## Health Summary
...

## Issues Found: N
## Auto-Fixed: M
## Flagged for Review: K

### Auto-Fixed Issues
| Issue | Category | Fix Applied | Verified |
|---|---|---|---|
| Stale paths in CRON_JOBS.md | A | Replaced /home/chieh/vessence → /home/chieh/ambient/vessence | Yes |

### Flagged for Review
| Issue | Category | Why Not Auto-Fixed |
|---|---|---|
| ... | C | Requires architecture decision |

### Defensive Guards Added
- Added path consistency check to nightly audit
```

## Files Involved
- `agent_skills/nightly_audit.py` — main audit script, needs restructuring
- `configs/CRON_JOBS.md` — frequently found stale
- `configs/SKILLS_REGISTRY.md` — frequently found stale
- `configs/Jane_architecture.md` — path references
- `configs/memory_manage_architecture.md` — path references

## Fix & Improve
- If the structured JSON approach doesn't work reliably, fall back to regex parsing of the free-text report
- If a fix introduces a regression, the verification pass should catch it and roll back
- Consider rate-limiting fixes per night (e.g., max 10 auto-fixes) to avoid runaway changes
- Log every fix to a persistent audit trail so Chieh can review what was changed

## Notes
- The automation runner (`jane/automation_runner.py`) is what executes the LLM call — check its timeout and model settings
- Category C items should be surfaced prominently — consider adding them to the work log or a "needs attention" file that Chieh sees
- The nightly audit already has access to `run_automation_prompt()` — the fix executor can use the same mechanism for complex fixes that need LLM reasoning
- Backup files before any modification — store in `logs/audits/backups/YYYY-MM-DD/`
