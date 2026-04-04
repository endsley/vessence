# Job: Settings Page — Per-Complexity Model Picker

Status: completed
Priority: 1
Model: opus
Created: 2026-03-25

## Objective
Add a model selection UI to Jane's settings page that lets users choose which LLM model to use for each complexity level (light/medium/heavy). Jane should also be able to recommend models based on the task type.

## UI Design

### Location
In the Jane web settings page (or onboarding settings at localhost:3000), add a "Brain Configuration" section.

### Layout
Show 3 rows, one per complexity level:

```
┌─────────────────────────────────────────────────┐
│  Brain Configuration                             │
│                                                  │
│  Simple tasks (greetings, quick answers)          │
│  [dropdown: gemini-2.5-flash ▼]                  │
│                                                  │
│  Medium tasks (code questions, analysis)           │
│  [dropdown: gemini-2.5-pro ▼]                    │
│                                                  │
│  Complex tasks (research, architecture, debugging) │
│  [dropdown: gemini-2.5-pro ▼]                    │
│                                                  │
│  [Save] [Reset to Defaults]                      │
└─────────────────────────────────────────────────┘
```

### Dropdown options per provider
**Claude:**
- claude-haiku-4-5-20251001 (fast, cheap)
- claude-sonnet-4-6 (balanced)
- claude-opus-4-6 (most capable)

**Gemini:**
- gemini-2.5-flash (fast, cheap)
- gemini-2.5-pro (most capable)

**OpenAI:**
- gpt-4.1-mini (fast, cheap)
- gpt-4.1 (balanced)
- o3 (most capable)

### Model recommendations
Add a small "ℹ️ Recommended" badge next to the default/suggested model for each level. Jane can query the current provider and show which models are available.

## Implementation

### Frontend
- Add the model picker UI to settings page (settings.html or jane.html settings panel)
- Read current values from env vars: `BRAIN_LIGHT_*`, `BRAIN_MEDIUM_*`, `BRAIN_HEAVY_*`
- Save via API endpoint

### Backend
- Add `GET /api/settings/models` — returns current model config and available options per provider
- Add `POST /api/settings/models` — saves the 3 model selections to .env
- The env vars are: `BRAIN_LIGHT_CLAUDE`, `BRAIN_MEDIUM_CLAUDE`, `BRAIN_HEAVY_CLAUDE` (and _GEMINI, _OPENAI variants)

### Standing brain restart
After saving model changes, the standing brains need to restart to pick up new models. Add a "Restart Brain" button or auto-restart on save.

## Verification
- Settings page shows current model for each level
- User can change models via dropdowns
- Save persists to .env
- Standing brains use the new models after save
- Default recommendations are shown

## Files Involved
- `vault_web/templates/jane.html` (settings panel) or `onboarding/templates/settings.html`
- `jane_web/main.py` (new API endpoints)
- `jane/standing_brain.py` (reads env vars — already does this)
- `.env` (stores overrides)
