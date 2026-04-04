# Job: Tools vs Essences Phase 2 — Folder Split, Android UI, First Essence

Status: completed
Completed: 2026-03-23
Priority: 1
Created: 2026-03-23

## Objective
Complete the tools vs essences architectural split: rename folders, update Android HomeScreen to show two sections, and build the first true AI essence as a proof of concept.

## What's Done (Phase 1)
- All 4 manifests have `type: "tool"` and `has_brain: false`
- essence_loader.py is type-aware with filtering
- /api/essences returns type field, supports ?type= filter
- Web UI (jane.html) splits picker into Tools and Essences sections
- context_builder.py distinguishes invoke (tools) vs delegate (essences)
- VESSENCE_SPEC.md documents the distinction

## Remaining Work

### 1. Folder Rename
- Rename `~/ambient/essences/` → `~/ambient/tools/`
- Create new `~/ambient/essences/` for true AI agents
- Update all path references: essence_loader.py, config.py (ESSENCES_DIR), context_builder.py, jane_web/main.py, cron jobs
- Update docker-compose.yml volume mounts
- Backward compatible: support both dirs during transition

### 2. Android HomeScreen — Two-Section Layout
- Split the home screen into "Tools" and "Essences" sections
- Jane stays at top, Work Log stays at bottom
- Essences get a visual distinction (violet accent like web)
- File: HomeScreen.kt

### 3. Build First True Essence (Proof of Concept)
- Create an essence with `type: "essence"`, `has_brain: true`
- Needs: personality.md, own ChromaDB, custom functions, preferred_model
- The essence should have its own LLM brain that makes decisions
- Validates the full architecture end-to-end

## Open Questions
1. Which essence to build first? (Tax accountant, personal trainer, tutor, or something else?)
2. Should the folder rename happen now, or keep both dirs co-existing?
3. For the first essence, which LLM should be the preferred_model?

## Files Involved
- `agent_skills/essence_loader.py` — path updates
- `jane/config.py` — ESSENCES_DIR update
- `jane_web/main.py` — route updates
- `docker-compose.yml` — volume mounts
- `android/.../ui/home/HomeScreen.kt` — two-section layout
- New essence folder structure

## Notes
- Jane is neither a tool nor an essence — she's the permanent orchestrator
- An essence can depend on tools but not on other essences (Jane mediates)
- Tools are stateless between sessions; essences can maintain workflow state
