# Job: Evolving Code Map Trigger Keywords via Nightly Cron

Status: completed
Priority: 2
Model: sonnet
Created: 2026-03-25

## Objective
Write a cron job that runs at 2:10 AM daily, reads that day's conversations from the SQLite ledger, identifies messages that were code-related (where the code map would have been useful), and updates the `CODE_MAP_KEYWORDS` tuple in `jane_web/jane_proxy.py` so the keyword list evolves as the codebase and conversation patterns change.

## How it should work

### 1. Read today's conversations
- Query `conversation_history_ledger.db` for all turns from the current day
- Extract user messages (role = "user")

### 2. Identify code-related messages
- Use the current `CODE_MAP_KEYWORDS`, `TASK_KEYWORDS`, and `AI_CODING_KEYWORDS` as a baseline
- Also check if any message references:
  - File names that appear in the code map (e.g., `jane_proxy.py`, `context_builder.py`)
  - Function/class names from `CODE_MAP_CORE.md`
  - New component names, new files, or new tools added to the codebase
- Use a local LLM (cheap model) to classify borderline messages as code-related or not

### 3. Extract new keywords
- From the identified code-related messages, extract words/phrases that are NOT already in the keyword lists
- Filter out common English words, pronouns, and filler
- Keep only words that appear in 2+ code-related messages (to avoid one-off noise)

### 4. Update the keyword list
- Read `jane_web/jane_proxy.py`
- Parse the `CODE_MAP_KEYWORDS` tuple
- Append new keywords (don't remove existing ones)
- Write the updated tuple back to the file
- Log what was added

### 5. Restart Jane web
- `systemctl --user restart jane-web.service` to pick up the new keywords

## Schedule
- Cron: `10 2 * * *` (2:10 AM daily, after USB sync at 2:00)
- Script: `agent_skills/evolve_code_map_keywords.py`

## Verification
- Script runs without error
- New keywords appear in `CODE_MAP_KEYWORDS` after a day with code conversations
- No false positives (common words like "the", "ok" are not added)
- Jane web restarts successfully after update
- Log output shows what was added and why

## Files Involved
- `agent_skills/evolve_code_map_keywords.py` (new)
- `jane_web/jane_proxy.py` (updated by script)
- `configs/CRON_JOBS.md` (add entry)
- crontab (add 2:10 AM schedule)
