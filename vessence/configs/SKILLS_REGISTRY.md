# Skills & Capabilities Registry

This document is a detailed index of Jane's major capabilities. It maps a high-level skill to its precise file location and the primary class or function that implements it. I must read this file at startup to have a complete, actionable map of the codebase.

---

## Jane Runtime Capabilities

-   **Capability:** Text-to-Speech (TTS)
    -   **File:** `$VESSENCE_HOME/amber/tools/speech_tools.py`
    -   **Class:** `TextToSpeechTool`
    -   **Note:** Legacy module path; capability now belongs to Jane's unified runtime

-   **Capability:** Local Computer Control
    -   **File:** `$VESSENCE_HOME/amber/tools/local_computer.py`
    -   **Class:** `LocalComputer`
    -   **Key Functions:** `click_at`, `type_text_at`, `scroll_document`, `navigate`, `search`, `list_windows`, `focus_window`
    -   **Note:** Legacy module path; capability now belongs to Jane's unified runtime

-   **Capability:** Secure Vault Management
    -   **File:** `$VESSENCE_HOME/amber/tools/vault_tools.py`
    -   **Classes:**
        -   `VaultSaveTool`
        -   `VaultSendFileTool`
        -   `VaultDeleteTool`
        -   `VaultReadFileTool`
        -   `VaultAnalyzePdfTool` — extracts and analyzes PDF content from vault
        -   `VaultSearchTool`
        -   `VaultTunnelURLTool` — reports current Cloudflare Quick Tunnel URL for vault website
        -   `VaultReorganizeTool` — reorganizes vault file structure
        -   `VaultIndexTool` — indexes vault files into ChromaDB for search
        -   `VaultFindAudioTool` — finds audio files in vault
        -   `VaultPlaylistTool` — manages vault music playlists
        -   `MemorySaveTool`
        -   `MemoryUpdateTool`
        -   `TerminalTool`

-   **Capability:** Vault Browser Website
    -   **Location:** `$VESSENCE_HOME/vault_web/`
    -   **URL:** Served on `http://127.0.0.1:8080`, public via Cloudflare Quick Tunnel
    -   **Services:** `vault-web.service` (FastAPI/uvicorn), `vault-tunnel.service` (cloudflared)
    -   **Features:** OTP auth via Discord, file browser, Jane chat, music player, share links

-   **Capability:** Web Research
    -   **File:** `$VESSENCE_HOME/amber/tools/research_tools.py`
    -   **Class:** `TechnicalResearchTool`
    -   **Note:** Legacy module path; capability now belongs to Jane's unified runtime

## Shared Agent Skills

-   **Capability:** Memory Retrieval & Librarian
    -   **Synchronous retrieval:** `memory_retrieval.py:build_memory_sections(query)` — queries all ChromaDB tiers and returns raw memory sections
    -   **Librarian synthesis:** `memory_retrieval.py:get_memory_summary(query)` — calls `build_memory_sections` then synthesizes via local LLM (Qwen Librarian)
    -   **Jane wrapper:** `$VESSENCE_HOME/agent_skills/search_memory.py:get_memory_summary(query)` — thin wrapper that calls `memory_retrieval.get_memory_summary` with `assistant_name="Jane"`
    -   **Full result:** `memory_retrieval.py:retrieve_memory_context(query)` — returns `MemoryRetrievalResult` with sections, facts_block, and summary (with embedding cache)

-   **Capability:** Gemma Sub-Agent Delegation
    -   **File:** `$VESSENCE_HOME/agent_skills/gemma_query.py`
    -   **Function:** `query_gemma`

-   **Capability:** Qwen Sub-Agent Delegation
    -   **File:** `$VESSENCE_HOME/agent_skills/qwen_query.py`
    -   **Function:** `query_qwen`

-   **Capability:** Provider-Agnostic CLI LLM Wrapper
    -   **File:** `$VESSENCE_HOME/agent_skills/claude_cli_llm.py`
    -   **Functions:** `completion(prompt)` (cheap model), `completion_smart(prompt)` (smart model), `completion_json(prompt)` (cheap model, JSON parsed)
    -   **Purpose:** Routes background LLM tasks to the active provider CLI (`claude`, `codex`, or `gemini`) using subscription auth. No API keys needed. Used by archivist and janitor.

-   **Capability:** Conversation Manager (Context Compaction)
    -   **File:** `$VESSENCE_HOME/agent_skills/conversation_manager.py`
    -   **Class:** `ConversationManager`

-   **Capability:** Intelligent Archivist (End-of-Session Memory)
    -   **File:** `$VESSENCE_HOME/agent_skills/conversation_manager.py`
    -   **Method:** `ConversationManager._run_archival()` — triages short-term memories into long-term/forgettable/discard via LLM
    -   **Triggers:** idle timer callback (`_on_idle`) and session close (`close()`)

---

## Essence System

-   **Capability:** Essence Validator
    -   **File:** `agent_skills/validate_essence.py`
    -   **Function:** `main()` — validates manifest.json schema and folder structure
    -   **CLI:** `python validate_essence.py /path/to/essence/folder`

-   **Capability:** Essence Loader
    -   **File:** `agent_skills/essence_loader.py`
    -   **Functions:** `load_essence()`, `unload_essence()`, `delete_essence()`, `list_available_essences()`
    -   **Class:** `EssenceState` — holds loaded essence state (name, manifest, ChromaDB, personality)

-   **Capability:** Essence Builder (Interview System)
    -   **File:** `agent_skills/essence_builder.py`
    -   **Functions:** `start_interview()`, `process_answer()`, `generate_spec_document()`, `generate_manifest()`, `build_essence_from_spec()`
    -   **State:** Persisted to `$VESSENCE_DATA_HOME/data/essence_interview_state.json`

-   **Capability:** Essence Runtime (Multi-Essence Orchestration)
    -   **File:** `agent_skills/essence_runtime.py`
    -   **Classes:** `EssenceRuntime` (lifecycle), `JaneOrchestrator` (Mode A top-down), `CapabilityRegistry` (Mode C peer-to-peer)

-   **Capability:** Essence Web API
    -   **File:** `vault_web/main.py` (lines 838+)
    -   **Endpoints:** `GET/POST/DELETE /api/essences/*` — list, load, unload, activate, delete essences

---

## Multi-User & Personality

-   **Capability:** User Manager (Per-User Configuration)
    -   **File:** `agent_skills/user_manager.py`
    -   **Functions:** `get_user_config(user_id)`, `create_user_space(user_id, display_name)`, `set_user_personality(user_id, personality)`, `get_personality_content(personality)`, `list_personalities()`, `ensure_user_space_from_email(email)`
    -   **Purpose:** Manages per-user directories, config files, and personality preferences at `$VESSENCE_DATA_HOME/users/<user_id>/config.json`

-   **Capability:** Multi-User Auth Support
    -   **File:** `vault_web/auth.py`
    -   **Functions:** `get_allowed_emails()`, `is_allowed_email(email)`, `user_id_from_email(email)`
    -   **Purpose:** Comma-separated `ALLOWED_GOOGLE_EMAILS` support, per-user session creation with `user_id` derived from email

-   **Capability:** Jane Personality Presets
    -   **Location:** `configs/personalities/`
    -   **Files:** `default.md`, `professional.md`, `casual.md`, `technical.md`
    -   **Purpose:** Customizable communication style presets for Jane, selectable per user

-   **Capability:** Personality Settings API
    -   **File:** `vault_web/main.py`
    -   **Endpoints:** `GET /api/settings/personality`, `POST /api/settings/personality`
    -   **Purpose:** Read and update the current user's Jane personality preference via vault_web Settings tab

-   **Capability:** Relay Server & Accounts
    -   **File:** `relay_server/database.py`
    -   **Classes:** `User` dataclass
    -   **Functions:** `create_user()`, `create_user_from_google()`, `get_user_by_email()`, `get_user_by_relay_token()`, `regenerate_relay_token()`
    -   **Purpose:** SQLite-backed account system for the Vessence relay server (registration, Google OAuth, relay tokens, marketplace purchases)
