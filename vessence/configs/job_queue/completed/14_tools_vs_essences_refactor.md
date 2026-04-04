# Job: Tools vs Essences — Split Architecture

Status: complete
Priority: 1
Created: 2026-03-22

## Objective
Split the current "essences" into two distinct categories: **Tools** (utilities) and **Essences** (AI agents). Refactor the codebase, UI, and marketplace to reflect this distinction.

## Definitions

### Tool
A single-purpose utility that performs a specific function. No LLM brain of its own — just functions/APIs with a UI. Users interact directly (tap, browse, play).

**Current tools (currently mislabeled as essences):**
- Daily Briefing — news aggregator
- Life Librarian — file browser
- Music Playlist — player
- Work Log — activity feed

### Essence
An AI agent with its own persona, reasoning, and multi-step workflow. Has an LLM brain that makes decisions, asks questions, and walks the user through complex tasks. Uses tools to accomplish goals.

**Future essences (don't exist yet):**
- Tax Accountant — walks through taxes, fills forms, generates PDF
- Personal Trainer — creates workout plans, tracks progress, adapts
- Tutor — teaches concepts, quizzes, explains at user's level
- Therapist — guided journaling, mood tracking, CBT exercises

## Changes Required

### 1. Folder Structure
```
~/ambient/tools/           # Renamed from essences/
├── daily_briefing/
├── life_librarian/
├── music_playlist/
└── work_log/

~/ambient/essences/        # New — for true AI agents
├── tax_accountant/
└── (future essences)
```

### 2. Manifest Schema
Add `type` field to `manifest.json`:
```json
{
  "type": "tool",           // or "essence"
  "essence_name": "...",    // keep for backward compat
  "tool_dependencies": [],  // essences declare which tools they need
  "has_brain": false,       // tools: false, essences: true
  "preferred_model": {},    // only for essences
  ...
}
```

### 3. Essence Agent Architecture
An essence needs:
- Its own system prompt / personality
- Ability to call tools (via the tool bridge we built in Job #06)
- Conversation state / workflow state (what step are we on?)
- Decision-making: "should I ask the user for more info or proceed?"
- Output generation: PDFs, forms, reports, etc.

### 4. UI Changes

**Home screen (Android + Web):**
```
Jane (always top)
── Tools ──
Daily Briefing | Life Librarian | Music | ...
── Essences ──
Tax Accountant | Personal Trainer | ...
── Work Log (always bottom) ──
```

**Essence picker dropdown:** separate sections for Tools and Essences

### 5. Jane's Role
- Jane invokes **tools** directly (like a function call)
- Jane delegates to **essences** (like handing off to a specialist)
- When user says "do my taxes", Jane activates the Tax Accountant essence
- When user says "show me my briefing", Jane opens the Daily Briefing tool

### 6. Marketplace
Two categories:
- **Tools**: $0-10, simple utilities, install and use immediately
- **Essences**: $10-100+, complete AI agents, more complex, higher value

### 7. Loader Changes
- `essence_loader.py` → handles both types
- `list_available_essences()` → `list_available(type="all"|"tool"|"essence")`
- Auto-detect type from manifest
- Tools load instantly (no LLM init)
- Essences may need to initialize their brain on first use

## Migration Steps
1. Add `type` field to all existing manifests (default: "tool")
2. Rename `essences/` folder to `tools/` (or keep both dirs)
3. Update all path references (essence_loader, context_builder, main.py, Android)
4. Update home screen UI to show two sections
5. Update essence picker dropdown
6. Update Job #09 (Isolation Framework) to handle both types
7. Build first true essence as proof of concept

## Files Involved
- `agent_skills/essence_loader.py` — type-aware loading
- `jane/context_builder.py` — distinguish tool invocation vs essence delegation
- `jane_web/main.py` — route handling for both types
- `vault_web/templates/jane.html` — essence picker with sections
- `android/.../ui/home/HomeScreen.kt` — two-section layout
- All existing `manifest.json` files — add `type: "tool"`
- `configs/VESSENCE_SPEC.md` — update architecture docs

## Notes
- Backward compatible: if `type` is missing from manifest, default to "tool"
- Jane is neither a tool nor an essence — she's the permanent orchestrator
- Work Log is a tool, not an essence
- An essence can depend on tools but not on other essences (Jane mediates)
- Tools CAN use other tools to accomplish their task (e.g., Daily Briefing uses news fetcher + summarizer + TTS). Tool composition is fine.
- The key distinction is NOT "can it use other tools" — both can. The distinction is: does it have an LLM brain making autonomous decisions? Tools = no brain, just functions. Essences = has a brain, reasons about what to do next.
- Tools are stateless between sessions; essences can maintain workflow state
