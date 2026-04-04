# Job: Fix "Background task failed: No response" Error

Status: completed
Priority: 1
Model: opus
Created: 2026-03-25

## Objective
Jane web sometimes shows "⚠️ Background task failed: No response" to the user. Investigate the cause and fix it.

## Investigation needed
1. Search for "Background task failed" and "No response" in the codebase to find where this error originates
2. Identify what "background task" this refers to — likely the standing brain, persistent claude, or an offloaded task
3. Check the logs for recent occurrences and what preceded them
4. Determine root cause: timeout? brain died? empty response?

## Fix
- Add proper error handling so the user gets a meaningful error message
- If the brain returned empty, retry once before showing an error
- If it's a timeout, show a more specific message

## Verification
- The generic "No response" error no longer appears
- User gets actionable error messages when something fails
- Background tasks that fail are logged with enough detail to debug

## Files Involved
- `jane_web/jane_proxy.py` (likely source of the error)
- `jane/standing_brain.py` (if brain-related)
- `jane/brain_adapters.py` (if adapter-related)
