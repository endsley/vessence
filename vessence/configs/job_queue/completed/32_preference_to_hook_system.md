# Job: Code-Enforced Preference System

Status: completed
Priority: 1
Model: opus
Created: 2026-03-25

## Objective
When the user states a preference that can be enforced by code (format, display, workflow), Jane modifies the relevant code immediately and registers the change. Behavioral/tone preferences stay in ChromaDB as-is — no change there.

## Scope: Only codifiable preferences
Examples that qualify:
- "show job queue with summary columns" → edit `show_job_queue.py`
- "use code map before reading code" → already done (code map injection)
- "always run tests after editing" → add post-edit hook
- "file references should be filename only, not full path" → edit output formatting

Examples that do NOT qualify (stay in ChromaDB):
- "be more concise" → behavioral, LLM-only
- "don't call me Professor" → behavioral
- "warm and friendly tone" → behavioral

## How it works

### 1. Detection
Jane recognizes a codifiable preference when:
- The user describes a specific output format
- The user describes a workflow rule ("always X before Y", "never do X without Y")
- The user references a specific script, display, or output behavior

### 2. Enforcement
Jane modifies the relevant code right then — same as any code change in the conversation.

### 3. Registry
After making the change, Jane appends to `$VESSENCE_DATA_HOME/preference_registry.json`:
```json
{
  "id": "job_queue_format",
  "description": "Job queue shows columns: #, Job, Summary, Status, Result",
  "enforcement": "code_change",
  "file_changed": "agent_skills/show_job_queue.py",
  "created": "2026-03-25"
}
```

The registry is for awareness only — so Jane in future sessions knows what preferences exist and where they're enforced, and doesn't accidentally undo them.

### 4. CLAUDE.md rule
Add to CLAUDE.md:
```
## Preference Enforcement
When the user states a preference that can be enforced by code:
1. Modify the relevant code immediately
2. Register in $VESSENCE_DATA_HOME/preference_registry.json
3. Confirm: "Preference enforced in [file]. Registered."
Before editing a file, check the preference registry to avoid undoing existing preferences.
```

## What to implement
1. Create `$VESSENCE_DATA_HOME/preference_registry.json` (empty array to start)
2. Add the CLAUDE.md rule
3. Implement the first real preference: update `show_job_queue.py` to use summary/status/result columns
4. Register it in the registry

## Verification
- `show_job_queue.py` outputs the preferred format
- Registry contains the entry
- Future sessions can read the registry to know what preferences exist

## Files Involved
- `$VESSENCE_DATA_HOME/preference_registry.json` (new)
- `CLAUDE.md` (add preference rule)
- `agent_skills/show_job_queue.py` (first preference enforcement)
