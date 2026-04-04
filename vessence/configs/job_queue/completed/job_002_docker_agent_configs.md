# Job #2: Docker Installer — Bundle Agent Config Files

Priority: 2
Status: completed
Created: 2026-04-03

## Description
The Docker/Windows installer must include and overwrite agent instruction files so all AI agents behave consistently out of the box.

### Files to bundle:
1. **CLAUDE.md** → `~/CLAUDE.md` — Claude Code runtime rules
2. **GEMINI.md** → `~/.gemini/GEMINI.md` — Gemini CLI runtime rules
3. **AGENTS.md** → `~/AGENTS.md` — OpenAI Codex runtime rules

### Key rules in all three:
- Code edit lock (`agent_skills/code_lock.py`) — prevents concurrent edits
- Android version bumping — always use `bump_android_version.py`
- Resource limits — no Ollama models >16GB on 32GB machines
- Server restart policy — no restart for build-only tasks
- Communication style — user preferences enforced

### Implementation:
- Add the three .md files to `startup_code/build_docker_bundle.py` package list
- On install, copy them to the correct locations (with backup of existing)
- On update, overwrite to ensure new rules propagate
- Template the user-specific fields (name, preferences) for first-run onboarding

### Acceptance criteria:
- Fresh Docker install has all three agent configs in place
- Agent configs survive Docker container restarts
- User customizations to communication style are preserved across updates (template merge, not blind overwrite)
