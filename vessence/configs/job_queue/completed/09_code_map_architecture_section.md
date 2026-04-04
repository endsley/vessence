# Job: Add Architecture Summary Section to CODE_MAP.md

Status: complete
Completed: 2026-03-24 14:30 UTC
Notes: Added ~50 line architecture section to CODE_MAP.md covering request lifecycle, model routing, persistent sessions, memory flow, cron pipeline, and key directories. Updated generate_code_map.py to preserve content above AUTO-GENERATED marker.
Priority: 3
Model: sonnet
Created: 2026-03-24

## Objective
Add a hand-written "Architecture" section at the top of CODE_MAP.md showing how the pieces connect — request lifecycle, memory flow, cron pipeline, persistent sessions. The auto-generated function index covers "where is this function" but not "how do these files interact."

## Steps
1. Add a `# Architecture` section above the auto-generated index
2. Document key flows: web request lifecycle, memory retrieval, cron pipeline, persistent sessions, intent classification → model routing
3. Modify `generate_code_map.py` to preserve the architecture section across regenerations (write below a `<!-- AUTO-GENERATED BELOW -->` marker)
4. Keep architecture section under 50 lines

## Files Involved
- `configs/CODE_MAP.md`
- `agent_skills/generate_code_map.py`
