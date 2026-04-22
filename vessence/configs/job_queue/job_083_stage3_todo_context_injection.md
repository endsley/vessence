# Job #83: Stage 3 TODO Context Injection

Status: completed
Priority: medium
Created: 2026-04-22

## Problem

When a TODO-related request falls through to Stage 3 (Opus), the LLM has no
TODO data in its context. The `protocol.md` tells it to read the cache file,
but this is unreliable — Opus sometimes ignores the instruction and asks
redundant clarifying questions (e.g., "what kind of item?" when the user
clearly means the TODO list).

Stage 2's handler has the cache data hardcoded into its logic and handles
TODO requests correctly. But when Stage 2 escalates (ambiguous category,
broad question, Ambient project category), Stage 3 is flying blind.

## Solution

Google Docs is the single source of truth. Stage 3 should fetch TODO data
live from the Google Doc (via `agent_skills.docs_tools`), NOT from the
local cache file. The cache is a Stage 2 speed optimization only.

In `stage3_escalate.py`, when the escalation reason maps to `todo_list`:

1. Fetch the current TODO list directly from Google Docs API
   (using `docs_tools` or `fetch_todo_list` in live mode)
2. Inject the category names and items into the prompt as a structured block
   (similar to how `_inject_structured_state` works)
3. Place it inside the `<class_protocol>` block or as a sibling block so
   Opus has the data without needing a tool call

Stage 3 can afford the ~1-2s Google API latency since it already takes
several seconds for Opus to respond. Single source of truth > speed here.

## Acceptance Criteria

- [ ] Stage 3 TODO escalations fetch live data from Google Docs (not cache)
- [ ] Opus can answer "how many items on my clinic list?" without a tool call
- [ ] Opus can add items to the correct category without asking "which list?"
- [ ] No regression in non-TODO Stage 3 escalations
- [ ] Cache file remains for Stage 2 fast-path only — no dual reads
