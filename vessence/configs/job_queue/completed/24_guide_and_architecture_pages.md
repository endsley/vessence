# Job: Complete User Guide + Architecture Deep-Dive Page

Status: completed
Priority: 1
Model: opus
Created: 2026-03-24

## Objective
Two tasks:
1. Add missing "Tools" section to the User Guide (guide.html)
2. Build a new Architecture page (architecture.html) with clickable component links that expand into detailed explanations

## Task 1: Add Tools section to guide.html

Add after the Essences section, covering:
- **What are Tools?** — Standalone utilities that essences and Jane can invoke (file indexer, vault search, TTS, memory tools)
- **How they appear** — Tools dropdown in the header shows installed tools
- **How they're used** — Jane calls them automatically when relevant, or user can reference them
- **How to create your own tool** — Create a Python file in the tools directory with a standard interface. Tool must expose function signatures that Jane can discover. Reference the existing tools as examples.
- **Tools vs Essences** — Tools are single functions. Essences are complete personas with memory, personality, and multiple tools combined.

## Task 2: Build architecture.html

Create /guide/architecture (or /architecture) page with:

### Header
- "Jane Architecture" title
- "Back to Jane" and "Back to Guide" links

### Component list (each is a clickable expandable section)
When clicked, shows a detailed explanation of how that component works, key files, and data flow.

**Core Brain**
- Standing Brain Manager — 3 CLI processes, stream-json, process lifecycle, auto-restart
- Intent Classifier — gemma3:4b, 4 levels, model routing table
- Context Builder — PromptProfile system, slim vs full context, when memory is skipped
- Model Routing — haiku/sonnet/opus selection, per-provider config

**Memory System**
- ChromaDB Collections — short-term (14d TTL), long-term (permanent), file index, user memories
- Memory Daemon — port 8083, fast retrieval, fallback to slow gemma path
- Librarian — gemma3:4b memory synthesis, how queries are built
- Conversation Manager — turn summarization, write-back to ChromaDB
- Session Summary — topic tracking, rotation handoff

**Web Architecture**
- Jane Proxy — stream_message flow, SSE event types, emit system
- Instant Commands — pattern matching, script execution, bypass LLM
- Authentication — Google OAuth, session cookies, trusted devices, localhost bypass
- Health Check — 2-failure threshold, 15s poll, offline banner

**Essence System**
- Essence Loader — auto-load at startup, manifest.json format
- Essence Activation — URL param, personality swap, ChromaDB isolation
- Essence Builder — interview mode, spec generation, code generation

**Automation**
- Prompt Queue — internal API path, dedicated session, idle detection
- Job Queue — markdown specs, priority system, show_job_queue.py
- Cron Pipeline — 15 jobs, nightly batch schedule, what each does

**Infrastructure**
- Standing Brain Process — stream-json protocol, NDJSON reader, buffer handling
- Docker — slim images, first-boot install, Alpine onboarding, pip trimming
- Cloudflare Tunnel — named tunnel, relay server
- USB Backup — incremental rsync, weekly snapshots

### Implementation
- Use Alpine.js with `x-show` for expandable sections (click to toggle)
- Dark theme matching jane.html
- Each section has: description, key files (with links to code map), data flow diagram (ASCII)
- Add "Architecture" button to jane.html header (book + gear icon), between Guide and the ml-auto div

### Route
- Add `GET /architecture` to main.py, serving `architecture.html`

## Verification
- Guide page has Tools section with create-your-own instructions
- Architecture page loads at /architecture
- All component sections expand/collapse on click
- "Back to Jane" links work from both pages
- "Architecture" button visible in jane.html header

## Files Involved
- vault_web/templates/guide.html — add Tools section
- vault_web/templates/architecture.html — new page
- jane_web/main.py — add /architecture route
- vault_web/templates/jane.html — add Architecture button
