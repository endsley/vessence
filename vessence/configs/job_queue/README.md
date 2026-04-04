# Job Queue

Jobs are complex tasks with full context that any session can execute cold.
Each job is a self-contained markdown file with everything needed to complete the work.

## Structure

Each job file: `{priority}_{short_name}.md` (e.g., `01_docker_e2e_test.md`)

## Job Format

```markdown
# Job: {title}
Status: [pending|in_progress|completed|blocked]
Priority: [1-5] (1 = highest)
Created: {date}

## Objective
One sentence: what needs to be done and why.

## Context
Background that a cold session needs to understand the job.
Reference relevant spec files, architecture docs, or code paths.

## Pre-conditions
What must be true before this job can run.

## Steps
Numbered, concrete steps. Each step should be independently verifiable.

## Verification
Exact commands or checks to confirm the job is done correctly.

## Files Involved
List of files that will be read or modified.

## Notes
Any gotchas, edge cases, or decisions already made.
```

## Auto-Archiving

When completed jobs exceed 10, they are automatically moved to `completed/`.
Jane runs this check after marking any job as complete.

## Commands

- `run job queue:` — Jane picks the highest-priority pending job and executes it
- `show job queue:` — Jane shows all jobs as a table
- `add job:` — Jane creates a new job file from the conversation context
