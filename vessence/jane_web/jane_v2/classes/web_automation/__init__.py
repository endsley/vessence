"""Stage 2 class: web_automation (browser automation).

Routes browser-related intents to the `agent_skills.web_automation`
skill. Phase 1 runs in "delegate to Opus" mode — the handler declines
at the Stage 2 level so Stage 3 takes over with full brain context,
calling the skill's CLIENT_TOOL surface.

See jane_web/jane_v2/classes/README.md for class pack structure.
"""
