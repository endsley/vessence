"""Web automation skill — Phase 1 MVP.

Jane's browser-automation surface. Phase 1 exposes a deterministic action
set (navigate, click, fill, press, select, wait, extract, download,
screenshot) on top of a Playwright Chromium session. The semantic
reasoning layer is Opus (Stage 3 brain); a dedicated semantic module
lands in Phase 2.

Entry point for Jane: :func:`agent_skills.web_automation.skill.run_task`.

Module map:
  - browser_session.py  Singleton Playwright browser + per-task context
  - snapshot.py         Accessibility-tree snapshots + compact refs
  - actions.py          Typed deterministic action registry
  - safety.py           Risk classifier, domain allowlist, confirm gates
  - artifacts.py        Run dirs, traces, redaction, retention
  - skill.py            Orchestrator called by jane_v2/classes/web_automation/handler.py

See configs/project_specs/web_automation_skill.md for the full spec.
"""

__all__ = [
    "actions",
    "artifacts",
    "browser_session",
    "safety",
    "skill",
    "snapshot",
]
