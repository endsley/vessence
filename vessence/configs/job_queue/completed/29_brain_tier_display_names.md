# Job: Use Model Names Instead of Tier Names in Work Log

Status: completed
Priority: 2
Model: sonnet
Created: 2026-03-25

## Objective
In work log entries and crash alerts, display the actual LLM model name (e.g., "opus", "sonnet", "haiku") instead of the internal tier names ("heavy", "medium", "light"). The display name should change based on the active provider (Claude → opus/sonnet/haiku, Gemini → pro/flash, OpenAI → o3/gpt-4.1/gpt-4.1-mini).

## Current Behavior
Work log shows: `CRASH: Standing Brain [heavy] — found dead`

## Desired Behavior
Work log shows: `CRASH: Standing Brain [opus] — found dead`
Or for Gemini: `CRASH: Standing Brain [gemini-2.5-pro] — found dead`

## Implementation
1. In `standing_brain.py`, update `_log_crash()` and log messages to use `bp.model` (which already holds the actual model name) instead of `tier`
2. Update `health_check()` response to include both tier and model name
3. Any other places that reference tier names in user-visible output should use the model name instead

## Verification
- Work log crash alerts show model name, not tier name
- Health check endpoint shows model names
- Log messages use model names in user-visible contexts

## Files Involved
- `jane/standing_brain.py` — update logging to use `bp.model`
