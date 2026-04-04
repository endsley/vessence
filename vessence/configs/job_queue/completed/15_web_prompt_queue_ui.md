# Job: Web Prompt Queue UI — Match Android Queue Panel on Jane Web

Status: complete
Completed: 2026-03-22
Notes: Fully implemented in jane.html (Alpine.js drawer with add/delete/reorder/retry/voice input) and jane_web/main.py (5 API endpoints). Matches Android functionality.
Priority: 2
Created: 2026-03-22

## Objective
The Android app has a prompt queue management panel (slide-out drawer with add/reorder/delete/retry). The web Jane chat page has the drawer skeleton built (Job #05) but needs verification and parity with Android.

## What exists (web)
- Slide-out drawer toggled by list icon in header
- Add prompt input with voice mic button
- List with status badges (green/grey/orange)
- Move up/down buttons for pending prompts
- Delete and retry buttons
- Auto-loads on open

## What needs verification/fixing
1. Verify the drawer actually opens and loads prompts from `/api/prompts/list`
2. Verify add/delete/reorder/retry work end-to-end
3. Match Android's visual style (compact rows, status dots, hover actions)
4. Add voice input for adding prompts (Web Speech API — already has mic button)
5. Test with actual prompt queue data

## Key Code Locations
- `vault_web/templates/jane.html` — search for "Prompt Queue Drawer" — slide-out panel with Alpine.js
  - `queueOpen`, `queuePrompts`, `queueNewText` state vars in `janeApp()`
  - `loadQueue()`, `addQueuePrompt()`, `deleteQueuePrompt()`, `retryQueuePrompt()`, `reorderQueue()` methods
  - Voice input mic button using Web Speech API
- `jane_web/main.py` — API endpoints already registered:
  - `GET /api/prompts/list` — returns `{"prompts": [{"index", "status", "text"}]}`
  - `POST /api/prompts/add` — body: `{"text": "..."}`
  - `DELETE /api/prompts/delete/{index}`
  - `POST /api/prompts/retry/{index}`
  - `POST /api/prompts/reorder` — body: `{"order": [3, 1, 2]}`
- Backend logic: `agent_skills/prompt_queue_runner.py` — `load_prompts()`, `add_prompt()`, `delete_prompt()`, `_renumber_prompts()`
- Prompt file: `vault/documents/prompt_list.md`

## What to verify
1. Open drawer (list icon in header) → does it load prompts?
2. Add a test prompt → does it appear?
3. Delete → does it remove and renumber?
4. Reorder arrows → do they swap correctly?
5. Retry button on incomplete → does it reset to [new]?
6. Voice mic button → does Web Speech API transcribe and fill input?
