# Web Automation Skill — Project Spec

**Status:** Pending Chieh approval
**Created:** 2026-04-18
**Source job:** `configs/job_queue/job_072_web_automation_spec.md`

---

## 1. User-Facing Behavior and UX Copy Style

Jane treats browser automation as an invisible skill. Chieh speaks in normal language; Jane does the browser work and reports in human terms. No selector jargon, no DOM dumps, no CDP events surface in conversation.

### Interaction flow

1. **Request.** Chieh says what he wants: "Find my latest water bill on the city website."
2. **Plan (conditional).** Jane shows a short plan only when the task is ambiguous, risky, or has multiple interpretations. For a clear task she just starts.
3. **Progress.** Jane streams short status lines as she works:
   - "Opening citywater.com/billing..."
   - "Found 3 invoices. Downloading the most recent one."
   - "Downloaded. Saved to ~/Downloads/water-bill-march-2026.pdf."
4. **Escalation.** Jane pauses and asks only when she must:
   - "The site is asking for your password. Can you log in? I'll wait."
   - "There are two accounts on file. Which one — the one ending in 4821 or 7733?"
   - "This will submit a payment of $47.20. Go ahead?"
5. **Result.** A short summary of what happened, where files landed, and anything unfinished.

### UX copy examples

| Situation | Jane says |
|---|---|
| Starting a task | "On it. Opening your account page now." |
| Found what she needed | "Found the March invoice — downloading it." |
| Needs login | "This site needs you to log in. I opened the login page — let me know when you're through." |
| 2FA prompt | "Looks like they want a verification code. Let me know when you've entered it." |
| Ambiguous choice | "There are two 'Download' buttons on this page — one for the summary and one for the full statement. Which do you want?" |
| Risky action | "This will cancel your subscription. Want me to go ahead?" |
| Failure | "The site returned an error after I clicked 'Submit.' I saved a trace in case you want to debug it." |
| Task complete | "Done. Your water bill is at ~/Downloads/water-bill-march-2026.pdf." |
| Saving a workflow | "Got it. I'll remember this as 'download water bill.' Just say 'run download water bill' anytime." |
| Replaying a workflow | "Running 'download water bill' now. One sec." |

### Anti-patterns (never do this)

- Never show raw selectors: `#billing-table > tr:nth-child(2) > td.amount`
- Never dump accessibility trees or DOM fragments into chat
- Never say "I executed a CDP command" or mention Playwright by name
- Never auto-proceed past a payment, form submission, or account change without asking

---

## 2. Module Architecture

### Directory layout

```
agent_skills/web_automation/
  __init__.py
  skill.py              # Jane-facing entry point; parses task, orchestrates flow
  browser_session.py    # Playwright browser/context/page lifecycle management
  snapshot.py           # Accessibility snapshots, compact element refs, page fingerprints
  actions.py            # Typed deterministic action registry (click, fill, navigate, etc.)
  semantic.py           # observe / act / extract — LLM-backed wrappers over snapshots
  workflow.py           # Workflow schema, recorder, replay engine, self-healing
  safety.py             # Risk classifier, domain allowlist, confirmation gates
  artifacts.py          # Run directories, screenshots, traces, logs, redaction
  profiles.py           # Named browser profiles, cookies, storage state, auth handoff

jane_web/jane_v2/classes/web_automation/
  __init__.py
  handler.py            # Stage 2 handler: routes browser intents to skill.py
  metadata.py           # Intent metadata and routing keywords
```

### Layer stack

```
┌─────────────────────────────────────────────┐
│  5. Jane Interaction Layer                  │
│     Natural-language progress, escalation,  │
│     final summaries. Emits streaming events │
│     via existing broadcast infrastructure.  │
├─────────────────────────────────────────────┤
│  4. Workflow Layer                          │
│     Record, replay, validate, self-heal.    │
│     Stored in $VESSENCE_DATA_HOME.          │
├─────────────────────────────────────────────┤
│  3. Semantic Layer                          │
│     observe() / act() / extract()           │
│     LLM-backed; used only when deterministic│
│     refs/selectors are insufficient.        │
├─────────────────────────────────────────────┤
│  2. Snapshot Layer                          │
│     Accessibility-tree snapshots, compact   │
│     element refs, page fingerprints.        │
│     Primary perception mode (not screenshots│
├─────────────────────────────────────────────┤
│  1. Browser Primitives                      │
│     Playwright API + selected CDP helpers.  │
│     navigate, click, fill, press, select,   │
│     wait, download, screenshot.             │
└─────────────────────────────────────────────┘
```

### Tool surface (internal, not user-facing)

These are the tools Jane's brain calls internally. Chieh never sees these names.

| Tool | Purpose |
|---|---|
| `browser.open(url, profile?)` | Launch browser, navigate to URL |
| `browser.snapshot()` | Accessibility-tree snapshot with compact element refs |
| `browser.click(ref)` | Click an element by ref or selector |
| `browser.fill(ref, text, secret_ref?)` | Fill an input; secrets resolved by ref, never literal |
| `browser.press(key)` | Keyboard press (Enter, Tab, Escape, etc.) |
| `browser.select(ref, value)` | Select dropdown option |
| `browser.wait(condition, timeout_ms)` | Wait for navigation, selector, or network idle |
| `browser.extract(query, schema?)` | Extract structured data from current page |
| `browser.screenshot(reason)` | Screenshot with stated reason (fallback, not default) |
| `browser.downloads()` | List completed downloads |
| `browser.status()` | Current URL, title, page state, session health |
| `browser.stop()` | Close browser session, save artifacts |

New tools are added only when a concrete task proves they are needed. Do not pre-expose CDP methods.

---

## 3. Workflow JSON Schema

### Workflow file

Stored at: `$VESSENCE_DATA_HOME/data/browser_workflows/<workflow_id>.json`

```json
{
  "id": "wf_pay_water_bill",
  "name": "pay water bill",
  "version": 1,
  "created_at": "2026-04-18T09:00:00Z",
  "updated_at": "2026-04-18T09:00:00Z",
  "owner_user_id": "chieh",
  "description": "Log in to citywater.com and pay the current bill.",

  "allowed_domains": ["citywater.com", "*.citywater.com"],
  "browser_profile_id": "profile_citywater",

  "inputs_schema": {
    "type": "object",
    "properties": {
      "payment_method": {
        "type": "string",
        "enum": ["card_ending_4821", "card_ending_7733"],
        "description": "Which payment card to use"
      }
    },
    "required": ["payment_method"]
  },

  "secrets_refs": ["citywater_login"],

  "risk_policy": {
    "max_risk_level": "high",
    "always_confirm": ["submit_payment", "change_account"]
  },

  "steps": [
    {
      "id": "step_01",
      "label": "Open billing page",
      "intent": "Navigate to the billing section of the city water site",
      "action": "navigate",
      "args": { "url": "https://citywater.com/billing" },
      "selector_candidates": [],
      "page_fingerprint": {
        "url_pattern": "citywater.com/billing",
        "title_contains": "Billing",
        "landmark_roles": ["heading:Current Balance"]
      },
      "preconditions": [],
      "postconditions": [
        { "type": "url_matches", "pattern": "*citywater.com/billing*" }
      ],
      "retry_policy": { "max_attempts": 2, "backoff_ms": 1000 },
      "repair_policy": { "allow_semantic_repair": true },
      "requires_confirmation": false
    },
    {
      "id": "step_02",
      "label": "Click Pay Now",
      "intent": "Click the Pay Now button to begin payment",
      "action": "click",
      "args": {},
      "selector_candidates": [
        { "strategy": "role", "value": "button", "name": "Pay Now" },
        { "strategy": "text", "value": "Pay Now" },
        { "strategy": "css", "value": "#pay-now-btn" }
      ],
      "page_fingerprint": {
        "url_pattern": "citywater.com/billing",
        "title_contains": "Billing"
      },
      "preconditions": [
        { "type": "element_visible", "ref": "Pay Now button" }
      ],
      "postconditions": [
        { "type": "url_matches", "pattern": "*citywater.com/payment*" }
      ],
      "retry_policy": { "max_attempts": 2, "backoff_ms": 1000 },
      "repair_policy": { "allow_semantic_repair": true },
      "requires_confirmation": false
    },
    {
      "id": "step_03",
      "label": "Confirm payment",
      "intent": "Submit the payment after user confirmation",
      "action": "click",
      "args": {},
      "selector_candidates": [
        { "strategy": "role", "value": "button", "name": "Confirm Payment" }
      ],
      "page_fingerprint": {
        "url_pattern": "citywater.com/payment/confirm"
      },
      "preconditions": [
        { "type": "element_visible", "ref": "Confirm Payment button" },
        { "type": "text_present", "value": "Amount:" }
      ],
      "postconditions": [
        { "type": "text_present", "value": "Payment successful" }
      ],
      "retry_policy": { "max_attempts": 1 },
      "repair_policy": { "allow_semantic_repair": false },
      "requires_confirmation": true
    }
  ],

  "validations": [
    {
      "after_step": "step_03",
      "check": { "type": "text_present", "value": "Payment successful" },
      "on_failure": "abort_and_notify"
    }
  ],

  "artifacts_policy": {
    "save_screenshots": "on_failure_only",
    "save_har": false,
    "save_console_log": false,
    "save_trace": true,
    "retention_days": 30
  }
}
```

### Selector candidate strategies

Tried in order; first match wins:

1. `role` — Accessibility role + name (most stable)
2. `text` — Visible text content
3. `ref` — Compact element ref from a previous snapshot
4. `css` — CSS selector (fragile, used as last resort)
5. `xpath` — XPath (escape hatch only)

### Run record

Stored at: `$VESSENCE_DATA_HOME/data/browser_runs/<run_id>/run.json`

```json
{
  "run_id": "run_20260418_093012_wf_pay_water_bill",
  "workflow_id": "wf_pay_water_bill",
  "started_at": "2026-04-18T09:30:12Z",
  "ended_at": "2026-04-18T09:31:45Z",
  "status": "completed",
  "steps_executed": [
    {
      "step_id": "step_01",
      "status": "ok",
      "url": "https://citywater.com/billing",
      "title": "City Water - Billing",
      "duration_ms": 2340,
      "repair_used": false
    },
    {
      "step_id": "step_02",
      "status": "ok",
      "url": "https://citywater.com/payment",
      "title": "City Water - Payment",
      "duration_ms": 1120,
      "repair_used": false
    },
    {
      "step_id": "step_03",
      "status": "ok",
      "url": "https://citywater.com/payment/confirm",
      "title": "City Water - Confirmation",
      "duration_ms": 3200,
      "repair_used": false,
      "user_confirmed": true
    }
  ],
  "artifacts": {
    "trace": "trace.json",
    "screenshots": []
  },
  "errors": [],
  "inputs_used": { "payment_method": "card_ending_4821" }
}
```

---

## 4. Safety Policy

### Actions that always require user confirmation

Jane must pause and ask before:

| Category | Examples |
|---|---|
| Financial | Purchases, payments, transfers, trades, donations, subscription changes |
| Communication | Sending messages, emails, or form submissions to another person/org |
| Official forms | Medical, legal, tax, school, employment, government submissions |
| Destructive | Deleting data, cancelling accounts, unsubscribing, changing passwords or security settings |
| Credential entry | Entering credentials on a domain not previously approved for that profile |
| Semantic repair drift | Self-healing changed the meaning of a saved risky step |

### Risk classification

Each action is classified at parse time:

| Level | Description | Confirmation required |
|---|---|---|
| `low` | Read-only navigation, data extraction, downloading public files | No |
| `medium` | Form fills with non-sensitive data, clicking through multi-step flows | No (unless workflow policy overrides) |
| `high` | Any action in the "always confirm" table above | Yes |
| `critical` | Multi-step financial transactions, bulk operations | Yes, with explicit summary of what will happen |

### Domain allowlist

- Workflows declare `allowed_domains`. Jane refuses to navigate outside them during replay.
- Ad-hoc mode has no domain restriction but still enforces risk classification.
- A global blocklist of known dangerous domains (phishing, malware) is maintained in `safety.py` and updated periodically.

### Secret handling

- Secrets are **never** stored as literals in workflow JSON, logs, screenshots, prompts, or conversation.
- Workflows reference secrets by ID (e.g., `"citywater_login"`). The secrets themselves live in `$VAULT_HOME` or the OS keyring.
- `browser.fill(ref, text, secret_ref="citywater_login")` resolves the secret at runtime and fills it without exposing the value to the LLM context.
- Screenshots and traces pass through a redaction layer that masks password fields and known sensitive elements before saving.

### Guardrails

- Jane does not execute arbitrary JavaScript on pages unless the workflow explicitly enables it and the safety layer approves.
- Jane does not mutate cookies or storage state outside of approved profile operations.
- Ad-hoc sessions are ephemeral by default — no persistent cookies, storage, or credentials unless Chieh explicitly asks to save a profile.

---

## 5. Auth / Session Policy

### Auth model: user handoff first

Jane does not log in on Chieh's behalf. She opens the door; he walks through.

1. Jane navigates to the login page.
2. Jane tells Chieh: "This site needs you to log in. I'll wait."
3. Chieh logs in manually (including 2FA if needed) in the browser.
4. Jane detects completion (URL change, presence of logged-in indicator, session cookie) and resumes.
5. If Chieh approves, Jane saves a named browser profile for that domain.

### Browser profiles

Stored at: `$VESSENCE_DATA_HOME/data/browser_profiles/<profile_id>/`

Each profile contains:
- `storage_state.json` — cookies, localStorage, sessionStorage (Playwright format)
- `profile_meta.json` — profile ID, display name, bound domains, created/updated timestamps, last used
- No raw passwords. Auth tokens/cookies are the stored state.

Profile rules:
- Profiles are per-site or per-purpose (e.g., `profile_citywater`, `profile_amazon`), never global.
- Profiles expire based on a configurable TTL. Default: 30 days since last use.
- Chieh can list, inspect, and delete profiles: "What browser profiles do I have?" / "Delete my Amazon profile."

### Session lifecycle

| Mode | Session behavior |
|---|---|
| Ad-hoc | Ephemeral context. Destroyed on `browser.stop()` or task completion. |
| Saved workflow | Loads named profile if specified. Session destroyed after run. Profile storage state updated if auth was refreshed. |
| Recording | Ephemeral unless Chieh approves saving a profile at the end. |

### Future: credential automation

Not in scope for phase 1. When added later:
- Credentials must be domain-bound (a secret can only be used on its declared domains).
- Secret references in workflows, never literals.
- Requires explicit opt-in per secret and per workflow.

---

## 6. Run Artifact Policy

### Directory structure

```
$VESSENCE_DATA_HOME/data/
  browser_workflows/           # Saved workflow JSON files
    wf_pay_water_bill.json
    wf_download_invoice.json
  browser_runs/                # Per-run artifacts
    run_20260418_093012_wf_pay_water_bill/
      run.json                 # Run record (see schema above)
      trace.json               # Step-by-step trace with compact snapshots
      screenshot_step03.png    # Only if failure or explicit request
      console.log              # Only if debug mode enabled
      network.har              # Only if debug mode enabled
    run_20260418_100000_adhoc/
      run.json
      trace.json
  browser_profiles/            # Saved auth profiles
    profile_citywater/
      storage_state.json
      profile_meta.json
```

### What is saved by default

| Artifact | When saved | Retention |
|---|---|---|
| `run.json` | Every run | 90 days |
| `trace.json` | Every run | 30 days |
| Screenshots | On failure, on user request, or for visually dependent tasks | 30 days |
| Console log | Debug mode only | 7 days |
| HAR | Debug mode only | 7 days |
| Downloaded files | Moved to user-specified location (default `~/Downloads/`) | Permanent (user manages) |

### Redaction

Before saving any artifact:
- Password fields are masked in screenshots (CSS overlay or pixel redaction).
- Secret values are replaced with `[REDACTED]` in traces and console logs.
- Network logs strip `Authorization`, `Cookie`, and `Set-Cookie` headers of their values.

### Cleanup

A periodic cleanup job (daily cron) removes artifacts past their retention window. Workflow files are never auto-deleted — only Chieh can remove them.

---

## 7. Pipeline Integration Plan

### Routing: Stage 2 class `web_automation`

A new Stage 2 class at `jane_web/jane_v2/classes/web_automation/` handles browser intent routing.

**Gemma Stage 1 keywords** (added to the classifier training):
- "go to website", "open site", "browse to", "look up on", "check the website"
- "find on [site]", "download from", "fill out the form"
- "run [workflow name]", "do [workflow name]"

**Routing rules:**
- Clear browser intent ("go to amazon.com and find...") routes directly to `web_automation`.
- Ambiguous requests ("find the cheapest flight") trigger a clarifying question: "Want me to search the web, or open a travel site and look?"
- Named workflow triggers ("run pay water bill") route to `web_automation` with `mode=replay`.

### Stage 2 handler behavior

```
1. Parse task: extract goal, target domain, expected output, risk level.
2. Check for matching saved workflow. If found and user said "run X", enter replay mode.
3. Otherwise, enter ad-hoc mode.
4. Spawn browser session (async background task).
5. Stream progress events through existing broadcast infrastructure.
6. On completion, emit final summary to the conversation.
```

### Long-running task handling

Browser tasks can take 30+ seconds. The handler:
- Moves execution to a background task immediately.
- Emits progress updates via the existing `StreamBroadcaster` / SSE channel.
- Jane's brain receives compact run state (current step, status, any questions), never raw snapshots or DOM.
- If the user sends a new message while a browser task is running, Jane can respond to it without blocking.

### Stage 3 brain context

When the brain needs to make a decision during browser automation:
- It receives: current URL, page title, compact element list (from accessibility snapshot), task goal, and what happened so far.
- It does not receive: raw HTML, full DOM, CDP event logs, or screenshot bytes (unless debugging).
- This keeps the context window lean.

### Cross-interface consistency

| Interface | Behavior |
|---|---|
| Web UI | Full streaming progress. "Open live browser" view deferred to later phase. |
| Android | Streaming progress via existing notification/chat channels. |
| CLI | Streaming progress in terminal. |

All three interfaces see the same progress events and final summary.

---

## 8. Implementation Phases

### Phase 1: Ad-hoc browsing (core)

**Ships:** Browser session management, snapshot layer, deterministic actions, safety gates, artifact storage, Stage 2 routing.

Deliverables:
- `browser_session.py` — launch/close Playwright browser, context, page lifecycle
- `snapshot.py` — accessibility snapshots, compact element ref generation, page fingerprints
- `actions.py` — typed action registry: navigate, click, fill, press, select, wait, download, screenshot
- `safety.py` — risk classifier, domain blocklist, confirmation gate logic
- `artifacts.py` — run directory creation, trace writing, screenshot redaction, cleanup
- `skill.py` — entry point that ties layers together; receives task from handler, orchestrates browser actions, streams progress, returns summary
- `jane_web/jane_v2/classes/web_automation/handler.py` — Stage 2 routing
- Gemma classifier update for web automation intents
- Unit tests for safety gates, action validation, artifact redaction
- Integration tests against local fixture sites (login page, form, table, download link)

**Not included:** Semantic layer, workflow recording/replay, browser profiles, credential automation.

**User can do after Phase 1:** "Go to weather.com and tell me tomorrow's forecast." "Open my bank's website." "Download the PDF from this page." All ad-hoc, ephemeral sessions.

### Phase 2: Semantic layer + profiles

**Ships:** LLM-backed observe/act/extract, browser profiles with saved auth state.

Deliverables:
- `semantic.py` — observe (describe what's on the page), act (perform a described action when deterministic refs fail), extract (pull structured data from a page given a query/schema)
- `profiles.py` — create, load, list, delete browser profiles; storage state persistence; domain binding; TTL expiration
- Auth handoff flow (Jane opens login page, detects completion, offers to save profile)
- Profile management commands: "What browser profiles do I have?" / "Delete my Amazon profile."
- Tests for semantic fallback, profile lifecycle, auth detection

**User can do after Phase 2:** "Log in to my water company — I'll enter the password — then download this month's bill." Profiles persist auth across sessions.

### Phase 3: Saved workflows

**Ships:** Workflow recording, replay, self-healing, named triggers.

Deliverables:
- `workflow.py` — workflow schema validation, recorder (captures steps during ad-hoc run), replay engine, self-healing (re-match elements using accessibility snapshots when selectors break)
- Recording flow: "Watch me do this and remember it as download water bill"
- Replay flow: "Run download water bill"
- Self-healing with confirmation gate: "The saved button moved; I found a matching one. Okay to proceed?"
- Workflow management commands: "List my workflows" / "Delete pay water bill"
- Tests for replay, self-healing, domain enforcement, confirmation gates on repaired risky steps

**User can do after Phase 3:** "Remember this as pay water bill." Then later: "Run pay water bill." Full recorded workflow replay with self-healing.

### Phase 4: Polish and advanced features

**Ships:** Debug mode (HAR + console capture), scheduled workflow runs, live browser view in web UI, credential automation (opt-in).

This phase is intentionally vague — scope depends on what Phase 1-3 surface as needs.

---

## 9. Open Decisions for Chieh

These require your input before implementation begins.

### 1. Playwright installation method  **— RESOLVED 2026-04-18**

**Decision:** Option A (Playwright-bundled Chromium). Option B rejected because Playwright's CDP surface is version-specific — an `apt-get upgrade` bumping system Chromium would silently break selectors or launch flags without our control.

**Install specifics:**

- **Python package**: `pip install playwright` into `/home/chieh/google-adk-env/adk-venv/`. Pin version in `requirements.txt` (e.g. `playwright==1.50.0`). Upgrades deliberate, never automatic.
- **Browser download location**: `PLAYWRIGHT_BROWSERS_PATH=$VESSENCE_DATA_HOME/playwright_browsers/`, NOT the default `~/.cache/ms-playwright/`. Survives venv rebuilds; lives with Vessence data.
- **Browser scope**: Chromium only. No Firefox or WebKit — saves ~360 MB, one reproducible test surface.
- **Disk budget**: ~180 MB (Chromium) + ~50 MB (Playwright pip + deps) = ~230 MB added footprint.

**Bootstrap (one-time, manual — never at server startup):**
```bash
/home/chieh/google-adk-env/adk-venv/bin/playwright install chromium
sudo /home/chieh/google-adk-env/adk-venv/bin/playwright install-deps chromium
```
The second command is separate because it needs sudo (installs libnss3, libatk1.0-0, libatk-bridge2.0-0, libdrm2, libxkbcommon0, libxcomposite1, libxdamage1, libxfixes3, libxrandr2, libgbm1, libasound2). Document in `configs/FIRST_TIME_SETUP.md`. Never invoke `playwright install` from jane-web startup — a 180 MB download would time out the systemd unit.

**Upgrade flow:**
1. Bump pin in `requirements.txt` via a deliberate PR.
2. `pip install -U playwright`
3. `playwright install chromium` (downloads the new build alongside the old one).
4. Old build stays on disk — rollback available by reverting the pin.

**Startup health check:**
- On jane-web start, a lazy check that `$PLAYWRIGHT_BROWSERS_PATH/chromium-<revision>/` exists for the pinned Playwright revision.
- Missing → log a warning ("Playwright Chromium not installed. Run: playwright install chromium") but **do not crash** the server.
- `web_automation` requests fail with a clear user-facing message ("Browser automation isn't set up yet — ask the admin to run `playwright install chromium`.") until the binary appears.

### 2. Browser visibility  **— RESOLVED 2026-04-18**

**Decision:** Option C (headless by default, visible on demand) with **lifecycle-aware auto-graduation** — workflows start visible during recording/early runs, automatically switch to headless after proving stable.

**Three real modes:**

| Mode | When | DISPLAY requirement |
|---|---|---|
| Headless | production runs, default | none |
| Visible local | recording / testing / "show me" requests | `DISPLAY` or `WAYLAND_DISPLAY` set |
| Stream (remote render) | Phase 4+ feature for Android users | noVNC or screenshot stream infra |

**Override precedence (most-specific wins):**

1. Per-run flag from prompt: phrases like "show me", "let me watch", "visible", "with the window open" force visible for this one run.
2. Per-workflow flag stored in the workflow JSON: `visible: true` during record mode, flips later.
3. Global default: headless.

**Auto-graduate from visible to headless:**

- Workflow recording starts with `visible=true` (user is actively watching).
- Each successful replay increments `consecutive_successes` in the workflow JSON.
- After **3 consecutive clean runs** (no errors, no self-healing events), Jane offers: *"<workflow> has run 3 times clean. Want me to stop showing the browser when I run this?"*
- On yes → `visible=false` in the workflow.
- Any failure resets the counter to 0 so if the site changes, you're watching again.
- Rationale for 3: flaky sites succeed once by luck; three clean runs is the cheapest confidence signal.

**DISPLAY availability fallback:**

- At launch, check `DISPLAY` / `WAYLAND_DISPLAY` env vars.
- Visible requested + display missing → log warning, fall back to headless, tell user in response: *"No desktop session available, running in the background."*
- Prevents hard-failing a phone-initiated request when laptop is asleep.

**Dev override:** `JANE_BROWSER_VISIBLE=1` env var forces visible for all tasks regardless of workflow flags. For debugging the skill itself, not end-user use.

**Stream mode (deferred):** rendering the browser into Jane's chat UI via noVNC/websockify or periodic screenshot streaming is a Phase 4 feature — enables phone-side "watch" without a desktop session. Out of scope for Phase 1.

**Implementation surface:**

```python
# browser_session.py
def launch(self, *, headless: bool | None = None) -> BrowserContext: ...

def _resolve_headless(self, explicit: bool | None) -> bool:
    if explicit is not None:
        return explicit
    if os.environ.get("JANE_BROWSER_VISIBLE") == "1":
        return not self._display_available()  # fall back to headless if no display
    if self.current_run.prompt_requested_visible:
        return not self._display_available()
    if self.workflow and self.workflow.visible:
        return not self._display_available()
    return True  # default: headless

def _display_available(self) -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
```

### 3. Concurrent sessions  **— RESOLVED 2026-04-18**

**Decision:** Option A (one session at a time) for Phase 1, with explicit queue semantics and stuck-state arbitration. Option B (true parallelism) deferred to Phase 4 once scheduled workflows ship.

**Rationale:**

- Single-user deployment (Chieh only in Phase 1–3); dominant pattern is "one task, then another."
- Two Chromium processes = ~600 MB RAM + two CDP channels + profile-lock races. Not free.
- Playwright supports multiple `BrowserContext`s inside ONE Browser process — if we later want parallelism, it's cheap to add without spawning a second browser.

**Queue semantics when a new task arrives while one is in-flight:**

| Current task state | New task behavior |
|---|---|
| Actively working (clicking / typing / navigating) | Enters FIFO queue (max depth 3). Jane tells user: *"I'll do that next — still on the first task."* |
| Waiting for user input (2FA, login handoff, confirmation) | Jane arbitrates: *"I'm still waiting for you to finish logging in to <domain>. Cancel that first, or finish it?"* User picks. |

**Cancellation is first-class:** the user can always say "cancel whatever you're doing in the browser"; Jane tears down the active context, preserves run record + artifacts up to that point.

**Input-wait timeout:** if the current task is paused waiting for user input for **>10 minutes with no activity**, Jane proactively prompts: *"Still stuck waiting on you for the login. Should I cancel?"* — prevents indefinite block.

**Shared browser, isolated contexts:** Phase 1 keeps ONE launched `Browser` (warm, reused), creates a fresh `BrowserContext` per task, `context.close()` when the task finishes. Same process, clean state between tasks.

**Deferred to Phase 4:**
- Parallel `BrowserContext`s (two workflows at once in the same browser process).
- Scheduled-workflow + interactive-task coexistence once cron-triggered workflows ship — cron runs shouldn't block the user's ad-hoc request.

**Implementation surface:**

```python
# browser_session.py — module-level singleton
class BrowserSessionManager:
    _browser: Browser | None = None           # launched once, reused
    _active: BrowserContext | None = None     # current task's context
    _active_task: ActiveTask | None = None    # id, state, waiting_for
    _queue: asyncio.Queue[QueuedTask] = ...   # maxsize=3

    async def submit(self, task: Task) -> RunHandle:
        if self._active_task is None:
            return await self._run_now(task)
        if self._active_task.state == "waiting_for_user":
            return await self._prompt_user_cancel_or_queue(task)
        return await self._enqueue(task)  # normal FIFO

    async def cancel_active(self) -> None:
        if self._active:
            await self._active.close()
        self._active_task = None
        # drain next queued task if any
```

### 4. Workflow storage location  **— RESOLVED 2026-04-18**

**Decision:** `$VESSENCE_DATA_HOME/data/browser_workflows/` with the full layout and semantics below. Confirmed the location; added every follow-on needed for implementation.

**Directory layout:**
```
$VESSENCE_DATA_HOME/data/browser_workflows/
  index.json                      # name → workflow_id mapping
  <workflow_id>.json              # one file per workflow
  archived/                       # soft-deleted, restorable for 30 days
    <workflow_id>.json
  imports/                        # drop-zone for shared workflows (Phase 4+)
```

**File format:** JSON. Matches Vessence convention (`preference_registry.json`, agent state). No YAML dependency.

**Workflow id:** opaque 16-char hex slug via `secrets.token_hex(8)`. **Never the user-given name** — names can be edited, and if names were filenames, rename would break every run-record cross-reference. Name lives as a field inside the JSON; `index.json` maps name → id.

**Index file semantics:**
- O(1) name lookup without scanning every workflow file.
- Rebuildable at any time via `workflow.rebuild_index()` by scanning `*.json` in the dir (ground truth).
- Corrupted index is a warning, not a hard error — system keeps running off the per-workflow files.

**Name lookup from chat:**
- Case-insensitive (`"Run Water Bill"` → `water-bill`).
- Fuzzy match via rapidfuzz on typos (`"water bil"` → suggests `water-bill`). Same pattern as `music_play/handler.py` playlist lookup.
- Slugification: non-`[a-z0-9-_ ]` characters normalized by the indexer so voice-transcribed names match.

**Schema versioning:** every workflow JSON has `"schema_version": 1` at the top level. Missing field → assume v1. Version bumps go through explicit migrations in `workflow.py` — no silent schema drift.

**Edit semantics:**
- Editing a workflow bumps `updated_at`, KEEPS `workflow_id`. Re-runs pick up the new version.
- Run records reference `workflow_id`, not content — historical runs stay linkable after edits.

**Delete semantics (soft delete default):**
- User: *"delete the water-bill workflow"* → Jane confirms → file moves to `archived/<workflow_id>.json`, index updated.
- Restorable for 30 days via `workflow.restore(id)`.
- Hard delete: explicit `workflow.purge(id)` or automatic after 30 days in archive.
- Rationale: workflows take recording effort; accidental delete must be reversible.

**Backup coupling:**
- `browser_workflows/` is **included** in the USB data backup (all of `data/` is).
- Master secret key at `config/secret_master.key` is **excluded** per #5 resolution.
- Consequence: restoring a backup without the master key → workflows load fine, but any `secret_ref` fails with `SecretDomainMismatch` at runtime. User must re-enter credentials. Intentional — protects against a stolen backup.

**Git:** the whole `data/` tree is already `.gitignore`d. Workflows live entirely outside source control.

**Discoverability:** *"what workflows do I have?"* → Jane reads `index.json`, lists names + descriptions. Metadata only; never dumps full JSON into chat.

**Multi-user (deferred):** Phase 4+ uses per-user prefix `data/browser_workflows/<user_id>/...`. Phase 1-3 is single-user so no prefix needed.
- **Alternative:** Store in `$ESSENCES_DIR/web_automation/workflows/` if you want them closer to essence data.
- **Recommendation:** `$VESSENCE_DATA_HOME` — consistent with how other runtime data is stored.

### 5. Secret storage backend  **— RESOLVED 2026-04-18**

**Decision:** Option A (filesystem under `$VESSENCE_DATA_HOME`) with explicit Fernet encryption. OS keyring rejected because `jane-web.service` runs as a headless `systemctl --user` unit and GNOME Keyring/`libsecret` require an unlocked desktop session — it would work interactively and fail in production.

**Storage layout:**
```
$VESSENCE_DATA_HOME/
  data/
    browser_secrets/
      <secret_id>.enc        # Fernet-encrypted {username, password, notes}
      index.json             # id → {domain, label, created_at, last_used}
      audit.log              # one line per get() — domain, id, ts, caller
  config/
    secret_master.key        # 0600-perms Fernet key, EXCLUDED from backups
```

**Why the master key lives outside `data/`:** an accidental rsync or stolen backup of `data/` hands over ciphertext without the decryption key. Backups must explicitly exclude `config/secret_master.key`. Migrating to a new machine = re-enter secrets OR manually copy the key file.

**Encryption:** Python `cryptography.fernet.Fernet` — AES-128-CBC + HMAC-SHA256, ~15 lines of wrapping. Each blob is a JSON dict encrypted before write, decrypted only inside `SecretStore.get()`.

**Permissions enforced on module load:**
- `data/browser_secrets/` → `0700`
- `config/secret_master.key` → `0600`
- Refuse to operate if perms are loose.

**API surface** (`agent_skills/web_automation/secrets.py`):
```python
class SecretStore:
    def create(domain: str, label: str, username: str, password: str) -> str
    def get(secret_id: str, expected_domain: str) -> SecretValue  # raises SecretDomainMismatch
    def list() -> list[SecretIndexEntry]                          # metadata only
    def delete(secret_id: str)
    def rotate_master_key()                                       # re-encrypt all; rare
```

**Domain binding (non-negotiable):** every `get()` passes the current page's domain. The store compares against the secret's registered domain and raises `SecretDomainMismatch` on any divergence. This is the single most important guardrail — it's what stops a prompt-injection attack from exfiltrating bank credentials into an attacker-controlled page.

**Logging discipline:**
- `get()` logs `domain`, `secret_id`, `caller` — never the decrypted value.
- The `log_safe()` helper (see Section 4) is the only code path allowed to emit secret-adjacent records. Using `f"filling {secret}"` anywhere in the codebase is a bug.
- Artifact redaction (Section 6) replaces decrypted values with `[REDACTED:<secret_id>]` in traces, screenshots (OCR'd fields masked), and replay debug dumps.

**Audit + rotation:**
- `last_used` updated on every successful `get()`; stale secrets easy to prune.
- Optional `audit.log` for post-incident review — domain + id + ts + caller, one line per access.
- `rotate_master_key()` re-encrypts every blob with a new master; typically only after a suspected key compromise.

**Ripple into rest of spec:**
- Section 4 "Secret handling" — the `secret_ref` pattern materializes as `SecretStore.get(secret_id, expected_domain)`.
- Section 5 "Future: credential automation" — autofill fills via `get()` at the exact `fill()` call, value never held in the agent loop.
- Section 6 "Redaction" — substitutes `[REDACTED:<secret_id>]` which is stable across runs and safe to log.

### 6. Artifact retention defaults  **— RESOLVED 2026-04-18**

**Decision:** Replace flat TTLs with **outcome-tiered TTLs + total size budget + pin**. Failed runs and user-pinned runs are kept longer than routine successes; total disk footprint is capped so we never blow up storage.

**Tiered TTL by outcome:**

| Artifact | Success TTL | Failure TTL | Pinned |
|---|---|---|---|
| Run record JSON | 90 days | 90 days | forever |
| Screenshots | 14 days | 90 days | forever |
| Playwright trace (`trace.zip`) | 7 days | 90 days | forever |
| HAR / console logs | 7 days | 30 days | forever |
| Video (debug mode, opt-in) | 7 days | 30 days | forever |

**Total size budget:** soft cap **2 GB** on `$VESSENCE_DATA_HOME/data/browser_runs/`. When over cap, cleanup sweeps in this order:
1. Evict entries past their TTL (per table above).
2. If still over cap, evict oldest **non-pinned successful** runs — artifact-by-artifact in cost order (video → HAR → trace → screenshots), preserving `run_record.json` until the run itself is evicted.
3. Never evict pinned runs or failed runs that are still inside their TTL.

**User pin:** user says *"save this run for <workflow>"* → Jane writes `"pinned": true` into the run record. Pinned runs never auto-purge. Useful for "the canonical good run" as a replay reference.

**Cleanup cadence:** lightweight sweep at jane-web startup + every 24 h afterward. NOT via cron (we killed the generic scheduler — see essence_scheduler cleanup from 2026-04-18). Baked into the existing `_background_tasks` set next to `_reap_stale_sessions_loop`.

**Debug mode toggle:** default traces OFF, HAR OFF, video OFF — too expensive for routine runs. Turned on via `"debug": true` in the workflow JSON or `JANE_BROWSER_DEBUG=1` env for one-off. Traces + HAR are **auto-enabled on any failure**, retroactively written to the run dir so the next debug cycle has material.

### 7. Phase 1 scope confirmation  **— RESOLVED 2026-04-18**

**Decision:** Keep Phase 1 tight as originally spec'd. Ship deterministic actions + accessibility snapshots first; defer the dedicated semantic layer to Phase 2.

**The honest Phase 1 model (made explicit — wasn't spelled out in the original rec):**

Phase 1 doesn't mean "no LLM reasoning about pages" — it means **Opus (the existing Stage 3 brain) does the semantic reasoning, not a dedicated `semantic.py` module.** The loop is:

1. User: *"Go to weather.com and tell me tomorrow's forecast."*
2. Stage 2 `web_automation` handler routes to `skill.py`.
3. `skill.py` opens browser, takes a snapshot, streams it + the user task to Opus via Stage 3.
4. Opus emits tool calls in Jane's existing CLIENT_TOOL / JSON tool format: `browser.navigate("weather.com")`, `browser.snapshot()`, `browser.extract("tomorrow's high temperature", ref="e42")`.
5. Deterministic actions in `actions.py` execute them. Snapshots + extract return data Opus narrates back to the user.

This is free — we're already paying for Opus. Stagehand, browser-use, and Vercel's agent-browser all use this same pattern; their "semantic layer" is a cost + caching optimization, not a prerequisite.

**What Phase 2's `semantic.py` adds (why it's Phase 2, not Phase 1):**

- **Cheaper model for observe/act** — swap Opus for a local qwen or small cloud model on routine browser reasoning → ~10-50× per-turn cost drop.
- **Cached action resolution** — "click the Download button on watercity.com" resolved once, cached, replayed without any LLM call.
- **Self-healing** — when a selector breaks, semantic layer re-matches against the current snapshot.

**Phase 1 delivers:**

| Example | Works in Phase 1? |
|---|---|
| "Go to weather.com and tell me tomorrow's forecast" | ✓ Opus drives snapshot + extract |
| "Open my bank's website" | ✓ `browser.navigate(url)` |
| "Download the PDF from this page" | ✓ Opus picks link ref, `browser.click(ref)` triggers download interception |

**Phase 1 explicitly cannot do** (upgrade paths are clean, not boxed in):

- Save/replay a workflow → `workflow.py` in Phase 3.
- Stay logged in across sessions → `profiles.py` in Phase 2.
- Auto-fill credentials → `secrets.py` + `profiles.py` in Phase 2-3.
- Self-heal when a saved selector breaks → `semantic.py` in Phase 2.

### 7. Phase 1 scope confirmation

Phase 1 deliberately excludes the semantic layer (LLM-backed observe/act/extract) and workflows. This means Phase 1 can only handle tasks where Jane can find elements by accessibility role/text. Is this acceptable, or should semantic observe/act be pulled into Phase 1?

**Recommendation:** Keep Phase 1 tight. Accessibility snapshots with role+text matching handle the majority of well-built sites. Semantic layer adds complexity and LLM cost — better to validate the core first.

### 8. Which sites to test first?  **— RESOLVED 2026-04-18**

**Decision:** Four sites, each chosen to cover a specific failure dimension rather than maximize breadth. Goal is to surface the edge cases that define Phase 1→2 priority, not to prove we work everywhere.

**1. `news.ycombinator.com` — the canary.**
- Read-only, static HTML, no JS rendering, no auth, no CAPTCHA.
- Tests: basic navigation, accessibility-snapshot extraction, element refs on real markup.
- Minimum bar: if this doesn't work, nothing else will.

**2. `en.wikipedia.org` — structured extraction.**
- Static, complex DOM with tables, sections, infoboxes.
- Tests: `browser.extract()` with a schema, table parsing, heading hierarchy.
- Catches "LLM picks wrong element from a dense page."

**3. `weather.gov` — government portal.** Deliberately NOT weather.com (paywall + aggressive anti-bot).
- Moderate JS, forecast grids, location-specific multi-step navigation.
- Tests: extracting data across multiple page sections, "page has multiple similar regions" edge case.

**4. Chieh's actual utility site — hero use case.** URL + account type TBD from Chieh.
- Auth-gated, login form, statement list, PDF download.
- Tests the ENTIRE stack: user-handoff login, profile save, session reuse, download interception, safety gate on "submit payment" controls.
- The real validation — does the architecture survive a real site.

**Deliberately deferred:**

- **Amazon / Walmart**: JS-heavy + anti-bot + CAPTCHA on anomalies. Worth testing only once the stack is stable; otherwise we burn Phase 1 on anti-bot, not architecture.
- **Bank**: high safety-gate value but legal/T&C friction around bank automation. Phase 2+ when safety gates are mature.
- **2FA-by-default sites (Gmail etc.)**: 2FA flow already covered by the utility site; no need to duplicate.

### 9. Scheduled workflow runs  **— RESOLVED 2026-04-18**

**Decision:** Defer to Phase 4. Keep Phase 3 focused on manual replay (the 80% of the value). Six named blockers must be resolved before Phase 4 ships scheduled runs — this list exists so we don't rediscover the gaps later.

**Blockers that must be resolved before scheduled runs can ship:**

1. **Concurrency with interactive tasks** (tied to #3). A 2 AM cron run colliding with a user ad-hoc task needs the parallel-BrowserContext path #3 deferred. No scheduled runs without that.
2. **Failure notification pipeline.** A run that fails at 2 AM needs to reach the user via existing Jane channels (Android push, web notification). Ship order: notification infra → scheduled runs.
3. **Auth expiry detection + recovery.** Saved profile cookies expire mid-cron → Jane detects, pauses, notifies ("water-bill needs you to log in again"), resumes next cycle.
4. **Retry policy.** Transient network failure shouldn't fail the whole run. Default: 3 retries with exponential backoff (30 s, 2 min, 10 min), then notify + park.
5. **Cron semantics.** Do NOT add a generic cron scheduler — we removed `essence_scheduler.py` on 2026-04-18 for runaway overlap (job 073 investigation). Scheduled workflows live as entries inside `workflow.json` with a `schedule: "0 8 1 * *"` field, triggered by ONE jane-web background task that maintains a singleton lock.
6. **Rate limiting per domain.** Can't hammer watercity.com 100× a day because user created 10 overlapping schedules. Per-domain minimum-interval enforcement.

**Phase 3 delivers manual replay** (`"run water-bill"`) — the workflow itself is where the interesting logic lives; cron is just convenience on top.

### 10. Workflow schema: flat steps vs typed DAG  **— RESOLVED 2026-04-18**

**Decision:** Phase 3 ships a flat `steps` array. Upgrade to typed DAG blocks in Phase 4 **only if** a real task demands branching/extraction-in-workflow/loops.

**Why not jump to typed DAG now:**

- Skyvern-style typed DAG (TaskBlock / NavigationBlock / ExtractionBlock / ConditionalBlock / LoopBlock) is powerful but nobody *needs* it for Phase 3 targets — "download this every month" workflows are linear.
- Typed DAG costs: schema validator, traversal engine, eventual visual editor. All deferred.
- Flat steps → readable, hand-editable, `diff`-friendly when debugging.

**Upgrade trigger:** first real workflow that hits a genuine branching need (e.g., *"if there's a bill due, pay it; if not, skip"*). Currently hypothetical.

**Migration path is already wired:** `schema_version` field (per #4 resolution) enables a mechanical v1 → v2 conversion, not a rewrite.

**Concrete v1 step shape:**

```json
{
  "schema_version": 1,
  "id": "a1b2c3d4e5f6g7h8",
  "name": "water-bill",
  "steps": [
    {
      "label": "Open login page",
      "intent": "Navigate to watercity login",
      "action": "navigate",
      "args": {"url": "https://watercity.com/login"},
      "selector_candidates": [],
      "preconditions": [],
      "postconditions": [{"url_matches": "watercity.com/(login|dashboard)"}],
      "retry_policy": {"max_attempts": 3},
      "requires_confirmation": false
    }
  ]
}
```

Each step's `action` ∈ `{navigate, click, fill, press, select, wait, extract, download}`. No nested blocks, no conditionals. Simple.

### 9. Scheduled workflow runs

Should Phase 3 include cron-triggered workflows (e.g., "download my water bill on the 1st of every month"), or defer that to Phase 4?

**Recommendation:** Defer to Phase 4. Phase 3 is already substantial with recording, replay, and self-healing. Scheduled runs add cron integration, failure notification, and retry logic.

---

## 10. Research Appendix — OSS Patterns We're Borrowing

Each design decision in sections 1-9 derives from a production browser-agent codebase. This appendix maps our spec back to source so future maintainers can trace "why we chose X" to the actual upstream implementation.

### 10.1 Stagehand — semantic handlers over accessibility trees

**Repo:** https://github.com/browserbase/stagehand (MIT)

**Key files referenced:**
- `packages/core/lib/v3/handlers/actHandler.ts` — implements `act()`: take a natural-language instruction ("click the Download button") plus the current accessibility snapshot, pick an element, execute a deterministic Playwright click.
- `packages/core/lib/v3/handlers/observeHandler.ts` — implements `observe()`: LLM returns a list of candidate element refs with confidence scores, no side effects.
- `packages/core/lib/v3/handlers/extractHandler.ts` — implements `extract()`: typed structured-data extraction against a provided schema.

**Design takeaways feeding our spec:**
- **Three-verb semantic surface** (`observe` / `act` / `extract`) is the right granularity for LLM agents. Our `semantic.py` module in section 2 mirrors this exact trio. Fewer verbs = less prompt confusion; more verbs = each one does less but model needs more plumbing.
- **Accessibility tree > raw DOM**: Stagehand's biggest architectural switch was from DOM parsing to Chrome's accessibility tree via Playwright. Reduces payload size 80-90%, which is a direct token/latency win for LLM calls. Our section 2 layer stack (snapshot layer #2) locks in accessibility-first. Sources: [Browserbase Stagehand v3 launch](https://www.browserbase.com/blog/stagehand-v3), [Dwarves breakdown](https://memo.d.foundation/breakdown/stagehand).
- **IFrame handling**: Stagehand calculates an absolute XPath per iframe, tags each snapshot with an `EncodedId`, then stitches them into a single combined tree. Our `snapshot.py` should follow this — naive iframe handling leaves elements invisible to the agent. Worth citing explicitly in the Phase 1 plan.
- **Preview + cache + self-healing**: Stagehand caches successful `act` resolutions so the same intent on the same page skips the LLM on replay. Our `workflow.py` replay engine (section 2 + 3) should cache deterministic selector resolutions per (workflow, step) — only re-query the LLM when the selector fails.

### 10.2 browser-use — typed action registry + sensitive-data plumbing

**Repo:** https://github.com/browser-use/browser-use (MIT)

**Key files referenced:**
- `browser_use/agent/service.py` — agent loop, binds tools to the LLM, tracks browser state history.
- `browser_use/browser/session.py` — `BrowserSession` abstraction: context, page, lifecycle independent of agent.
- `browser_use/tools/service.py` + `browser_use/tools/views.py` — typed action registry (each action has pydantic input schema, description, and handler).
- `browser_use/agent/message_manager/service.py` — message compaction for long-running loops.

**Design takeaways feeding our spec:**
- **Typed action registry** is strictly better than prose-only tool definitions. Our `actions.py` (section 2) should declare each action as a typed entry `{name, pydantic_schema, doc, handler}`. The LLM gets accurate validation errors instead of string-matching failures.
- **BrowserSession as a separate abstraction** lets multiple agents or workflow replays share one browser while remaining logically isolated (different contexts). Our `browser_session.py` in section 2 follows this — the session is NOT the skill; the skill uses a session.
- **Sensitive-data redaction caveat**: browser-use has documented gaps where redacted values leak into controller logs ([issue 713](https://github.com/browser-use/browser-use/issues/713)) and fields get placeholder values instead of real secrets ([issue 1062](https://github.com/browser-use/browser-use/issues/1062)). **Lesson for us**: every code path that logs arguments or writes artifacts must pass through a single redaction helper in `safety.py` — NEVER format a credential into a log line inline. Our section 4 "Secret handling" should name this redaction helper as the single source of truth for log/artifact output.
- **Message compaction**: for long agent loops, raw tool outputs blow the context window. browser-use compacts older turns to summaries. Our Phase 2+ spec should plan for this — Phase 1 can skip.

### 10.3 Skyvern — workflows as durable runs with artifacts

**Repo:** https://github.com/Skyvern-AI/skyvern (AGPL-3.0)

**Key files referenced:**
- `skyvern/webeye/browser_factory.py` — browser factory that emits artifact paths (HAR, video, screenshots) alongside the session.
- `skyvern/forge/sdk/workflow/models/workflow.py` + `block.py` — workflow as a DAG of typed blocks (TaskBlock, NavigationBlock, ExtractionBlock, CodeBlock, HttpRequestBlock, control-flow blocks).
- `skyvern/webeye/actions/handler.py` — action execution with per-step status tracking.

**Design takeaways feeding our spec:**
- **Durable run as first-class entity**: every automation creates a run record with start/end time, status, URL/title per step, attempts, validations, artifact pointers. Our section 6 "Run Artifact Policy" + section 3 "Run record" already mirror this pattern; the Skyvern source confirms the schema shape.
- **Typed workflow blocks vs. flat step lists**: Skyvern treats a workflow as a DAG of block types, not a linear script. Our section 3 workflow schema currently uses flat `steps`; that's fine for Phase 3 MVP, but **open decision: upgrade to typed blocks in Phase 4** to support branching / conditional / extraction blocks cleanly. Worth adding as open decision #10.
- **HAR + video artifacts**: Skyvern records the entire operation on video per run, plus HAR for debugging. Our section 6 "What is saved by default" should make HAR/video opt-in (debug mode) — they're heavy storage but invaluable when a workflow suddenly breaks.
- **Presigned-URL artifact access**: Skyvern stores artifacts in S3/Azure with metadata in Postgres, UI generates presigned URLs. For Jane's single-user case we can skip object storage and keep everything under `$VESSENCE_DATA_HOME/data/browser_runs/<run_id>/`, but the principle — artifacts separate from workflow definition — still applies.

### 10.4 Microsoft Playwright MCP — accessibility-first snapshots

**Repo:** https://github.com/microsoft/playwright-mcp (Apache-2.0)

**Design takeaways:**
- Playwright MCP's `browser_snapshot` tool returns the page's accessibility tree by default; `browser_take_screenshot` is a separate, explicit tool. This crystallizes the Stagehand lesson: screenshots are fallback, never default.
- Reinforces section 2 layer #2 (snapshot layer) as accessibility-first with screenshots as a debug/user-facing supplement.

### 10.5 Vercel agent-browser — compact element refs for agent prompts

**Repo:** https://github.com/vercel-labs/agent-browser (MIT)

**Key files referenced:**
- `skills/agent-browser/SKILL.md` — the prompt/behavior spec exposed to Claude Code skill users.

**Design takeaways:**
- **Compact element refs > raw Playwright schemas**: each interactive element in the snapshot gets a short opaque id (e.g. `e42`) that the agent uses in `click(e42)`. Stable within a snapshot; regenerated per snapshot. Our `snapshot.py` should emit refs in this format. Our section 2 "Tool surface" already uses `ref_or_selector` — lock that `ref` format to "short opaque string per snapshot."
- **Persistent daemon/session flow**: the browser stays open across agent turns so snapshots + clicks reuse the same page state. Our `browser_session.py` MUST keep the session alive across the whole task (ad-hoc) or workflow run (saved). Closing per tool call is a regression.

### 10.6 Browserbase skills — CLI-like minimal tool surface

**Repo:** https://github.com/browserbase/skills (MIT)

**Key files referenced:**
- `skills/browser/SKILL.md` — CLI-shaped tool set for Claude Code.

**Design takeaways:**
- **Minimal tool vocabulary**: `open`, `snapshot`, `click`, `type`, `screenshot`, `status`, `stop`. Our section 2 "Tool surface" lists 11 tools — comparable, and we should not grow it casually. Each additional tool = more agent confusion + larger prompt. Add only when a real task proves it's needed.
- **Screenshot as fallback tool, not first-line**: same lesson as Stagehand + Playwright MCP. Confirmed pattern across all three.

### 10.7 Open decisions added from research

**10.** Workflow schema — flat `steps` (current spec) vs. typed DAG blocks (Skyvern-style)? Recommend: ship Phase 3 with flat steps, upgrade to typed blocks in Phase 4 when we hit a task that needs branching/extraction-within-workflow.

### 10.8 Non-negotiable patterns (from cross-repo consensus)

All six projects agree on these, so they're hardcoded in the spec:

1. Accessibility tree is the default snapshot; screenshots are supplemental.
2. Semantic verbs are `observe` / `act` / `extract`; don't add more.
3. Browser session lives across the whole task, not per tool call.
4. Element refs are short opaque strings tied to the current snapshot.
5. Secrets flow as opaque references; never get stringified into logs, prompts, or workflow JSON.
6. Every automation produces a run record; artifacts live under a run-id directory.
