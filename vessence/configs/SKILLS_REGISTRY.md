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
    -   **Location:** `$VESSENCE_HOME/jane_web/` (routes + templates) + `$VESSENCE_HOME/vault_web/` (shared library modules: auth, files, oauth, playlists, share, database)
    -   **URL:** Served on `http://127.0.0.1:8081`, public via Cloudflare named tunnel at `jane.vessences.com`
    -   **Services:** `jane-web.service` (FastAPI/uvicorn), `vault-tunnel.service` (cloudflared named tunnel)
    -   **Features:** OTP auth via Discord, file browser, Jane chat, music player, share links
    -   **Note:** Legacy `vault-web.service` on port 8080 and `vault_web/main.py` were retired in v0.1.71 — all endpoints consolidated into `jane_web/main.py`.

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
    -   **Codex MCP bridge:** `$VESSENCE_HOME/startup_code/codex_memory_mcp.py` — stdio MCP server registered as `jane-memory` for OpenAI Codex sessions; exposes `query_jane_memory(query, max_chars=12000)` and `jane_memory_paths()`

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

-   **Capability:** Google Calendar Read (server-side)
    -   **File:** `$VESSENCE_HOME/agent_skills/calendar_tools.py`
    -   **Key Functions:** `list_events_in_range(range_hint, max_results)`, `resolve_range(hint)` (today/tomorrow/this_week/next_week/weekend/next/YYYY-MM-DD), `list_events(time_min_iso, time_max_iso)`, `create_event`, `update_event`, `delete_event`, `quick_add`
    -   **OAuth:** reuses the Gmail OAuth grant (`calendar.events` scope already included); accepts `calendar.readonly` for pure reads
    -   **Wiring:** `READ_CALENDAR` intent class fetches events server-side and injects `[CALENDAR DATA]` into the brain context — see `jane_web/jane_proxy.py` (v2 path + legacy read_calendar branch) and `intent_classifier/v2/classes/read_calendar.py`

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
    -   **File:** `jane_web/main.py`
    -   **Endpoints:** `GET/POST/DELETE /api/essences/*` — list, load, unload, activate, delete essences

---

## Multi-User & Personality

-   **Capability:** User Manager (Per-User Configuration)
    -   **File:** `agent_skills/user_manager.py`
    -   **Functions:** `normalize_user_id(user_id)`, `get_user_config(user_id)`, `create_user_space(user_id, display_name, ...)`, `seed_user_memory(user_id, facts)`, `list_users()`, `set_user_personality(user_id, personality)`, `get_personality_content(personality)`, `list_personalities()`, `ensure_user_space_from_email(email)`
    -   **Purpose:** Manages per-user email-derived directories, config files, capability flags, personality preferences, private ChromaDB memory, and private vault roots at `$VESSENCE_DATA_HOME/users/<sanitized_email>/`

-   **Capability:** Multi-User Auth Support
    -   **File:** `vault_web/auth.py`
    -   **Functions:** `get_allowed_emails()`, `is_allowed_email(email)`, `user_id_from_email(email)`
    -   **Purpose:** Comma-separated `ALLOWED_GOOGLE_EMAILS` support, per-user session creation with `user_id` derived from email

-   **Capability:** Jane Personality Presets
    -   **Location:** `configs/personalities/`
    -   **Files:** `default.md`, `professional.md`, `casual.md`, `technical.md`
    -   **Purpose:** Customizable communication style presets for Jane, selectable per user

-   **Capability:** Personality Settings API
    -   **File:** `jane_web/main.py`
    -   **Endpoints:** `GET /api/settings/personality`, `POST /api/settings/personality`
    -   **Purpose:** Read and update the current user's Jane personality preference via vault_web Settings tab

-   **Capability:** Relay Server & Accounts
    -   **File:** `relay_server/database.py`
    -   **Classes:** `User` dataclass
    -   **Functions:** `create_user()`, `create_user_from_google()`, `get_user_by_email()`, `get_user_by_relay_token()`, `regenerate_relay_token()`
    -   **Purpose:** SQLite-backed account system for the Vessence relay server (registration, Google OAuth, relay tokens, marketplace purchases)

---

## Web Sequences (Browser Automation Skills)

A **WebSequence** is a named, reusable Playwright browser automation script. Each subclass implements `steps(page)` and the base class handles browser lifecycle. Sequences are classifiable by the Stage 1 intent pipeline and answered at Stage 2 (fast SQL) with no LLM required.

-   **Base Class:** `skills/web_sequences/base.py` — `WebSequence(ABC)`
    -   `run()`: launches headless Playwright, calls `steps()`, optionally saves to ChromaDB
    -   `steps(page)`: abstract — implement the browser actions
    -   `_save(data)`: saves results to ChromaDB collection `web_sequence_data`

-   **Registry:** `skills/web_sequences/registry.py` — `registry` singleton
    -   Auto-discovers `WebSequence` subclasses via `pkgutil.iter_modules`
    -   `registry.get(name)` → class, `registry.names()` → list

-   **Sequence: Clinic Schedule Scraper**
    -   **File:** `skills/web_sequences/kathia_schedule.py`
    -   **Class:** `KathiaScheduleSequence` (name=`kathia_schedule`)
    -   **What it does:** Logs into Water Lily Wellness (acubliss.app), navigates to Kathia Kirschner's FullCalendar week view, extracts appointments from `fc-timegrid-col[data-date]` DOM elements, parses patient name / appointment type / start-end times via regex, stores rows in `$VESSENCE_DATA_HOME/schedule.db` SQLite.
    -   **Credentials:** `WATERLILY_USERNAME` / `WATERLILY_PASSWORD` from `$VESSENCE_DATA_HOME/.env`
    -   **Trigger:** Run manually or via cron (cron not yet configured)

-   **Intent Class:** `intent_classifier/v2/classes/clinic_schedules_info.py` — `CLINIC_SCHEDULES_INFO`
    -   Routes questions about the acupuncturist's current-week schedule (patient count per day, who's coming in) to Stage 2 — bypasses Opus entirely
    -   18 positive examples using "she/her" pronouns only (no practitioner names in embeddings)
    -   Counter-examples in `DELEGATE_OPUS` pull named-practitioner queries away from this class

-   **Stage 2 Handler:** `jane_web/jane_v2/classes/clinic_schedules_info/handler.py`
    -   Resolves day of week (today/tomorrow → actual day name)
    -   COUNT queries: `SELECT COUNT(*) WHERE day_of_week=? AND week_start=?`
    -   WHO queries: `SELECT patient_name ORDER BY start_time` (first 4 + "and N more")
    -   Weekly summary: `GROUP BY day_of_week ORDER BY cnt DESC`
    -   Falls through to Stage 3 only if DB is missing

-   **SQLite Schema:** `$VESSENCE_DATA_HOME/schedule.db`, table `appointments`
    -   Columns: `week_start`, `day_of_week`, `patient_name`, `appt_type`, `visit_number`, `start_time`, `end_time`, `practitioner`, `scraped_at`
    -   On each scrape: DELETEs current week's rows for the practitioner, then inserts fresh

-   **Skill: Facebook Marketplace Harvester**
    -   **Module:** `agent_skills/marketplace/` (`config.py`, `harvester.py`)
    -   **What it does:** Runs a saved-search bundle against Facebook Marketplace, applies the car-filter pipeline (miles<max, price<max, "clean title" in description, suspicion rule that flags >5-year-old cars with <3k mi/yr), and saves surviving listings + photos to disk. Uses the `facebook_julius` profile (stored cookies → no 2FA prompt).
    -   **Entry points:**
        -   `config.list_searches() / get_search(name) / save_search(name, label=..., queries=[...], filters=..., location_id=...)`
        -   `harvester.harvest(search_name)` — blocking, runs the full pipeline
        -   `harvester.listings_for(search_name)` — reads the latest saved summary
        -   `harvester.listing_detail(name, slug, id)`, `harvester.photo_path(...)` — detail/photo helpers
    -   **CLI:** `python -m agent_skills.marketplace.harvester <search_name>`
    -   **Config:** `$VESSENCE_DATA_HOME/config/marketplace_searches.json`
    -   **Data:** `$VESSENCE_DATA_HOME/data/facebook_marketplace_finds/<search_name>/<query_slug>/<listing_id>/listing.json` + `photo_NN.jpg`
    -   **Default search `cars`:** queries `Toyota corolla`, `Honda civic`, `Honda fit`; filters `max_price=15000`, `max_miles=60000`, `require_clean_title=True`, `suspicion_filter=True`; Medford MA (`109352265750998`)
    -   **Web UI:** Marketplace pill in `/briefing` — card grid of saved searches, drill-in to listings, drill-in to listing detail with photo gallery
    -   **API:** `GET/POST /api/marketplace/searches`, `GET/DELETE /api/marketplace/search/{name}`, `GET /api/marketplace/listing/{name}/{slug}/{id}`, `GET /marketplace-image/{name}/{slug}/{id}/{photo}`
    -   **Trigger:** Intended for cron (not yet configured) — call `harvest("cars")` nightly
