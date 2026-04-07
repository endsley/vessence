# Job: Prompt Queue Management UI — Panel Inside Jane Chat Page

Status: complete
Priority: 2
Created: 2026-03-22

## Objective
Build a prompt queue management UI as a panel/section inside the Jane chat page, so the user can view, reorder, and delete queued prompts without editing the raw markdown file.

## Context
The prompt queue (`vault/documents/prompt_list.md`) is the autonomous task queue that Jane processes via `prompt_queue_runner.py`. Currently:
- **Backend logic exists**: `prompt_queue_runner.py` has `load_prompts()`, `delete_prompt()`, `_renumber_prompts()`
- **No dedicated UI**: the only way to manage the queue is editing the raw markdown file through the vault file editor
- **The user wants**: a panel inside the Jane chat page (option B) with drag-to-reorder and one-click delete

## Design

### API Endpoints (add to `jane_web/main.py`)

#### `GET /api/prompts/list`
Returns all prompts with their index, status, and text.
```json
{
  "prompts": [
    {"index": 1, "status": "new", "text": "Fix the login page..."},
    {"index": 2, "status": "completed", "text": "Add latex support..."},
    {"index": 3, "status": "incomplete", "text": "Reindex vault files..."}
  ]
}
```

#### `POST /api/prompts/reorder`
Accepts a new ordering of prompt indices.
```json
{"order": [3, 1, 2]}
```
Rewrites `prompt_list.md` with the new order, preserving status and text.

#### `DELETE /api/prompts/delete/{index}`
Deletes a prompt by index and renumbers the remaining ones.

#### `POST /api/prompts/add`
Adds a new prompt to the queue.
```json
{"text": "New task description here"}
```

#### `POST /api/prompts/retry/{index}`
Resets an `[incomplete]` prompt back to `[new]` so it gets retried.

### UI Panel (add to `vault_web/templates/jane.html`)

#### Location
A collapsible panel accessible from the Jane chat page — either:
- A sidebar drawer (slide in from right)
- Or a toggle panel below the header

#### Features
1. **List view**: shows all prompts with status badges (`[new]` green, `[completed]` grey, `[incomplete]` orange)
2. **Drag to reorder**: drag handle on each `[new]` prompt to change priority order
3. **One-click delete**: trash icon on each prompt
4. **Add new**: text input at the top to add a new prompt
5. **Retry**: button on `[incomplete]` prompts to reset them to `[new]`
6. **Filter**: toggle to show/hide completed prompts (default: hide completed)
7. **Auto-refresh**: poll `/api/prompts/list` every 30s to reflect queue runner progress

#### Visual Design
- Match the existing Jane chat page dark theme
- Compact rows — prompt text truncated with ellipsis, expand on click
- Status badges: `[new]` = green dot, `[completed]` = grey checkmark, `[incomplete]` = orange warning
- Drag handle: `⠿` grip icon on the left of each row

### Backend Implementation

#### Parsing `prompt_list.md`
Use the existing `load_prompts()` from `prompt_queue_runner.py`. It returns a list of dicts with `index`, `status`, and `text`.

#### Reorder logic
1. Read all prompts
2. Reorder according to the provided index list
3. Renumber sequentially starting from 1
4. Write back to `prompt_list.md` preserving the exact format

#### Delete logic
Use existing `delete_prompt()` and `_renumber_prompts()`.

### Android Parity
The Android app should have the same queue management:
- Accessible from a menu item or panel in Jane's chat screen
- Same API endpoints
- Same features: list, reorder, delete, add, retry

## Files Involved
- `jane_web/main.py` — new API endpoints
- `vault_web/templates/jane.html` — new UI panel
- `agent_skills/prompt_queue_runner.py` — existing backend logic to reuse
- Android chat screen — queue panel

## Notes
- All endpoints require auth (use existing `require_auth` dependency)
- The queue runner processes `[new]` items every 5 minutes — the UI should show a "processing..." indicator if a prompt is currently being worked on
- Consider adding a "run now" button that triggers immediate processing of the next `[new]` prompt
- Drag-to-reorder should only work on `[new]` prompts — completed/incomplete stay in place
