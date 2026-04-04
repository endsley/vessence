# Job #55: Sonnet Main Brain + Opus Subagents

Priority: 2
Status: completed
Created: 2026-03-29

## Description
Switch Jane web's standing brain from Opus 4.6 to Sonnet 4.6 for faster conversational responses. When Sonnet needs code work or deep reasoning, it spawns Opus 4.6 subagents.

### Architecture
- **Sonnet 4.6** (standing brain): conversation, quick answers, planning, ACK generation, light analysis
- **Opus 4.6** (subagent): code reading/writing/refactoring, complex debugging, deep reasoning, research

### How it works
- Standing brain model changes from `claude-opus-4-6` to `claude-sonnet-4-6`
- System prompt instructs Sonnet to use the Agent tool to spawn Opus subagents for:
  - Code tasks (read, write, edit, refactor, debug)
  - Deep reasoning (complex analysis, architecture decisions)
  - Research (multi-step investigation)
- Subagents run as separate Claude CLI processes with `--model claude-opus-4-6`
- Subagent results stream back through the existing tool_use/tool_result event pipeline

### Changes
- `jane/standing_brain.py` — change default model to `claude-sonnet-4-6`
- `jane/config.py` — update WEB_CHAT_MODEL / SMART_MODEL defaults
- `jane/context_builder.py` — add instruction about when to delegate to Opus subagents
- Verify Agent tool works in standing brain's stream-json mode

### Benefits
- Faster time to first token (~1-2s vs ~3-5s for Opus)
- Cheaper for conversational turns
- Opus quality preserved for code and reasoning via subagents
- User experience: quick ack from Sonnet, then detailed work from Opus
