# Job: Jane Responds After Each Job Completion

Status: completed
Priority: 1
Model: sonnet
Created: 2026-03-25

## Objective
When Jane processes multiple jobs in sequence (e.g., "run the job queue"), she should send a visible response to the user after completing each job — not stay silent until the entire queue is done. This serves two purposes:
1. User sees progress instead of hours of silence
2. The brain's `last_used` timestamp stays fresh, preventing the CPU reaper from killing an actively working brain

## Current Behavior
Jane processes all jobs silently, only responding once at the very end (or timing out).

## Desired Behavior
After each job completes, Jane sends a message to the chat like:
```
Job #28 completed: Rebuild Docker Package v0.0.43
- Built Jane and Onboarding images
- Security scan passed
- Package size: 245 MB
```
Then moves to the next job.

## Implementation
1. In the job queue execution flow, after each job is marked complete, emit a chat response summarizing what was done
2. This should work for both web (streaming SSE) and prompt queue (CLI) paths
3. The response should include: job number, title, and 2-3 bullet points of what changed
4. Also log to the work log via `log_activity()` (Job #27 already added this rule)

## Where to implement
- Check how `run prompt list:` works in CLAUDE.md — it already has a per-item display pattern (`**[Queue Mode → Prompt #N of M]:** [text]`). Apply the same pattern to job queue execution.
- The job queue runner (or the CLAUDE.md rule for `run job queue:`) should enforce per-job responses.

## Verification
- Running "do the job queue" with 3 pending jobs produces 3 separate visible responses
- Each response shows job number, title, and summary
- Brain `last_used` updates after each job (check logs)
- Work log shows completion entries for each job

## Files Involved
- `CLAUDE.md` — update `run job queue:` instructions to require per-job responses
- Possibly `agent_skills/show_job_queue.py` or a new runner script
