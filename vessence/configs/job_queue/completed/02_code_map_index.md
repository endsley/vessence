# Job: Build Code Map Index Generator

Status: complete
Completed: 2026-03-24 11:45 UTC
Notes: Script created (180 lines). Indexes 21 priority files (full) + secondary files (functions only, 150+ lines). Output: 646 lines. Cron at 4:15 AM daily. Spot-checked 5 line numbers — all accurate.
Priority: 2
Model: sonnet
Created: 2026-03-24

## Objective
Build a lightweight Python script that generates a code map index of the Vessence codebase — function names, class definitions, route decorators, and key variables with their line numbers. This eliminates redundant file reads during editing sessions.

## Context
Jane frequently re-reads the same files (jane.html, jane_proxy.py, persistent_claude.py, etc.) to find function locations. A pre-built index would let her jump directly to exact line numbers. The index is pure static analysis — no LLM needed, just `ast.parse()` for Python and regex for HTML/JS.

## Pre-conditions
- None. This is a new standalone script.

## Steps
1. Create `agent_skills/generate_code_map.py` that:
   - Walks key directories: `jane_web/`, `jane/`, `vault_web/templates/`, `agent_skills/`, `amber/`
   - For `.py` files: uses `ast.parse()` to extract function/class definitions + line ranges, route decorators (`@app.get`, `@app.post`), key constants/assignments
   - For `.html` files: uses regex to extract Alpine.js methods, event handler blocks, CSS class definitions, template sections (marked by HTML comments)
   - Outputs to `configs/CODE_MAP.md` in a clean, scannable format
2. Format should be grouped by file, e.g.:
   ```
   ## jane_web/jane_proxy.py (2100 lines)
     emit() → L691-696 — Queue event emitter
     stream_message() → L670-910 — Main streaming entry point
     _classify_intent() → L700-740 — Intent classification wrapper
     POST /api/jane/chat/stream → L793
   ```
3. Add a daily cron job at 4:15 AM: `generate_code_map.py >> logs/code_map.log 2>&1`
4. Script should also be callable on-demand (Jane runs it after code edit sessions)
5. Output file should be kept under 500 lines — focus on the most-edited files, skip test files and one-off scripts

## Verification
- `python agent_skills/generate_code_map.py` runs without error
- `configs/CODE_MAP.md` exists and contains indexed entries for at least: `jane_proxy.py`, `persistent_claude.py`, `persistent_gemini.py`, `jane.html`, `main.py`, `intent_classifier.py`
- Cron job is added to crontab
- Index is accurate: spot-check 5 function line numbers against actual files

## Files Involved
- `agent_skills/generate_code_map.py` (new)
- `configs/CODE_MAP.md` (new, generated output)
- crontab (add entry)
- `configs/CRON_JOBS.md` (update registry)

## Notes
- No LLM required — pure `ast` + regex parsing
- Keep it fast: should complete in under 2 seconds
- Skip `__pycache__`, `.pyc`, `node_modules`, `omniparser/`
- For HTML: look for `x-data`, `function`, method definitions inside Alpine components
- Jane will call this script after editing sessions to keep the index fresh
