# Agent Architecture & Capabilities

This document serves as a manifest of my (Jane's) core architectural components and learned skills. I must read this file at the start of every session to ensure I am fully aware of my own capabilities.

---

## Communication Channels
- **Primary:** Vessence Android app (v0.0.14+) — native chat, voice, file attachments
- **Fallback:** Discord bridge — keep Discord as fallback communication until the Android app is stable and proven reliable
- **Policy:** Do not remove or disable Discord integration while the Android app is being stabilized

## Configuration
- **Single source of truth:** `jane/config.py` — all paths, timeouts, model names, Discord limits, memory TTLs, ChromaDB settings, and queue parameters. Change settings here; all scripts import from it.
- **Backward compat shim:** `llm_config.py` re-exports LLM-related constants from `config.py` for any callers that still use the old import.
- **Log directory:** All log files go to `$VESSENCE_DATA_HOME/logs/`. Never write logs to the repo root.
- **Path portability:** Runtime state resolves from `VESSENCE_DATA_HOME`, user files from `VAULT_HOME`, and code/config from `VESSENCE_HOME`. `AMBIENT_HOME` is a temporary compatibility alias to `VESSENCE_DATA_HOME`, not a canonical root.
- **Personal name portability:** All hardcoded "Chieh" references in agent prompts and system messages replaced with `os.environ.get('USER_NAME', 'the user')`. Set `USER_NAME` in `.env` at onboarding.

## Standing Brain Architecture (2026-03-24)
- **3 long-lived CLI processes** (tiers: light/medium/heavy) using `--input-format stream-json --output-format stream-json` (Claude) or plain text stdin (Gemini/OpenAI)
- Default models per provider: Claude → haiku-4-5/sonnet-4-6/opus-4-6; Gemini → flash/pro/pro; OpenAI → gpt-4.1-mini/gpt-4.1/o3. All overridable via env vars (`BRAIN_LIGHT_*`, `BRAIN_MEDIUM_*`, `BRAIN_HEAVY_*`)
- Spawn at jane-web startup via `StandingBrainManager` in `jane/standing_brain.py`
- System prompt injected on turn 1 only — subsequent turns send raw message (no re-injection overhead)
- Custom `_read_ndjson_line()` bypasses asyncio 64KB readline limit
- Provider-agnostic: supports Claude CLI (NDJSON stream), Gemini PTY (plain text), OpenAI Codex CLI
- Gemma3:4b only classifies (never responds to user). All levels route through standing brain.
- Brain thoughts (thinking blocks, tool use) streamed to web UI as white text status events
- Instant commands (`show job queue`, `my commands`) bypass LLM entirely (<100ms)
- **Reaper policy (every 60s):** dead brains auto-restart; running brains killed only if BOTH idle (5+ min) AND CPU >15% sustained for 1 hour — prevents killing brains actively handling long jobs
- **Turn rotation:** forced restart after 20 turns (`MAX_TURNS_BEFORE_REFRESH`) to prevent context staleness from CLI token rotation

## Web Permission Gate (2026-03-26)
- **Real-time tool approval** for Jane web UI — same approve/deny UX as CLI terminal
- Enabled via `JANE_WEB_PERMISSIONS=1` in `.env`
- Components: `jane_web/permission_broker.py` (async coordinator), `jane/hooks/permission_gate.py` (PreToolUse hook), endpoints in `jane_web/main.py`
- Flow: CLI tool call → hook fires → HTTP POST to broker → SSE `permission_request` event → web UI dialog → user approve/deny → hook unblocks
- Tools requiring approval: Bash, Write, Edit, NotebookEdit. Read-only bash commands auto-approved.
- Dangerous patterns (rm -rf, git push --force, DROP TABLE) always flagged
- 5-minute timeout → auto-deny. Fail-open if web server unreachable (to avoid blocking brain)
- Page reload recovery: `GET /api/jane/permission/pending` restores pending dialogs

## Intent Classification & Model Routing
- Gemma3:4b classifies every message into: greeting/simple/medium/hard
- Greeting/simple → haiku (slim context: no memory, no task state)
- Medium → sonnet (full context)
- Hard → opus (full context + tools)
- Pre-warmed at startup so first classification is <2ms (not 29s)

## Docker Deployment (Updated 2026-03-24)
- **3 services:** jane (8090, FastAPI + CLI-at-boot), onboarding (3000, Alpine), chromadb (pulled from Docker Hub)
- **Amber removed** — essences run through Jane's standing brain
- **Download: 210 MB** (was 1.3 GB). Jane 770 MB, Onboarding 139 MB (Alpine). Pip trimmed: removed sympy, kubernetes, pygments, pillow, opentelemetry, pip.
- CLI installs on first boot via `install_brain.sh` based on JANE_BRAIN env var
- **Traefik:** Serves `vault.localhost` → vault:8080, `jane.localhost` → jane:8090. Config: `traefik/traefik.yml`
- **Jane image bakes in 3 CLIs:** `@google/gemini-cli`, `@anthropic-ai/claude-code`, and an OpenAI-backed CLI path. `JANE_BRAIN` env var (gemini|claude|openai) selects which is active in the web stack.
- **Onboarding:** First-run wizard at `localhost:3000`. Detects if `.env` exists; if not, walks user through welcome → system check → setup form → identity interview → success. Writes `.env` and `user_profile.md` to the host compose directory.
- **Cloudflare:** Named tunnel (token set in `.env`) or quick-tunnel fallback. Opt-in: `docker compose --profile cloudflare up`
- **Web consolidation (2026-03-21):** Jane web (port 8081) now serves all vault web (port 8080) functionality. Vault routes (`/vault`, `/chat`, `/downloads/*`, `/api/essences/*`, `/essences`) are all served by jane_web. The Cloudflare tunnel config needs updating: `vault.vessences.com` should redirect to `jane.vessences.com` (or both can point to jane_web port 8081). The vault_web service can be retired once the tunnel redirect is in place.
- **CI/CD:** `.github/workflows/docker-publish.yml` builds all 4 images on push to main, pushes to Docker Hub with semver + sha tags. Multi-platform: linux/amd64 + linux/arm64.
- **Interactive OpenAI shell command:** On this machine, the agentic OpenAI CLI is the `codex` command. `.bashrc` now exposes `openai()` as a shell function that runs `codex --dangerously-bypass-approvals-and-sandbox`, matching the existing permissive defaults used for `gemini` and `claude`.

## Component Hardening
- **Jane Session Wrapper:** Implemented an `asyncio`-based, PTY-enabled architecture with non-blocking reads and a 1.5s idle-timeout heuristic for assistant turn detection.
- **Robustness:** Added ANSI escape code stripping, startup noise suppression (10s), and offloaded all blocking LLM/DB calls (ChromaDB, LiteLLM) to a background thread executor. User input is sent to Gemini immediately, before the background memory sync begins, ensuring zero UI latency.
- **Wrapper log writeback:** `jane_session_wrapper.py` now batches raw transcript logging through an async queue and flushes to disk on a background thread, so large PTY output no longer performs synchronous file I/O on the main event loop.
- **PTY Management:** Disabled slave PTY echo using `termios` to prevent double-input display and visual noise.
- **Noise Filtering:** Integrated global UI suppression via `settings.json` to eliminate ADK system logs and ensure only high-signal agent outputs reach the interface.
- **Screen Reader Mode:** Support for `--screen-reader` flag to provide a simplified, text-only output stream optimized for screen readers or low-bandwidth connections.
- **Swappable Jane web brains:** `jane_web/jane_proxy.py` now routes through a shared context builder (`jane/context_builder.py`) and pluggable CLI adapters (`jane/brain_adapters.py`) so memory, identity, and session writeback stay independent from the active CLI backend.
- **Research token conservation:** Jane web research can be offloaded through `jane/research_router.py`, which gathers raw web search results and synthesizes them with the local Ollama model instead of consuming main-brain tokens.
- **Jane web split memory path:** Jane web now uses two local subprocess roles for continuity and memory recall. `gemma3:4b` is the fast Memory Librarian on the reply path, and a separate `qwen2.5-coder:14b` subprocess updates a Python-owned per-session conversation summary file after each turn. The summary stores at most 3 central topics and replaces raw recent-turn replay in the Librarian path.
- **Jane web first-turn prewarm:** When the browser session is established, Jane prewarms a session bootstrap summary in the background and reuses it for later turns. Session IDs are unified between backend auth state and the frontend chat session so the prewarm cache is not lost on the first message.
- **Structured personal context:** Jane web no longer injects the full `user_profile.md` blob on every turn. It now reads compact typed facts from `$VESSENCE_DATA_HOME/user_profile_facts.json` and selects only topic-relevant snippets, such as profession for AI/coding topics or piano familiarity for music topics.
- **Intent-based prompt profiles:** Jane web now uses different prompt shapes for `factual_personal`, `file_lookup`, `project_work`, and `casual_followup` turns. Simple factual turns avoid unnecessary task state and conversation-summary payload.
- **Similarity thresholds on retrieval:** Memory lanes are filtered by cosine-distance cutoffs before the Librarian sees them, reducing weak matches and token waste.
- **Short-term retrieval compaction:** Jane's `ConversationManager` now writes concise retrieval notes into short-term Chroma instead of raw full-turn text. Raw transcripts remain in the SQLite ledger. Assistant turns that contain code edits are summarized with a code-aware prompt that extracts changed files, behavioral effect, key symbols, and open follow-up risk rather than storing the raw diff.
- **Async persistence path:** Jane web returns the final response before short-term writeback and session-summary updates finish. The persistence path now runs in the background so it does not delay the visible response.
- **Single in-progress web bubble:** Jane web and Amber web now show one assistant bubble while thinking; status updates are rendered inside that same bubble instead of using a second empty placeholder bubble.
- **Amber web session continuity:** Amber web now persists its chat session id in browser `sessionStorage`, reuses that session across refreshes, and streams periodic status updates while the ADK backend is working so the UI no longer waits silently on a blocking call.
- **Watchdog restart policy:** `startup_code/bot_watchdog.sh` now requires repeated failed probes before restarting services and applies a restart cooldown. This reduces false restarts when a service is transiently slow or its event loop is briefly blocked.
- **Persistent Gemini session:** `jane/persistent_gemini.py` manages a persistent PTY subprocess for the Gemini CLI. Avoids cold starts on repeated turns by keeping the Gemini process alive across multiple web turns. Gated by `JANE_WEB_PERSISTENT_GEMINI` env var (default: on for Gemini brain).
- **One-subscription-per-provider strategy:** All LLM calls (user-facing and background) go through the provider's CLI binary (`claude`, `codex`, or `gemini`) using the user's existing subscription auth. No separate API keys are needed. `JANE_BRAIN` selects the active provider; `SMART_MODEL` and `CHEAP_MODEL` can override the defaults. See `memory_manage_architecture.md §5` for the full provider table.
- **Claude CLI /tmp cwd:** `ClaudeBrainAdapter` in `jane/brain_adapters.py` sets `cwd_override = "/tmp"` so the Claude CLI subprocess does not search upward for `CLAUDE.md`, which would activate hooks that interfere with subprocess calls. `ClaudeBrainAdapter.required_env` is empty — the Claude CLI uses its own auth and does not require `ANTHROPIC_API_KEY`.
- **Background task LLM wrapper:** `agent_skills/claude_cli_llm.py` is the provider-agnostic CLI wrapper for background tasks (archivist, janitor, summarization). Exposes `completion()`, `completion_smart()`, and `completion_json()`. Routes to the correct CLI binary based on `JANE_BRAIN`.
- **Automation runner:** `jane/automation_runner.py` provides a shared CLI-agnostic interface for running automated tasks. Uses the brain adapter layer; defaults to `codex` (OpenAI) via `AUTOMATION_CLI_PROVIDER` env var, falls back to `JANE_BRAIN`.
- **Audit wrapper:** `jane/audit_wrapper.py` runs code audit passes using the Qwen orchestrator, reading the session wrapper source for static analysis.
- **Memory diagnostics:** `test_code/benchmark_gemma_librarian.py` measures where Librarian time is spent, `test_code/inspect_librarian_input.py` shows the exact Librarian prompt, and `agent_skills/migrate_short_term_memory.py` rewrites legacy bloated short-term entries into the concise format.
- **Claude Code hooks:** Claude Code gets memory and context via UserPromptSubmit hooks (see `memory_manage_architecture.md §2.5`). The `claude_smart_context.py` hook replaced 3 old hooks (identity, full startup context, jane context) reducing per-turn injection from ~25,000 tokens to ~800–2,000 tokens. Hooks output plain text to stdout (JSON format does not work with Claude Code).
- **Essence builder:** `agent_skills/essence_builder.py` implements Jane's structured spec interview for building new essences. 12 sections, state persisted to disk, spec-first enforcement. Triggered by "build essence" command in CLAUDE.md.
- **Essence runtime:** `agent_skills/essence_runtime.py` manages multi-essence lifecycle, Mode A orchestration (Jane as PM), and Mode C peer-to-peer via capability registry.
- **Essence loader:** `agent_skills/essence_loader.py` handles loading/unloading/deleting essences, ChromaDB initialization, and manifest validation.
- **Essence validator:** `agent_skills/validate_essence.py` validates essence folder structure and manifest.json schema compliance.
- **Task spine enforcement:** Long-running work now has a persistent task spine in `$VESSENCE_DATA_HOME/data/task_spine.json` plus an interrupt stack in `$VESSENCE_DATA_HOME/data/interrupt_stack.json`. The helper module `jane/task_spine.py` is the source of truth for pausing side tasks and resuming the saved main step.
## Multi-User Support
- **Auth multi-user:** `vault_web/auth.py` now supports comma-separated `ALLOWED_GOOGLE_EMAILS` (e.g., `chieh.t.wu@gmail.com,spouse@gmail.com`). Each email gets its own session with a `user_id` derived from the email address.
- **Helper functions:** `get_allowed_emails()`, `is_allowed_email(email)`, `user_id_from_email(email)` in `vault_web/auth.py`.
- **User manager:** `agent_skills/user_manager.py` provides per-user configuration management:
  - `get_user_config(user_id)` — returns user's config (personality, memory namespace, etc.)
  - `create_user_space(user_id, display_name)` — creates per-user directory and config at `$VESSENCE_DATA_HOME/users/<user_id>/config.json`
  - `set_user_personality(user_id, personality)` — sets a user's personality preference
  - `get_personality_content(personality)` — loads personality markdown content
  - `list_personalities()` — lists all available personality options
  - `ensure_user_space_from_email(email)` — convenience wrapper
- **Per-user data:** Each user gets a directory at `$VESSENCE_DATA_HOME/users/<user_id>/` with a `config.json` containing display_name, personality, memory_namespace, and created_at.

## Jane Personality Customization
- **Personality files:** `configs/personalities/` contains 4 personality presets:
  - `default.md` — warm, direct, efficient, no filler
  - `professional.md` — formal, thorough, structured
  - `casual.md` — friendly, relaxed, conversational
  - `technical.md` — direct, precise, code-focused
- **Settings UI:** The vault_web Settings tab includes a "Jane's Personality" dropdown that lets each user choose their preferred personality. Stored per-user via `user_manager.py`.
- **API endpoints:**
  - `GET /api/settings/personality` — returns current personality and available options
  - `POST /api/settings/personality` — sets the user's personality preference

This checklist contains core directives that I must mentally verify before completing a task to ensure I am following our established operational procedures.

1.  **Qwen Delegation Check:** If the task involved code analysis, search result summarization, or log triage, have I delegated it to the Qwen sub-agent via the hardware-locked orchestrator?
2.  **Micromanagement Audit:** Did I perform any low-level file edits or shell commands that should have been handled autonomously by the sub-agent? My role is strategic intent, not manual execution.
3.  **Documentation Update Check:** If the task involved a change to any system architecture, capability, or core process, have I updated all relevant documentation files?
