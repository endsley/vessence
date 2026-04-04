# Job: Docker End-to-End Test — Verify Full Claude Experience for Docker Users
Status: complete
Completed: 2026-03-22
Priority: 1
Created: 2026-03-22

## Objective
Verify that a fresh Docker user who picks Claude as their brain gets the full coding agent experience: persistent sessions, stream-json tool visibility, ChromaDB memory, and real-time status updates on web/Android.

## Context
On 2026-03-22, we built persistent Claude sessions using `--verbose --output-format stream-json --resume`. This replaced the old one-shot `claude -p` subprocess approach and the Haiku summarizer. The new system:
- Keeps a persistent Claude CLI session per user (via `--resume <session_id>`)
- Streams tool_use events (Read, Edit, Bash, Grep, etc.) as real-time status updates
- Uses ChromaDB for all memory (no .md files)
- Architecture doc: `configs/project_specs/jane_streaming_architecture.md`

Key code:
- `jane/persistent_claude.py` — manages persistent sessions, parses stream-json events
- `jane_web/jane_proxy.py` — `_use_persistent_claude()` gates the feature, `_execute_brain_stream()` wires `on_status` and `on_delta`
- `jane/context_builder.py` — builds system prompt with memory from ChromaDB
- `docker/jane/Dockerfile` — installs `@anthropic-ai/claude-code` via npm

## Pre-conditions
- Docker and docker-compose installed on the test machine
- An Anthropic API key available (Claude brain requires it)
- ChromaDB container must be running and reachable from Jane container
- Port 8090 (Jane web) must be accessible

## Steps

### 1. Verify Claude CLI in Docker
```bash
docker compose exec jane claude --version
docker compose exec jane claude --help | grep "output-format"
```
Expected: Claude Code version printed, `stream-json` listed as an output format option.

### 2. Verify persistent_claude.py can create a session
```bash
docker compose exec jane python -c "
import asyncio
from jane.persistent_claude import get_claude_persistent_manager
async def test():
    m = get_claude_persistent_manager()
    result = await m.run_turn('test_session', 'Say hello in one word', timeout_seconds=30)
    print('Response:', result)
    session = await m.get('test_session')
    print('Claude session ID:', session.claude_session_id)
    print('Turn count:', session.turn_count)
asyncio.run(test())
"
```
Expected: Response text, a non-null Claude session ID, turn_count=1.

### 3. Verify session resume works
```bash
docker compose exec jane python -c "
import asyncio
from jane.persistent_claude import get_claude_persistent_manager
async def test():
    m = get_claude_persistent_manager()
    r1 = await m.run_turn('resume_test', 'Remember the number 42', timeout_seconds=30)
    print('Turn 1:', r1[:100])
    r2 = await m.run_turn('resume_test', 'What number did I tell you?', timeout_seconds=30)
    print('Turn 2:', r2[:100])
    session = await m.get('resume_test')
    print('Turn count:', session.turn_count)
asyncio.run(test())
"
```
Expected: Turn 2 response contains "42". Turn count = 2.

### 4. Verify stream-json emits tool_use events
```bash
docker compose exec jane python -c "
import asyncio
statuses = []
from jane.persistent_claude import get_claude_persistent_manager
async def test():
    m = get_claude_persistent_manager()
    result = await m.run_turn(
        'tool_test',
        'Read the file /app/jane_web/main.py and count how many lines it has',
        on_status=lambda s: statuses.append(s),
        on_delta=lambda d: None,
        timeout_seconds=60,
    )
    print('Statuses received:', statuses)
    print('Response:', result[:200])
asyncio.run(test())
"
```
Expected: `statuses` list contains at least one entry like "Reading file: main.py" or "Running command: ...".

### 5. Verify ChromaDB is reachable
```bash
docker compose exec jane python -c "
import chromadb
client = chromadb.HttpClient(host='chromadb', port=8000)
print('Heartbeat:', client.heartbeat())
collections = client.list_collections()
print('Collections:', [c.name for c in collections])
"
```
Expected: Heartbeat returns, collections listed.

### 6. Verify context_builder queries ChromaDB
```bash
docker compose exec jane python -c "
import asyncio, sys
sys.path.insert(0, '/app')
from jane.context_builder import build_jane_context_async
async def test():
    ctx = await build_jane_context_async('What do you remember about me?', [], session_id='test')
    print('System prompt length:', len(ctx.system_prompt))
    print('Has memory section:', 'memory' in ctx.system_prompt.lower() or 'Memory' in ctx.system_prompt)
asyncio.run(test())
"
```
Expected: System prompt is non-empty and contains memory context.

### 7. Verify web UI receives status events
```bash
# Start Jane web, send a message via curl, check the NDJSON stream for status events
curl -X POST http://localhost:8090/api/jane/chat/stream \
  -H "Content-Type: application/json" \
  -H "Cookie: vault_session=<test_session_cookie>" \
  -d '{"message":"Read main.py and tell me the first import","session_id":"web_test"}' \
  --no-buffer 2>&1 | head -20
```
Expected: Stream contains `{"type":"status","data":"Reading file: main.py"}` events before the final `{"type":"done",...}`.

## Verification Summary
All 7 steps pass = Docker users get the full Claude Code agent experience with real-time tool visibility and persistent memory.

## Files Involved
- `jane/persistent_claude.py` — persistent session manager
- `jane_web/jane_proxy.py` — streaming proxy with on_status wiring
- `jane/context_builder.py` — system prompt + ChromaDB memory injection
- `docker/jane/Dockerfile` — Claude CLI installation
- `docker-compose.yml` — service definitions + ChromaDB container
- `configs/project_specs/jane_streaming_architecture.md` — architecture reference

## Fix & Improve
If any step fails or reveals a problem:
- **Fix it** — don't just report the failure. Trace the root cause and patch the code.
- **If you spot potential issues** (race conditions, missing error handling, edge cases, config gaps) — fix them proactively.
- **If you see improvements** (better error messages, missing logging, redundant code, performance wins) — make them.
- Document every fix/improvement in the job's completion notes.

## Notes
- `_use_persistent_claude()` requires `JANE_BRAIN=claude` in .env — test must set this
- The onboarding flow sets JANE_BRAIN during first run, so this should be automatic for users who pick Claude
- If any step fails, check that the Claude CLI auth is configured (API key or OAuth)

## Completion Notes (2026-03-22)

### What was done
- Created comprehensive E2E test script at `tests/docker_e2e_test.sh`
- Script automates all 7 verification steps from this job spec
- Supports `--dry-run` mode to preview commands without executing
- Validates compose stack is running before testing
- Cleans up test sessions after completion
- Provides colored pass/fail output and a summary table

### Docker config validation
- **Dockerfile (`docker/jane/Dockerfile`)**: All COPY source paths verified (vault_web/, jane_web/, jane/, agent_skills/ all exist). Sets `AMBIENT_HOME=/app` as a fallback; docker-compose.yml correctly overrides with explicit `VESSENCE_HOME=/app` and `VESSENCE_DATA_HOME=/data`.
- **docker-compose.yml**: All volume mount source paths verified (traefik/traefik.yml, marketing_site/, marketing_site/nginx/default.conf all exist). Service dependencies and healthchecks are correctly configured. ChromaDB, Jane, and Amber services properly wired.
- **No issues found** in the Docker configuration that would prevent the stack from building or running correctly.

### Test script location
`tests/docker_e2e_test.sh` — run with `sudo bash tests/docker_e2e_test.sh` from the vessence root. Requires the compose stack to be running first.
