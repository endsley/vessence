# Root Split Migration Plan

Reference: see `configs/ROOT_LAYOUT.md` for the steady-state definition of the three-root model and what belongs in each root.

Goal: make `/home/chieh/vessence` a shippable code/config repo, move personal files to `/home/chieh/vault`, move live runtime state to a separate data root, and preserve current behavior.

## Target Layout

Use three roots instead of overloading one:

- Code root: `/home/chieh/vessence`
- Personal file vault: `/home/chieh/vault`
- Live runtime/data root: `/home/chieh/vessence-data`

Why this split:

- `vessence` can be shipped publicly.
- `vault` holds user-owned files and documents.
- `vessence-data` holds mutable runtime state that is not a "file vault": `.env`, credentials, logs, ChromaDB, session state, SQLite web DBs, and similar machine-local artifacts.

## Required Runtime Contract

Code should stop assuming that `AMBIENT_HOME` is also the code root.

Introduce and use distinct environment variables:

- `VESSENCE_HOME=/home/chieh/vessence`
- `VESSENCE_DATA_HOME=/home/chieh/vessence-data`
- `VAULT_HOME=/home/chieh/vault`

Interpretation:

- `VESSENCE_HOME`: source code, configs, templates, Docker files
- `VESSENCE_DATA_HOME`: logs, `.env`, credentials, runtime JSON/SQLite, vector DB
- `VAULT_HOME`: user documents, images, audio, pdfs, research, videos, private files

Backward-compatibility during migration:

- Temporarily allow fallback order:
  - `VESSENCE_DATA_HOME`
  - `AMBIENT_HOME`
  - legacy hardcoded default

## Current State Classification

### A. Should remain in `/home/chieh/vessence`

- application code
- Docker files and compose files
- onboarding UI
- configs and templates
- project specs
- tests
- model assets that are intended to ship

### B. Should move to `/home/chieh/vault`

Current source: `/home/chieh/ambient/vault`

Includes:

- `documents/`
- `images/`
- `audio/`
- `pdf/`
- `videos/`
- `research/`
- `private/`
- `Music/`
- `video_games/`
- `others/`
- `conversation_history_ledger.db`
- `.hash_index.json`

### C. Should move to `/home/chieh/vessence-data`

Current source: `/home/chieh/ambient`

Includes:

- `.env`
- `credentials/`
- `logs/`
- `vector_db/`
- `data/jane_sessions.json`
- `user_state.json`
- `jane_sessions.json`
- `idle_state.json` if present
- `queue_session.json` if present
- runtime SQLite DBs currently under the code tree:
  - `vault_web/vault_web.db`
  - `amber/.adk/session.db`
- transient/runtime logs currently under the code tree:
  - `bridge.log`
  - `crash.log`

### D. Must be removed or sanitized from `/home/chieh/vessence`

These make the repo non-shippable today:

- personal references in docs/specs
- user-specific config content in `configs/amber_capabilities.json`
- runtime DBs/logs inside the repo
- empty/legacy local data roots:
  - `vessence/vector_db`
  - `vessence/vault`

## Code Changes Required Before Cutover

### 1. Split root semantics in configuration

Current problem:

- many modules treat `AMBIENT_HOME` as both code root and data root
- some modules also assume `vault` and `vector_db` live under that same root

Required change:

- centralize path derivation in `jane/config.py`
- convert callers to read:
  - code paths from `VESSENCE_HOME`
  - runtime state from `VESSENCE_DATA_HOME`
  - user files from `VAULT_HOME`

### 2. Stop loading runtime `.env` from the code repo

Current problem:

- Docker and several scripts assume `.env` is under the repo or the ambient root-as-code root model

Required change:

- read `.env` from `VESSENCE_DATA_HOME/.env`
- keep `.env.example` in the repo as the template only

### 3. Separate vault path from runtime path

Current problem:

- many tools derive the vault as `${root}/vault`

Required change:

- make vault resolution explicit via `VAULT_HOME`
- do not infer vault location from the runtime root

### 4. Separate vector DB path from vault path

Current problem:

- vector DB is currently inferred from the same root that also hosts logs and vault

Required change:

- make ChromaDB root explicit via `VESSENCE_DATA_HOME/vector_db`

### 5. Move mutable SQLite DBs out of the repo

Required change:

- `vault_web.db` should live under `VESSENCE_DATA_HOME`
- ADK session DB should live under `VESSENCE_DATA_HOME`

### 6. Update Docker bind mounts

Current problem:

- `docker-compose.yml` currently binds `./vector_db`, `./vault`, `./credentials`, `./.env`, `./user_profile.md`

Required change:

- code stays mounted from repo
- runtime state mounts from external data root
- vault mounts from external vault root

Recommended host layout for Docker:

- `${VESSENCE_DATA_HOME}:/app/data`
- `${VAULT_HOME}:/app/vault`
- repo mounted read-only where practical

Inside containers:

- `VESSENCE_HOME=/app/code`
- `VESSENCE_DATA_HOME=/app/data`
- `VAULT_HOME=/app/vault`

## Ordered Migration Steps

### Phase 1: Make the codebase path-safe

1. Add new root env vars and path helpers.
2. Update Python modules and shell scripts to use them.
3. Update Docker Compose and service files.
4. Update docs to describe the new split.

Validation:

- all services start with the old layout still in place
- all path resolution is via the new config layer

### Phase 2: Clean the repo

1. Remove runtime artifacts from the repo tree.
2. Remove or sanitize user-specific docs/spec examples.
3. Replace personal examples with generic placeholders.
4. Ensure `.gitignore` excludes all mutable state.

Validation:

- `rg` over the repo shows no user-specific facts except intentionally generic docs about external data files
- `find` shows no runtime DBs/logs/vector stores inside the repo

### Phase 3: Create new external roots

1. Create `/home/chieh/vault`
2. Create `/home/chieh/vessence-data`
3. Copy, do not move yet:
   - `/home/chieh/ambient/vault` -> `/home/chieh/vault`
   - selected runtime files from `/home/chieh/ambient` -> `/home/chieh/vessence-data`
4. Move repo-local runtime artifacts into `vessence-data`

Validation:

- compare file counts
- verify important files exist in new locations
- verify ChromaDB opens from the new root

### Phase 4: Cut over configuration

1. Export:
   - `VESSENCE_HOME=/home/chieh/vessence`
   - `VESSENCE_DATA_HOME=/home/chieh/vessence-data`
   - `VAULT_HOME=/home/chieh/vault`
2. Update systemd user services and cron jobs.
3. Restart Amber, Jane, vault web, and related services.

Validation:

- memory search works
- vault reads/writes work
- prompt queue works
- web UIs work
- logs write to `vessence-data/logs`
- identity essays and prompt list load from `/home/chieh/vault/documents`

### Phase 5: Observe before deleting `ambient`

1. Leave `/home/chieh/ambient` in place for a soak period.
2. Confirm no process reads or writes there anymore.
3. Only then archive or delete it.

Validation:

- `lsof` / targeted searches show no active references to `/home/chieh/ambient`
- fresh restart still works
- cron jobs still work

## Recommended Mapping From Current Ambient Root

- `/home/chieh/ambient/vault/*` -> `/home/chieh/vault/`
- `/home/chieh/ambient/vector_db/*` -> `/home/chieh/vessence-data/vector_db/`
- `/home/chieh/ambient/logs/*` -> `/home/chieh/vessence-data/logs/`
- `/home/chieh/ambient/.env` -> `/home/chieh/vessence-data/.env`
- `/home/chieh/ambient/credentials/*` -> `/home/chieh/vessence-data/credentials/`
- `/home/chieh/ambient/data/*` -> `/home/chieh/vessence-data/data/`
- `/home/chieh/ambient/user_profile.md` -> `/home/chieh/vessence-data/user_profile.md`
- `/home/chieh/ambient/user_state.json` -> `/home/chieh/vessence-data/user_state.json`
- `/home/chieh/ambient/jane_sessions.json` -> `/home/chieh/vessence-data/jane_sessions.json` or remove if duplicate after verification

## Known Blockers

The following must be addressed before deleting `/home/chieh/ambient`:

- many source files still default to `/home/chieh/vessence` as if it were the runtime root
- many docs still refer to `/home/chieh/ambient`
- Docker Compose currently models user data as living beside the repo
- some repo files still contain user-specific personal references
- some mutable DB/log files still live inside the repo

## Definition of Done

The migration is complete when all are true:

1. `/home/chieh/vessence` contains only shippable code, docs, templates, and intended assets.
2. `/home/chieh/vault` contains personal files only.
3. `/home/chieh/vessence-data` contains all mutable runtime state.
4. No running process depends on `/home/chieh/ambient`.
5. All services, cron jobs, memory retrieval, vault operations, and web UIs behave the same after cutover.
6. Repo scan shows no personal facts, secrets, runtime DBs, or logs.
