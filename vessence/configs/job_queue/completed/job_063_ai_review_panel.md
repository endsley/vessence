# Job #63: AI Review Panel — Multi-Model Consultation Tool

Priority: 2
Status: completed
Created: 2026-03-31

## Description
Build a `consult_panel.py` tool that queries Claude, Gemini, and OpenAI in parallel with a problem description + proposed solution, then synthesizes their perspectives into a unified recommendation.

### How It Works
1. Takes a problem description and (optionally) a proposed approach
2. Sends to all three models in parallel via their APIs
3. Each model reviews the approach and suggests improvements or alternatives
4. Synthesizes: agreements, disagreements, edge cases, and a final recommendation
5. Returns a concise summary Jane can use to make better decisions

### When to Use
- **Architecture decisions** — no single "right" answer, get multiple perspectives
- **Complex debugging** — after 2-3 failed attempts, get fresh eyes
- **Pre-implementation review** — before writing 50+ lines, validate the approach
- **Post-implementation code review** — after writing critical code, have others review for:
  - Bugs and edge cases
  - Missing features a user would expect
  - Security issues
  - Performance concerns
- **Test generation** — ask peers to write tests for new code (they'll think of cases the author missed)
- **"What did I miss?"** — after completing a feature, ask peers to list gaps from a user's perspective

### CLI Auto-Detection
- Auto-detect available CLIs on localhost via `shutil.which()`
- Supported: `gemini`, `codex`, `claude` (Claude Code CLI), or any future frontier CLI
- If only one CLI is installed, skip consultation (no peers available)
- No hardcoded assumptions — works on any user's machine with whatever they have
- Extensible: adding a new CLI to the detection list is one line
- **Skip Ollama** — local models are not frontier-tier, exclude from consultation
- Only consult frontier-class models (Claude Opus, Gemini 2.5 Pro, GPT-4o/o3)

### Any Brain Can Be the Caller
- Caller passes its own identity (e.g., `caller="gemini"`)
- Tool skips self-consultation — only queries the OTHER available CLIs
- Claude as brain → consults Gemini + Codex
- Gemini as brain → consults Claude Code + Codex
- OpenAI as brain → consults Claude Code + Gemini
- This makes it a platform-level capability, not tied to any single brain

### Key Files
- New: `agent_skills/consult_panel.py`
- Config: API keys from `$VESSENCE_DATA_HOME/.env`

### UI Announcement
When consulting, display prominently:
- **Claude Code**: `## Consulting Gemini and OpenAI on this decision...`
- **Jane Web**: Status message "Consulting other AI models..."
- **Android**: Status bubble "Consulting other AI models..."

### All Interfaces
- Claude Code (CLI) — calls `consult_panel.py` directly
- Jane Web — brain invokes as a tool via the backend
- Android — same backend path, shows status in chat

### Acceptance Criteria
- Queries available frontier CLIs in parallel (fast)
- Returns structured output: per-model opinion + synthesis
- Can be called from CLI or imported as a function
- Works across all Jane interfaces (CLI, Web, Android)
- Handles API failures gracefully (if one model is down, still returns results from the others)
- Announces consultation visibly to the user before proceeding
