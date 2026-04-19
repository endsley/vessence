# Job: Web Automation Skill — Research-Backed Spec Only

Status: completed
Priority: 3
Created: 2026-04-17
Updated: 2026-04-18
Completed: 2026-04-18

**Deliverable landed at:** `configs/project_specs/web_automation_skill.md` (1062 lines, all 10 open decisions resolved 2026-04-18 with explicit `RESOLVED` markers, Section 10 research appendix cites Stagehand, browser-use, Skyvern, Playwright MCP, Vercel agent-browser, Browserbase skills). Any new session implementing Phase 1 should start by reading that spec end-to-end.

## Objective

Design a user-friendly Jane web automation skill using Playwright + CDP. This job is SPEC ONLY: no Playwright install, no implementation, no service restart until Chieh approves the spec.

The design goal is not "give Jane a browser API." The goal is: Chieh can ask Jane to do a web task in normal language, watch useful progress, answer only necessary questions, and later replay trusted workflows by name.

## Research Inputs

Read these implementations before writing the final spec:

- Stagehand: https://github.com/browserbase/stagehand
  - Relevant code: `packages/core/lib/v3/handlers/actHandler.ts`, `observeHandler.ts`, `extractHandler.ts`.
  - Design lesson: expose semantic `observe` / `act` / `extract`, but keep deterministic browser operations underneath. Stagehand also emphasizes preview, caching, and self-healing for repeatable workflows.
- browser-use: https://github.com/browser-use/browser-use
  - Relevant code: `browser_use/agent/service.py`, `browser_use/browser/session.py`, `browser_use/tools/service.py`, `browser_use/tools/views.py`, `browser_use/agent/message_manager/service.py`.
  - Design lesson: keep a browser session abstraction, a typed action registry, sensitive-data redaction, browser-state history, and message compaction separate.
- Skyvern: https://github.com/Skyvern-AI/skyvern
  - Relevant code: `skyvern/webeye/browser_manager.py`, `browser_artifacts.py`, `skyvern/forge/sdk/workflow/models/workflow.py`, `workflow/models/block.py`.
  - Design lesson: model long-running browser work as durable workflow runs with block status, browser session IDs, artifacts, console logs, HAR/video, validation, and cleanup.
- Microsoft Playwright MCP: https://github.com/microsoft/playwright-mcp
  - Design lesson: default to accessibility-tree snapshots over screenshots because they are faster, structured, and less ambiguous for LLMs.
- Vercel agent-browser: https://github.com/vercel-labs/agent-browser
  - Relevant code/docs: `skills/agent-browser/SKILL.md`.
  - Design lesson: compact element refs from snapshots are more agent-friendly than raw DOM or full Playwright schemas; persistent daemon/session flow keeps repeated interactions fast.
- Browserbase skills: https://github.com/browserbase/skills
  - Relevant code/docs: `skills/browser/SKILL.md`.
  - Design lesson: a CLI-like tool surface with `open`, `snapshot`, `click`, `type`, `screenshot`, `status`, and `stop` is easy for agents to use; screenshots should be fallback, not default.

## User-Friendly Product Requirements

Jane should hide browser-agent machinery from Chieh unless it matters.

1. Chieh says the task in normal language: "Jane, find the latest invoice from X and download it."
2. Jane answers with a short plan only when the task has ambiguity, risk, or multiple possible targets.
3. Jane streams progress in human terms: "I opened the billing page", "I found three invoices", "I need you to approve the download."
4. Jane asks for help only at decision points: login, 2FA, CAPTCHA, ambiguous option selection, destructive/risky action, or site breakage she cannot repair.
5. Jane never exposes selector jargon, DOM dumps, CDP events, or workflow internals in normal conversation.
6. Jane gives a final result with exactly what happened, where artifacts were saved, and anything she could not complete.
7. Saved workflows should feel like naming a routine: "Remember this as pay water bill", then later "Run pay water bill."

## Modes

### 1. Ad-Hoc Mode

For one-off tasks where Jane explores the website.

Flow:
1. Parse task: goal, target site/domain, expected output, risk level.
2. Create an ephemeral browser session unless the user explicitly chooses a saved profile.
3. Navigate and observe page state through accessibility snapshots first.
4. Use deterministic primitives for simple steps: navigate, click, fill, press, select, wait, download, screenshot.
5. Use semantic actions only when deterministic refs/selectors are insufficient.
6. Verify after each meaningful action with a fresh snapshot or extraction.
7. Escalate to Chieh only for user decisions, auth, or safety confirmations.

Ad-hoc mode should not save credentials, long-term cookies, or workflow scripts unless Chieh explicitly asks.

### 2. Saved Workflow Mode

For repeatable tasks Chieh wants Jane to run later.

Creation flow:
1. Chieh starts recording: "Watch me do this and remember it as X", or Jane offers after a successful repeated task.
2. Jane records high-level intent, deterministic actions, element refs, candidate selectors, page fingerprints, inputs, outputs, and validations.
3. Jane asks Chieh to name the workflow, choose when it is allowed to run, and confirm risky steps.
4. Jane stores the workflow in runtime data, not the repo:
   - `$VESSENCE_DATA_HOME/data/browser_workflows/<workflow_id>.json`
   - artifacts under `$VESSENCE_DATA_HOME/data/browser_runs/<run_id>/`
5. Jane stores no raw secrets in workflow files. Workflows reference secret/profile IDs only.

Replay flow:
1. Load workflow and inputs.
2. Run deterministic steps first.
3. If a selector/ref fails, try self-healing using current accessibility snapshot and the saved step intent.
4. If self-healing changes a risky step, ask Chieh before continuing.
5. Validate each checkpoint before moving on.
6. Save run trace, screenshots only when useful, console/network logs when debugging is enabled.

## Architecture

### Proposed Modules

- `agent_skills/web_automation/`
  - `skill.py`: Jane-facing skill entry point.
  - `browser_session.py`: Playwright browser/context/page lifecycle.
  - `snapshot.py`: accessibility snapshot, compact element refs, page fingerprints.
  - `actions.py`: typed deterministic action registry.
  - `semantic.py`: `observe`, `act`, `extract` wrappers.
  - `workflow.py`: workflow schema, recorder, replay engine.
  - `safety.py`: risk classifier, domain allowlist, confirmation gates.
  - `artifacts.py`: run directories, screenshots, traces, logs, redaction.
  - `profiles.py`: named browser profiles, cookies, storage state, auth handoff.
- `jane_web/jane_v2/classes/web_automation/`
  - Stage 2 handler/protocol for routing browser tasks without dumping all browser instructions into unrelated turns.
- Android/web UI integration:
  - Progress updates through existing Jane streaming/live announcement channels.
  - Optional "open live browser" view later, but not required for phase 1.

### Layering

1. Browser primitives: Playwright operations plus selected CDP operations.
2. Snapshot layer: compact accessibility-tree state and stable element refs.
3. Semantic layer: `observe`, `act`, `extract` over snapshots and schemas.
4. Workflow layer: record, replay, validate, repair.
5. Jane interaction layer: natural-language progress, confirmations, final summaries.

This keeps the user experience simple while preserving debuggability and deterministic replay.

## Tool Surface

Phase 1 should expose a small internal tool set:

- `browser.open(url, profile=None)`
- `browser.snapshot()`
- `browser.click(ref_or_selector)`
- `browser.fill(ref_or_selector, text, secret_ref=None)`
- `browser.press(key)`
- `browser.select(ref_or_selector, value)`
- `browser.wait(condition, timeout_ms)`
- `browser.extract(query, schema=None)`
- `browser.screenshot(reason)`
- `browser.downloads()`
- `browser.status()`
- `browser.stop()`

Do not expose every Playwright or CDP method to the model. More tools increase confusion and prompt size. Add CDP-specific operations only behind named helpers when a task proves it needs them.

## Workflow Schema

Each workflow file should contain:

- `id`, `name`, `created_at`, `updated_at`, `owner_user_id`
- `allowed_domains`
- `browser_profile_id`
- `inputs_schema`
- `secrets_refs`
- `risk_policy`
- `steps`
- `validations`
- `artifacts_policy`

Each step should contain:

- `label`: user-readable step name
- `intent`: natural-language purpose
- `action`: deterministic operation name
- `args`: non-secret arguments
- `selector_candidates`: role/text/css/xpath/ref candidates
- `page_fingerprint`: URL pattern, title, important text/roles
- `preconditions`
- `postconditions`
- `retry_policy`
- `repair_policy`
- `requires_confirmation`: true for irreversible or sensitive actions

## Safety

Jane must require explicit user confirmation before:

- Purchases, payments, transfers, trades, donations.
- Sending messages/emails/forms to another person or organization.
- Submitting medical, legal, tax, school, employment, or government forms.
- Deleting, cancelling, unsubscribing, or changing account/security settings.
- Entering credentials into a domain not previously approved for that profile.
- Continuing after semantic repair changes the meaning of a saved risky step.

Default restrictions:

- Ad-hoc sessions are ephemeral by default.
- Persistent profiles are per-site or per-purpose, not global.
- Domain allowlists are enforced per workflow.
- Secrets are references, never literal values in logs, screenshots, prompts, or workflow JSON.
- Screenshots and traces go through redaction where feasible and are saved only when useful.

## Authentication

Auth should be user-handoff first:

1. Jane opens the login page.
2. Chieh logs in or completes 2FA in the browser.
3. Jane detects completion and resumes.
4. Chieh can then approve saving a named browser profile for that domain.

Credential automation can come later. It must require domain binding and explicit secret references.

## CDP Usage

CDP is not the primary interface. Use CDP for:

- Network logs/HAR capture for debugging.
- Download interception and file naming.
- Console logs and page errors.
- Cookie/storage inspection inside approved profiles.
- Advanced wait conditions when Playwright primitives are insufficient.

Do not let Jane run arbitrary JS or mutate cookies/storage unless the workflow explicitly needs it and the safety layer allows it.

## Error Handling

Failures should be reported in user terms:

- "The page asked for 2FA."
- "The saved button moved; I found a matching 'Download invoice' button and need confirmation."
- "The website returned an error after submit. I saved the run trace."

Internally every run should record:

- Run ID, workflow ID if any, start/end time, status.
- Current URL/title per step.
- Action attempts and results.
- Validation failures.
- Screenshots only at failure, explicit user request, or visually dependent tasks.
- Console log and HAR when debug mode is enabled.

## Integration With Jane Pipeline

Add a Stage 2 class `web_automation` only after the spec is approved.

Routing behavior:

- Obvious browser commands route to `web_automation`.
- Ambiguous requests ask a clarifying question rather than opening a browser.
- Long-running automation should move into a background task and emit progress updates.
- Jane's Stage 3 brain should receive compact run state, not raw snapshots, unless debugging requires it.

The handler must respect existing Jane architecture:

- Do not inject web automation protocol into unrelated turns.
- Use `$VESSENCE_DATA_HOME` for runtime workflows/artifacts.
- Use ChromaDB only for facts and user preferences, not workflow files.
- Keep Android and web behavior consistent.

## Testing Plan For Later Implementation

When implementation is approved:

- Unit-test workflow schema validation, safety gates, redaction, and domain allowlists.
- Add local static fixture sites for login, form fill, table extraction, download, changed-selector repair, and dangerous submit.
- Add Playwright integration tests against those fixtures.
- Verify artifact creation and cleanup.
- Verify saved workflow replay uses deterministic steps before semantic repair.
- Verify screenshots are not used when accessibility snapshots are enough.

## Deliverable For This Job

Write the full spec document under `configs/project_specs/` for Chieh approval. The spec should include:

1. User-facing behavior and UX copy style.
2. Module architecture.
3. Workflow JSON schema.
4. Safety policy.
5. Auth/session policy.
6. Run artifact policy.
7. Pipeline integration plan.
8. Implementation phases.
9. Open decisions for Chieh.

## Constraints

- Do NOT install Playwright.
- Do NOT write implementation code.
- Do NOT start a browser daemon.
- Do NOT restart `jane-web.service`.
- Keep this as a design/spec job until Chieh approves implementation.
