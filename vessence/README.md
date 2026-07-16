# Vessence Setup Runbook

This repository contains Vessence/Jane plus supporting automation, including the
education-project homework auditor for `classes.chiehwu.com`.

If you are a separate Codex instance setting this up for Chieh on a new
computer, read `AGENTS.md` first, then follow this file. Do not infer secrets,
do not print secrets, and do not copy old credential directories unless Chieh
explicitly asks for that. Re-authenticate tools on the new computer whenever
possible.

## Repository Layout

Expected local layout:

```text
~/ambient/
  vessence/          # this repository
  vessence-data/     # runtime data, .env, logs, credentials, ChromaDB
  vault/             # user documents/data
  venv/              # Python virtualenv created by setup.sh
```

Important paths:

- Code root: `~/ambient/vessence`
- Runtime env file: `~/ambient/vessence-data/.env`
- Example env file: `~/ambient/vessence/.env.example`
- Main setup script: `~/ambient/vessence/setup.sh`
- First-run env configurator: `~/ambient/vessence/startup_code/first_run_setup.py`
- Repo-backed Codex skills: `~/ambient/vessence/codex_skills/`
- Web app entry point: `~/ambient/vessence/jane_web/main.py`
- Education homework auditor: `~/ambient/vessence/agent_skills/edu_homework_audit.py`

## New Computer Quickstart

Install baseline tools first:

```bash
sudo apt update
sudo apt install -y git curl python3 python3-venv python3-dev ripgrep
```

For macOS, install equivalent tools with Homebrew:

```bash
brew install git python ripgrep
```

Clone the repo into the expected layout:

```bash
mkdir -p ~/ambient
cd ~/ambient
git clone <REPO_URL> vessence
```

Install and authenticate at least one AI CLI before running setup:

- Codex CLI if this machine will use OpenAI/Codex.
- Gemini CLI if this machine will use Gemini.
- Claude Code if this machine will use Claude.

Verify one of these commands exists:

```bash
command -v codex || command -v gemini || command -v claude
```

Run the installer from `~/ambient`, not from inside `vessence`:

```bash
cd ~/ambient
bash vessence/setup.sh
```

The setup script is intended to be idempotent. It creates `venv`,
`vessence-data`, `vault`, the runtime `.env`, installs Python dependencies,
seeds memory, configures Jane, installs repo-backed Codex skills into
`~/.codex/skills`, installs Codex's Chroma memory hook/MCP bridge when Codex CLI
is available, tests the web server, and installs the user service when
supported.

After setup, verify the web app:

```bash
curl -I http://localhost:8081/
systemctl --user status jane-web.service --no-pager
```

Useful logs on Linux:

```bash
journalctl --user -u jane-web.service -f
```

Manual server command if the service is not installed:

```bash
cd ~/ambient/vessence
../venv/bin/python -m uvicorn jane_web.main:app --host 127.0.0.1 --port 8081
```

## Runtime Secrets

Runtime secrets belong in:

```text
~/ambient/vessence-data/.env
```

Do not commit `.env`, service-account JSON, OAuth credential files, API keys, or
anything under `vessence-data/`.

Minimal values:

- `USER_NAME` - usually `Chieh`
- `JANE_BRAIN` - `gemini`, `openai`, or `claude`
- `GOOGLE_API_KEY` - required when `JANE_BRAIN=gemini`; also useful for some background services
- `OPENAI_API_KEY` - required when `JANE_BRAIN=openai`
- `ANTHROPIC_API_KEY` - required only for API-key based Claude paths

Optional values are documented in `.env.example`, including Google OAuth,
Cloudflare tunnel, Discord, Ollama/local LLM, and Tavily.

To rerun only the env/onboarding step after dependencies exist:

```bash
cd ~/ambient/vessence
../venv/bin/python startup_code/first_run_setup.py
```

To rerun only the standalone Codex Jane runtime integration:

```bash
cd ~/ambient/vessence
../venv/bin/python startup_code/install_codex_memory.py
```

This writes `~/.codex/hooks/jane_memory_hook.py`, persistent Jane runtime
instructions, and the `jane-memory` plus `jane-coordination` MCP registrations
in `~/.codex/config.toml`. Session and prompt hooks inject live coordination
context, post-tool hooks heartbeat active scoped claims, and the main Stop hook
releases any claims left open at session completion. The first interactive
Codex boot may ask to trust the hook via `/hooks`.

To rerun only the repo-backed Codex skill installation:

```bash
cd ~/ambient/vessence
../venv/bin/python startup_code/install_codex_skills.py
```

This copies every skill in `codex_skills/*` that has a `SKILL.md` into
`~/.codex/skills/`. Treat `codex_skills/` as the durable Git-tracked source and
`~/.codex/skills/` as the local runtime install target.

## Google Cloud Setup

Install the Google Cloud CLI on the new machine before running these commands,
then verify it is available:

```bash
gcloud --version
```

On a new machine, prefer fresh login over copying old gcloud files:

```bash
gcloud auth login
gcloud config configurations create education || true
gcloud config configurations activate education
gcloud config set project "$PROJECT_ID"
gcloud auth application-default login
gcloud auth application-default set-quota-project "$PROJECT_ID"
```

`PROJECT_ID` is not stored in this repo. Ask Chieh for the correct Google Cloud
project ID if it is not already known.

Verify auth:

```bash
gcloud auth list
gcloud config list
gcloud auth application-default print-access-token >/dev/null && echo "ADC works"
```

Avoid user-managed service-account JSON keys unless there is no alternative. If
one is unavoidable, create a new key for this machine, store it outside the repo,
and point `GOOGLE_APPLICATION_CREDENTIALS` at that file:

```bash
mkdir -p ~/.config/secrets
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/.config/secrets/education-sa.json"
```

## Education Project / Homework Auditor

The auditor in this repo is:

```text
agent_skills/edu_homework_audit.py
```

It audits homework in the separate `classes.chiehwu.com` / `chieh_class_v2`
FastAPI app. This repo contains the auditor, not necessarily the whole teaching
app. If the teaching app is not already on the new computer, ask Chieh for its
repo/path, branch, and app-specific `.env`.

The auditor expects:

- Teaching app running locally at `http://localhost:8501`
- Teaching app has `ALLOW_DEV_LOGIN=true`
- Google Cloud CLI installed as `gcloud`
- Cloud SQL Auth Proxy installed as `cloud-sql-proxy`
- MySQL database `teaching_app` available through Cloud SQL Proxy at `127.0.0.1:3307`
- gcloud account can read Secret Manager secret `TEACHING_APP_DB_ROOT_PASSWORD`
- Python dependencies installed by the Vessence setup script

Verify the required CLIs:

```bash
gcloud --version
cloud-sql-proxy --version
```

Verify Secret Manager access:

```bash
gcloud secrets versions access latest --secret=TEACHING_APP_DB_ROOT_PASSWORD >/dev/null \
  && echo "Secret access works"
```

Start Cloud SQL Proxy in a separate terminal:

```bash
cloud-sql-proxy --port 3307 "$INSTANCE_CONNECTION_NAME"
```

`INSTANCE_CONNECTION_NAME` is not stored in this repo. Ask Chieh for it if it is
not already known.

Verify the local ports:

```bash
curl -I http://localhost:8501/
ss -ltnp | rg ':3307|:8501'
```

Run an audit from this repo:

```bash
cd ~/ambient/vessence
export VESSENCE_HOME="$HOME/ambient/vessence"
export VESSENCE_DATA_HOME="$HOME/ambient/vessence-data"
export VAULT_HOME="$HOME/ambient/vault"
export PYTHONPATH="$VESSENCE_HOME"

../venv/bin/python agent_skills/edu_homework_audit.py \
  --section 33 \
  --hw 1 \
  --mode audit-only
```

Reports are written to:

```text
~/ambient/vessence-data/audit_reports/
```

Use `--mode full-grade` only when Chieh explicitly wants the auditor to submit
and finish the homework attempt.

## Backup / Full Restore

For a full Vessence backup from an existing machine:

```bash
bash "$HOME/ambient/vessence/startup_code/backup_all.sh"
```

Backup archives may include sensitive files. Handle them as secrets.

For a full-machine restore, extract the archive and then follow:

```text
startup_code/INITIALIZE_NEW_SYSTEM.md
```

That restore path is broader than the new-computer quickstart above. Use it
when Chieh wants Jane's full data/memory/runtime state restored, not just the
repo and education tooling working on another machine.

## What A Future Codex Should Ask Chieh For

Ask only for missing values that cannot be discovered from the local repo:

- Git repository URL, if the repo is not already cloned
- Desired AI CLI/provider for `JANE_BRAIN`
- Google Cloud `PROJECT_ID`
- Cloud SQL `INSTANCE_CONNECTION_NAME`
- Teaching app repo/path/branch and app `.env`, if running the homework auditor
- API keys that belong in `vessence-data/.env`

Never ask Chieh to paste secrets into git-tracked files.
