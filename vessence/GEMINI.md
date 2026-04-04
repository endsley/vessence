# Project Ambient — Context for Gemini CLI (Jane)

This file provides project-level context loaded automatically when Gemini CLI runs from `/home/chieh/vessence/`.
The global identity and protocols are in `/home/chieh/.gemini/GEMINI.md`.

## Initialization

At the start of every new session, Jane should rebuild herself from the canonical startup sequence in [`/home/chieh/vessence/configs/JANE_INITIALIZATION_SEQUENCE.md`](/home/chieh/vessence/configs/JANE_INITIALIZATION_SEQUENCE.md).

The live runtime/data roots are `/home/chieh/vessence-data` for mutable state and `/home/chieh/vault` for user-owned documents.

When prior session context is missing, run:

```bash
PYTHONPATH=/home/chieh/vessence /home/chieh/google-adk-env/adk-venv/bin/python /home/chieh/vessence/startup_code/jane_bootstrap.py
```

That script rebuilds a startup digest from:

- identity essays in `/home/chieh/vault/documents/`
- source-of-truth project docs in `/home/chieh/vessence/configs/`
- live ChromaDB stores under `/home/chieh/vessence-data/vector_db`
- active prompt queue state

---

## Project Overview

**Project Ambient** is a two-agent personal AI system:
- **Jane** (pluggable CLI brain: Gemini CLI / Claude Code / OpenAI CLI) — primary technical brain, coding, architecture, research
- **Amber** (Google ADK / gemini-2.5-flash) — always-on Discord bot, vault management, TTS, computer control

---

## Key Paths

| Resource | Path |
|---|---|
| Agent skills | `/home/chieh/vessence/agent_skills/` |
| Jane context builder | `/home/chieh/vessence/jane/context_builder.py` |
| Jane brain adapters | `/home/chieh/vessence/jane/brain_adapters.py` |
| Amber agent | `/home/chieh/vessence/amber/` |
| Vault | `/home/chieh/vault/` |
| Vector memory (ChromaDB) | `/home/chieh/vessence-data/vector_db/` |
| Configs & docs | `/home/chieh/vessence/configs/` |
| Logs | `/home/chieh/vessence-data/logs/` |
| Jane web router | `/home/chieh/vessence/jane_web/jane_proxy.py` |
| Vault website code | `/home/chieh/vessence/vault_web/` |
| ADK venv python | `/home/chieh/google-adk-env/adk-venv/bin/python` |
| Amber server | `http://localhost:8000` |
| Jane website | `http://localhost:8090` |
| Vault website | `http://localhost:8080` |

---

## Architecture Summary

- **Memory**: ChromaDB (`/home/chieh/vessence-data/vector_db`, collection: `user_memories`) is the live shared cross-agent memory store. Jane's short-term and archived long-term memory collections also live under the runtime data root. SQLite is used separately for ledgers and web-app state.
- **Jane routing**: Jane's identity/memory/context is now separated from the active CLI backend. Shared context is built in `jane/context_builder.py`, and CLI-specific execution lives in `jane/brain_adapters.py`.
- **Jane session writeback**: `jane_web/jane_proxy.py` writes user and assistant turns through `ConversationManager`, so the Jane web path feeds the same short-term and archival memory pipeline.
- **Research offload**: Jane web research can be offloaded to the local Ollama stack instead of spending main-brain tokens. Raw web search uses Tavily-first / DuckDuckGo-fallback search, and synthesis is delegated to the local model.
- **Background tasks**: Cron jobs run nightly (audit, janitor, heartbeat research, USB backup). See `configs/CRON_JOBS.md`.
- **Discord**: Two bots — Jane bridge (Jane#3353) via `gemini_cli_bridge/`, Amber (Amber#9957) via ADK.
- **Vault website**: FastAPI + vanilla JS on port 8080, Cloudflare Quick Tunnel for public access.
- **TTS**: Kokoro-82M in dedicated `kokoro` conda env.
- **Vision**: OmniParser V2 in `omniparser_venv/`.

---

## Current Model Strategy

| Role | Model |
|---|---|
| Jane (primary brain) | Pluggable: Gemini CLI / Claude Code / OpenAI CLI |
| Amber (primary brain) | gemini-2.5-flash (ADK) |
| Memory librarian/searcher | gemma3:4b (background local librarian) |
| Research synthesis / local technical analysis | qwen2.5-coder:14b via Ollama |
| Local fallback | qwen2.5-coder:14b via Ollama |

Jane's local non-Docker runtime must resolve memory from `/home/chieh/vessence-data`, where the live `user_memories` collection currently exists.

---

## Documentation Enforcement

- Memory-system source changes are protected by the git hook at `/home/chieh/vessence/.git/hooks/pre-commit`.
- If a commit stages memory-related source files without also staging `configs/memory_manage_architecture.md`, the commit is blocked.

---

## Prompt Queue

Active work items are tracked in `/home/chieh/vault/documents/prompt_list.md`.
Completed items are archived in `/home/chieh/vault/documents/completed_prompts.md`.
