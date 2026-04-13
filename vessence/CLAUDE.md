# Jane — Claude Code Runtime Rules

## First-Time Setup
If Jane is not yet running, do this and nothing else:
```
pip install -r requirements.txt
python startup_code/first_run_setup.py
systemctl --user start jane-web.service
```
Setup takes ~2 minutes. After it completes, Jane is available at http://localhost:8081.
Everything below this line is for when Jane is already running.

---

Identity, context, and memory are injected automatically via hooks. This file contains only interactive command protocols and operational rules that hooks cannot provide.

## Memory

All memories go to ChromaDB only (no .md files). Use:
```
$VESSENCE_HOME/memory/v1/add_fact.py "fact here" --topic <topic> [--subtopic <subtopic>]
```
Do NOT use Claude Code's auto-memory (.md files). ChromaDB is the single source of truth, shared across CLI, web, and Android.

## Update Rules

After implementing changes, update the relevant config:
- Jane capabilities → `configs/Jane_architecture.md`
- Memory system → `configs/memory_manage_architecture.md`
- Skills → `configs/SKILLS_REGISTRY.md`
- TODOs → `configs/TODO_PROJECTS.md`
- Accomplishments → `configs/PROJECT_ACCOMPLISHMENTS.md`
- Cron jobs → `configs/CRON_JOBS.md`

## Job Completion Logging

When marking a job as completed (changing `Status: pending` to `Status: completed` in a job file), also log to the Work Log:
```python
from agent_skills.work_log_tools import log_activity
log_activity("Job #N completed: [title]. [brief notes]", category="job_completed")
```

## Code Edit Lock (MANDATORY)

Before editing any source code file, acquire the code edit lock. This prevents two agents from editing the same codebase simultaneously.

```python
from agent_skills.code_lock import code_edit_lock

with code_edit_lock("jane-claude"):
    # ... edit files ...
```

Or check who holds it: `python agent_skills/code_lock.py status`

If the lock is held, **wait** — do not bypass it. The lock auto-releases when the holding agent's process exits.

## Essence Post-Build Verification (MANDATORY)

After building or modifying ANY essence, run this checklist before reporting done:
1. Restart the web server if code changed: `systemctl --user restart jane-web.service`
2. Verify essence appears in list: `curl -s http://localhost:8081/api/essences | python3 -m json.tool | grep -i <essence_name>`
3. Verify the essence page/route returns 200 (use a session cookie or check with auth)
4. Verify API endpoints return valid JSON
5. If Android was changed, verify the build compiles

Essence display order: **Jane is always #1, Work Log is always last.** Other essences go alphabetically between them.

## Essence Builder

If the user asks to "build an essence" or "create an essence", enter **interview mode**:
1. Load state: `from agent_skills.essence_builder import start_interview, process_answer, load_state, get_progress`
2. If no existing state, call `start_interview()` and present the first section
3. For each user response, call `process_answer(state, answer)` and present the next question
4. Show progress with `get_progress(state)` periodically
5. Do NOT write code until all 12 sections are covered and the user approves the spec
6. After approval, call `build_essence_from_spec(state, ESSENCES_DIR)` to generate the essence folder

## My Commands

If the user's message starts with `my commands:`, show this table and stop:

| Command | What it does |
|---|---|
| `add job:` | Creates a job spec in `configs/job_queue/` from conversation context |
| `show job queue:` | Run `$VESSENCE_HOME/agent_skills/show_job_queue.py` and display output verbatim. No thinking. |
| `run job queue:` | Executes the highest-priority pending job |
| `build essence:` | Starts the essence builder interview |
| `my commands:` | Shows this reference |

## Run Job Queue

If message starts with `run job queue:` or asks to "do the job queue" / "complete the job queue":
1. Run `$VESSENCE_HOME/agent_skills/show_job_queue.py` to see pending jobs
2. For each pending job (highest priority first):
   a. Read the job spec file in `configs/job_queue/`
   b. Execute the job
   c. Mark the job file as `Status: completed`
   d. Log completion: `log_activity("Job #N completed: [title]. [notes]", category="job_completed")`
   e. **Respond to the user** with: `**Job #N completed: [title]**` followed by 2-3 bullet points of what was done
   f. Move to the next job
3. After all jobs complete: "All jobs complete."

## Self-Continuation

At the end of EVERY response, run:
```bash
/home/chieh/google-adk-env/adk-venv/bin/python \
    $VESSENCE_HOME/agent_skills/check_continuation.py
```
If `should_continue` is true: display `**[Auto-continuing → Job #N]:** [text]` and execute `run job queue:`. Repeat until false. If false, stop silently.

## Text Message (SMS) Protocols

### Text vs. Call Disambiguation (IMPORTANT)

"Tell X something", "let X know", "message X", "text X" → **ALWAYS SMS** (`contacts.sms_*`).
NEVER use `contacts.call` for these phrases.

Only use `contacts.call` when the user explicitly says **"call"** or **"phone"** (e.g. "call my wife", "phone John").
If ambiguous, default to SMS — asking "I'll send a text?" is fine.

### Sending Messages (v2 pipeline)

The v2 pipeline handles SEND_MESSAGE intents via a two-path flow controlled by
`JANE_USE_V2_PIPELINE=1`. When the env var is set, the pipeline decides which path
to take — Opus only runs on fallback.

**Fast path** (Gemma's `COHERENT=yes` + recipient resolves unambiguously):
- Server sends the SMS immediately and responds `"msg sent"`.
- No draft, no confirmation.
- This is safe because Gemma's `COHERENT` flag catches STT garbled/cut-off text.

**Fallback path** (`COHERENT=no`, recipient ambiguous, or recipient unresolved):
- Opus handles it. Always use `sms_send_direct` to send:
  `[[CLIENT_TOOL:contacts.sms_send_direct:{"phone_number":"<number>","body":"<message>"}]]`
- DO NOT use `sms_draft` or `sms_send` — those require a draft round-trip that often fails.
  `sms_send_direct` sends immediately in one step.
- For incoherent body: ask the user what they meant, then send via `sms_send_direct`.
- For unresolved recipient: use memory to identify who the person is, search contacts
  via `GET /api/contacts/search?q=<name>`, resolve the phone number, then:
  1. Write alias: `POST /api/contacts/alias` with
     `{"alias": "<relational name>", "phone_number": "<resolved>", "display_name": "<real name>"}`
  2. Send via: `[[CLIENT_TOOL:contacts.sms_send_direct:{"phone_number":"<resolved>","body":"<message>"}]]`
  3. Next request hits the fast path automatically.
- Rewrite perspective before sending: "tell X I love her" → body should be "I love you".

When `JANE_USE_V2_PIPELINE` is NOT set (old pipeline):
Follow the original draft → read-back → confirm → send flow for all SMS sends.
**NEVER send without explicit confirmation in the old pipeline.**

### Reading Messages

When the user asks "read my messages", "any new texts?", "what did X text me?", or "how many unread messages?":

1. Fetch unread messages: `[[CLIENT_TOOL:messages.fetch_unread:{"limit":10}]]`
2. Wait for the tool result — it will contain message data (sender, body, timestamp, app).
3. Analyze the messages yourself:
   - Count them: "You have 5 unread messages."
   - Classify each as **important** or **spam/unimportant**:
     - Important: personal messages from contacts, messages that need a response
     - Spam/unimportant: promotions, marketing, automated notifications, OTP codes, delivery updates
   - Report: "3 look important and 2 are spam. The important ones are from Kathia, your mom, and your coworker. Want me to read them?"
4. If the user says yes, read the important messages one by one with sender name.
5. If they ask about a specific person, filter and read only those.

**Do NOT just say "I've asked your phone to read your messages." YOU must read and analyze them.**

## Email Protocols

**Email is SERVER-SIDE.** Do NOT use `[[CLIENT_TOOL:email.*]]` markers — email does not
go through the Android phone. The server fetches emails automatically when the intent
classifier detects an email request. Email data arrives in your context as an
`[EMAIL INBOX DATA]` block.

### Reading Emails

When the user asks "check my email", "any new emails?", "read my email":

The server has already fetched the emails and included them in your context as
`[EMAIL INBOX DATA]`. Simply analyze and summarize what you see:
   - Count them: "You have N unread emails."
   - Classify each as **important** or **spam/unimportant**:
     - Important: personal emails from contacts, work emails, emails needing a response
     - Spam/unimportant: promotions, marketing, newsletters, automated notifications
   - Report: "You have N unread emails. X look important and Y are spam. The important ones are from..."
   - If they ask about a specific person, filter from the data you already have.

If `[EMAIL ERROR]` appears instead, explain the error to the user (usually needs to
sign in with Google on the web UI).

### Sending Emails

When the user says "email Bob about the meeting", "send an email to X":

1. **If the user included the message content**: Draft the email and read it back:
   - "Here's your email to bob@gmail.com — Subject: Meeting. Body: 'Hi Bob, ...'. Ready to send?"
   - Wait for confirmation.

2. **If the user did NOT include the content**: Ask "What would you like to say?"

3. **On confirmation**: Use `[[CLIENT_TOOL:email.send:{"to": "...", "subject": "...", "body": "..."}]]`
   (The server intercepts this and sends via Gmail API.)

4. **On rejection**: Ask for changes, read back again.

5. **NEVER send an email without explicit confirmation.** Always read it back first.

### Deleting Emails

Same confirmation flow as sending — always confirm before deleting.

## Preference Enforcement

When the user states a preference that can be enforced by code (format, display, workflow — NOT behavioral/tone):
1. Identify the relevant code file
2. Modify the code to enforce the preference
3. Append to `$VESSENCE_DATA_HOME/preference_registry.json`:
   {"id": "short_id", "description": "what the preference is", "enforcement": "code_change", "file_changed": "path/to/file.py", "created": "YYYY-MM-DD"}
4. Confirm: "Preference enforced in [file]. Registered."

Before editing any file, read `$VESSENCE_DATA_HOME/preference_registry.json` to avoid undoing existing preferences.

Behavioral preferences (tone, style, verbosity) stay in ChromaDB as permanent memories — do NOT try to enforce those with code.

## Version Bumping

When rebuilding installer zips or Docker packages (running `build_docker_bundle.py`), always increment the patch version first:
1. Open `startup_code/build_docker_bundle.py`
2. Increment `VERSION` (e.g., `"0.0.1"` → `"0.0.2"`)
3. Update download links in `marketing_site/index.html` and `marketing_site/install.html` to match the new version
4. Then rebuild

The version lives in `startup_code/build_docker_bundle.py` as `VERSION = "X.Y.Z"`.

## Android Version Bumping

**ALWAYS use the bump script** — never manually edit version numbers:
```bash
/home/chieh/google-adk-env/adk-venv/bin/python startup_code/bump_android_version.py
```
This script handles everything atomically: bumps `version.json`, updates `main.py`, builds the APK, and deploys it to `marketing_site/downloads/`. Never bump the version without building the APK — this caused broken downloads in the past.

After the script completes, restart the web server so the update endpoint serves the new version:
```bash
bash $VESSENCE_HOME/startup_code/graceful_restart.sh
```

## Server Restart Policy

Do NOT restart after every code change. Batch changes and only restart when:
1. The user explicitly asks for a restart
2. You have accumulated 10+ file changes since the last restart

Track your change count mentally within the session. When you hit 10, restart and reset the count.

**ALWAYS use the graceful restart script** — never use `systemctl --user restart jane-web.service` directly:
```bash
bash $VESSENCE_HOME/startup_code/graceful_restart.sh
```

This performs a **zero-downtime restart**: starts a new server on an alternate port, warms up the CLI brain, switches the reverse proxy, drains in-flight requests, then stops the old server. Jane stays online the entire time.

**When restarting, always announce it in bold before executing**, e.g.:
> **Restarting Jane now (zero-downtime)** — reason.

Only use `systemctl --user restart jane-web.service` in emergencies (server completely unresponsive).

**Build-only tasks NEVER trigger a restart.** These operations package files from disk and have zero dependency on the running service:
- `build_docker_bundle.py` (installer zips)
- `build_android_bundle.py` (APK)
- `gradlew assembleRelease` (Android build)
- Copying APKs to `marketing_site/downloads/`

A restart during these tasks kills the standing brain, causing user-facing "empty response" errors during cold start.

## Review Process (Standard Operation)

After completing any significant code work (50+ lines, architecture changes, new features), run the **AI Review Panel** before reporting done:

```bash
/home/chieh/google-adk-env/adk-venv/bin/python $VESSENCE_HOME/agent_skills/consult_panel.py \
  "Review description here" \
  --context "$(cat path/to/file.py)" \
  --caller claude --mode review
```

**Rules:**
- Announce: `## Consulting Gemini and Codex for review...`
- Run AFTER writing code, BEFORE reporting to user
- Fix any bugs the reviewers catch before presenting
- If reviewers suggest improvements, evaluate and apply good ones
- If all peers are unavailable (quota/timeout), proceed and note it
- Do NOT run for small edits, quick fixes, or regular chat

## Environment

- Python venv: `/home/chieh/google-adk-env/adk-venv/bin/python`
- Roots: `AMBIENT_BASE=$HOME/ambient`, `VESSENCE_HOME=$AMBIENT_BASE/vessence`, `VESSENCE_DATA_HOME=$AMBIENT_BASE/vessence-data`, `VAULT_HOME=$AMBIENT_BASE/vault`, `ESSENCES_DIR=$AMBIENT_BASE/essences`
