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

-   **Capability:** Encrypted Secret Store
    -   **File:** `$VESSENCE_HOME/agent_skills/secret_store.py`
    -   **Class:** `SecretStore`
    -   **Purpose:** Centralized encrypted storage for sensitive credentials (API keys, passwords). Replaces plaintext `.env` secrets.

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
    -   **Codex MCP bridge:** `$VESSENCE_HOME/startup_code/codex_memory_mcp.py` — stdio MCP server registered as `jane-memory` for OpenAI Codex sessions; exposes `query_jane_memory(query, max_chars=12000)`, `query_nearest_jane_memories(query, limit=2, max_distance=0.50)`, and `jane_memory_paths()`
    -   **Codex CLI installer:** `$VESSENCE_HOME/startup_code/install_codex_memory.py` — idempotently writes `~/.codex/hooks/jane_memory_hook.py`, `~/.codex/jane-memory-instructions.md`, and the Codex `UserPromptSubmit` hook plus `jane-memory` MCP registration in `~/.codex/config.toml`

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

-   **Intent Class:** `intent_classifier/v2/classes/tell_joke.py` — `TELL_JOKE`
    -   Routes "tell me a joke" / "make me laugh" / "got any jokes" to Stage 2 — no Opus
    -   Counter-pulls in `send_message` / `send_email` / `delegate_opus` / `end_conversation` absorb proxy-send ("tell Lee a joke"), meta ("what is a joke"), figurative ("this meeting is a joke"), and decline ("no jokes please") variants
    -   Adversarial sidecar: 0/30 false positives

-   **Stage 2 Handler:** `jane_web/jane_v2/classes/tell_joke/handler.py`
    -   qwen2.5:7b at temp 0.9, num_predict 100; FIFO context lets "another joke" pivot
    -   THOUGHT/REPLY tag parser strips a leaked `THOUGHT:` prefix when the model omits the `REPLY:` tag
    -   Returns `None` on LLM failure → escalates to Stage 3

-   **Intent Class:** `intent_classifier/v2/classes/do_math.py` — `DO_MATH`
    -   Routes arithmetic prompts (multiplication, division, addition, subtraction, percent, square/root, small mixed expressions) to Stage 2 — no Opus
    -   Counter-pulls in `delegate_opus` absorb venting ("I'm bad at math"), narrative ("I'm working on a math problem"), and teaching questions ("how do I do long division")
    -   Adversarial sidecar: 0/30 false positives

-   **Stage 2 Handler:** `jane_web/jane_v2/classes/do_math/handler.py`
    -   qwen2.5:7b at temp 0.0, num_predict 40 — translates spoken phrase to a single Python expression (or `NONE` to escalate)
    -   Restricted `ast` walker evaluates only numeric literals + binary/unary ops + safe calls (`sqrt`, `pow`, `abs`, `round`, `floor`, `ceil`); no names, no attribute access, no kwargs
    -   `_MAX_EXPONENT=1000` caps `**` to block DoS via `9**9999`; `TypeError` is caught and escalates
    -   `_format_number` falls back to `:.6g` for tiny non-zero values so 1/30000 doesn't render as "0"
    -   Built because Qwen alone hallucinates multi-digit products (audit 2026-04-24: 234×567 → 132066 vs 132678 actual). Python is now the source of truth for arithmetic.

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
    -   **Default search `cars`:** queries `Toyota corolla`, `Honda civic`, `Honda fit`, `Honda CRV`; filters `min_price=6000`, `max_price=15000`, `max_miles=60000`, `require_clean_title=True`, `suspicion_filter=True`; Medford MA (`109352265750998`)
    -   **Web UI:** Marketplace pill in `/briefing` — card grid of saved searches, drill-in to listings, drill-in to listing detail with photo gallery
    -   **API:** `GET/POST /api/marketplace/searches`, `GET/DELETE /api/marketplace/search/{name}`, `GET /api/marketplace/listing/{name}/{slug}/{id}`, `GET /marketplace-image/{name}/{slug}/{id}/{photo}`
    -   **Trigger:** Intended for cron (not yet configured) — call `harvest("cars")` nightly

-   **Skill: Education App Homework Auditor (`classes.chiehwu.com`)**
    -   **File:** `agent_skills/edu_homework_audit.py`
    -   **What it does:** Logs into the local `chieh_class_v2` FastAPI dev server via `/dev-login` as a test student (default `juliaprocess@gmail.com`), starts a fresh attempt on a homework, walks every question, computes the canonical answer (reads `attempts.question_seeds` from MySQL via the cloud-sql-proxy at `127.0.0.1:3307`; uses sympy for nullspace / particular-solution problems), submits each answer through the real form, runs static lint + a single batched LLM conceptual-review pass on the prompts, and emits a Markdown + JSON audit report flagging unrendered Jinja, unbalanced math delimiters, typos, grader/canonical disagreements, and LLM-flagged ambiguity / conceptual issues.
    -   **CLI:**
        -   `python edu_homework_audit.py --section <id> --hw <assignment_id> [--mode {full-grade|audit-only}] [--reuse-attempt] [--no-llm-review] [--llm-tier {utility|agent}] [--student <email>] [--base-url http://localhost:8501] [--out-dir <path>]`
        -   `--mode full-grade` (default) submits + finishes; the attempt persists as a finished gradebook row.
        -   `--mode audit-only` renders + lints only, then deletes the unfinished attempt so it doesn't block real students.
        -   `--reuse-attempt` attaches to the student's currently open attempt instead of deleting + restarting. Forces `--mode audit-only`, never submits/finishes, and skips end-of-run cleanup so the student's in-flight progress is preserved. Use this when auditing a homework that you (or a real student) are actively working on.
    -   **Output:** `$VESSENCE_DATA_HOME/audit_reports/edu_audit_s<section>_a<assignment>_<ts>.{md,json}`
    -   **Answer types covered:** `number`, `text`, `math_expression`, `multiple_choice`, `vector`, `subspace_basis` (computes nullspace / columnspace / rowspace), `linear_system_solve` (computes a particular solution for the "infinite" case), `classify_and_reach`, `invertibility_with_blank`, `solve_system_with_basis` (computes particular + null basis).
    -   **Lint heuristics:** unrendered Jinja `{{ }}` / `{% %}`, unbalanced `$...$` math, brace mismatch, common typos (~20 in dictionary), short prompt, TODO/FIXME markers, LaTeX commands outside `$...$`/`\begin{}` envs, leaked `Fraction(a, b)` reprs. **Display-layer checks** on the post-submit fragment: rendered "Your answer:" equals a known answer-type identifier (Jinja filter signature bug — see 2026-05-10 `student_response` arg-swap), rendered "Your answer:" is empty or `(none)` despite a real submission.
    -   **LLM review:** single batched call via `claude_cli_llm.completion_json(tier="agent")` covering all questions in one prompt; degrades gracefully if the LLM CLI is unavailable.
    -   **Safety:** refuses to run against non-localhost base-urls (DB is hardcoded local); cleanup `DELETE` is restricted to attempts owned by the audit student AND started within the last 24h; `try/finally` cleans up an in-progress attempt if the loop crashes mid-run.
    -   **Verdict semantics:** `incorrect` from the grader → high-severity `grader_canonical_mismatch`; `stale` / `locked` / `unknown` → high-severity `verdict_*` (audit data unreliable for that question).
    -   **Discovered during the May 9 2026 Codex-via-Playwright run** (system Chrome + CDP + DB peek). This skill replaces that whole dance with plain `httpx` + `dev-login` + the same DB peek for snapshot solutions.

-   **Skill: Google Cloud Billing Receipt Downloader**
    -   **File:** `agent_skills/google_cloud_receipts.py`
    -   **What it does:** Captures a one-time Playwright browser profile for `console.cloud.google.com`, enumerates open billing accounts via `gcloud billing accounts list`, scans Billing Transactions pages for receipt controls, and downloads the last `n` recent payment receipts.
    -   **CLI:**
        -   `python agent_skills/google_cloud_receipts.py capture-profile`
        -   `python agent_skills/google_cloud_receipts.py download --count 5 [--billing-account ACCOUNT_ID] [--out-dir DIR]`
        -   `python agent_skills/google_cloud_receipts.py download --start-date 2026-03-01 --end-date 2026-05-14`
        -   `python agent_skills/google_cloud_receipts.py list-accounts`
    -   **Filename convention:** `google_<month>_<day>_<year>_<amount>.pdf` when the page exposes both a receipt date and amount
    -   **Storage:** browser auth state in `$VESSENCE_DATA_HOME/data/browser_profiles/google_cloud_billing/`; downloads in `~/Downloads/google_cloud_receipts_<timestamp>/`
