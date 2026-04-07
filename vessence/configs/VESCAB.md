# Vescab — Vessence Vocabulary

Official terminology for the Vessence platform. When we refer to these terms, this is the canonical definition.

---

## Core Platform

| Term | Definition |
|---|---|
| **Vessence** | The platform. Name from "Vessel + Essence" — a container that holds someone's digital essence. The north star: a digital clone and living memory. |
| **Jane** | The permanent builder agent. Handles reasoning, code, architecture, research. The user's technical partner. One Jane per Vessence instance. |
| **Amber** | The universal runtime agent. Takes on essence roles ("Amber the briefer", "Amber the librarian"). Powered by Gemini Flash via Google ADK. The user-facing companion. |
| **Vault** | The file storage system. Physical files live here — PDFs, images, audio, documents. Accessed via web file browser (Life Librarian essence) or API. Path: `$VAULT_HOME`. |
| **ChromaDB** | The memory system. Facts, preferences, conversation history, searchable knowledge stored as vector embeddings. "The soul of the product." Shared across Jane, Amber, CLI, web, and Android. |

## Essences

| Term | Definition |
|---|---|
| **Essence** | A pluggable persona/role package that loads into Amber. Contains: personality, knowledge (own ChromaDB), custom functions, UI layout, and settings. Self-contained folder — zip to export, delete folder to remove. |
| **Manifest** | `manifest.json` inside each essence. Declares name, role title, version, permissions, capabilities, preferred model, UI type, and interaction patterns. |
| **Essence Builder** | Jane's interview-driven tool for creating new essences. 12-section spec interview → approved spec → auto-generated essence folder. |
| **Default Essences** | Essences that ship with every Vessence install: Life Librarian (file browser), Music Playlist (audio player), Daily Briefing (news aggregator), Work Log (activity feed). |
| **Marketplace** | The platform at vessences.com where users buy/sell/rent essences. Three models: Buy (download), Rent (hosted access), Free. |

## Queues & Task Management

| Term | Definition |
|---|---|
| **Prompt Queue** | Small, self-contained tasks stored in `vault/documents/prompt_list.md`. Auto-runs when user is idle (cron every 5 min). For quick tasks: "delete these files", "fix this bug", "reindex vault". Command: `prompt: <text>` to add. |
| **Job Queue** | Complex jobs stored as individual spec files in `configs/job_queue/`. Each job is a self-contained markdown file with objective, context, pre-conditions, steps, verification commands, and file references. Only runs on explicit `run job queue:` command. For multi-step work that needs full context to execute across sessions. |
| **Prompt** | A single item in the prompt queue. Short text, executed as-is. |
| **Job** | A single item in the job queue. Full spec file with enough context for any session to execute cold. Named `{priority}_{short_name}.md`. |

## Architecture

| Term | Definition |
|---|---|
| **Brain** | The LLM backend that powers Jane. Swappable via `JANE_BRAIN` env var. Options: `claude` (Claude Code CLI), `gemini` (Gemini CLI), `openai` (OpenAI CLI). Jane's identity stays the same regardless of brain. |
| **Brain Adapter** | Code in `jane/brain_adapters.py` that wraps each CLI into a common interface. Handles command building, timeout, streaming. |
| **Persistent Session** | A long-lived CLI session that maintains context across messages via `--resume`. Implemented for Claude (`persistent_claude.py`) and Gemini (`persistent_gemini.py`). Eliminates re-sending full history every message. |
| **stream-json** | Claude Code's `--output-format stream-json --verbose` mode. Outputs one JSON event per line: tool_use, text deltas, results, session IDs, token costs. Enables real-time tool visibility on web/Android. |
| **Jane Proxy** | `jane_web/jane_proxy.py` — the server-side orchestrator. Builds context, manages sessions, spawns CLI subprocesses, streams responses. The bridge between web/Android and the CLI brain. |
| **Context Builder** | `jane/context_builder.py` — assembles the full system prompt for each message. Combines: identity, ChromaDB memory, conversation history, session summary, platform context, and essence-specific data. |
| **Broadcast** | `jane_web/broadcast.py` — real-time cross-session status updates. When Jane is working on one client, other connected clients see summarized progress. Uses SSE endpoint `/api/jane/live`. |

## Memory

| Term | Definition |
|---|---|
| **Long-term Memory** | Persistent facts in ChromaDB with no expiration. User preferences, project decisions, relationship facts. Shared across all agents and sessions. |
| **Short-term Memory** | Recent conversation context in ChromaDB with 14-day TTL. Auto-deleted by the memory janitor. |
| **Forgettable Memory** | Operational logs (cron executions, queue results) stored with short TTL. Useful for debugging but not permanent. |
| **Permanent Memory** | Core identity facts that never expire. User's name, family, profession, key preferences. |
| **Librarian** | The memory retrieval pipeline. Queries ChromaDB, ranks results by relevance, injects into the system prompt via hooks (CLI) or context_builder (web/Android). |
| **Memory Hook** | `~/.claude/hooks/memory_hook.sh` — CLI-only hook that queries ChromaDB before every Claude Code prompt and injects relevant memories as additional context. |

## UI & Clients

| Term | Definition |
|---|---|
| **Action Tag** | Special markup in Jane's responses that renders as interactive elements. `{{navigate:Essence}}` = tappable navigation chip. `{{image:path}}` = inline image. `{{play:path}}` = audio player card. |
| **Card Grid** | UI layout type for essences like Daily Briefing. Scrollable grid of cards with images, text, and action buttons. Inspired by Google News. |
| **Live Activity Banner** | Purple banner on web/Android that shows when Jane is working on another session. Powered by the broadcast system. |
| **TTS Toggle** | Speaker icon in Android chat header. Enables/disables Android native TextToSpeech for all Jane responses. Setting persists across app restarts. |

## Infrastructure

| Term | Definition |
|---|---|
| **Relay** | Server at `relay.vessences.com` that routes traffic between users' Docker instances and their mobile/remote clients. Users don't need Cloudflare or Tailscale. Cost: ~$20/month per 1000 users. |
| **Keepalive Cron** | `*/5 * * * *` cron that checks if Jane web server is running and restarts it if not. Replaced the full bot watchdog after Discord was disconnected. |
| **Identity Hook** | `~/.claude/hooks/identity_hook.sh` — CLI-only hook that injects compact Jane/user identity into every prompt. Compressed from 17.8KB to 1.3KB on 2026-03-22. |
| **Onboarding** | First-run setup wizard (port 3000). Collects user name, brain choice, API keys. Writes `.env` file and seeds initial ChromaDB memories. |

## Commands

| Command | What it does |
|---|---|
| `prompt: <text>` | Adds to prompt queue — does NOT execute |
| `run prompt list:` | Executes all pending prompts sequentially |
| `add job:` | Creates a job spec in `configs/job_queue/` from conversation context |
| `show job queue:` | Shows all jobs as table (priority, status, title) |
| `run job queue:` | Executes highest-priority pending job |
| `build essence:` | Starts the 12-section essence builder interview |
| `my commands:` | Shows command reference |
| `show cron:` | Shows cron jobs as formatted table |
