# Job: Sanitize All Personal Data from Source Code Before Docker Distribution

Status: complete
Completed: 2026-03-24 13:30 UTC
Notes: 20 files sanitized. All /home/chieh paths replaced with sys.executable or env vars. All hardcoded "chieh" usernames replaced with USER_NAME env var. .dockerignore updated. Dockerfiles have RUN cleanup. Zero remaining personal references in Docker-shipped code.
Priority: 1
Model: opus
Created: 2026-03-24

## Objective
Remove all hardcoded personal data (paths, usernames, tokens) from source code that gets COPIED into Docker images. These images will be distributed to users.

## Critical Files to Fix

### Hardcoded `/home/chieh/` paths (replace with env vars or Path.home()):
1. `jane/context_builder.py` (lines 407, 421) — hardcoded venv path
2. `jane/jane_session_wrapper.py` (line 16) — shebang with hardcoded venv
3. `jane/persistent_claude.py` (line 289) — hardcoded venv path
4. `jane_web/main.py` (lines 1524, 2178) — hardcoded venv path
5. `agent_skills/essence_scheduler.py` (line 35) — hardcoded venv path
6. `agent_skills/backfill_file_index_descriptions.py` (line 8) — hardcoded venv path
7. `jane/config.py` (line 108) — hardcoded venv path

### Hardcoded username "chieh":
8. `jane/config.py` (line 84) — `chieh_identity_essay.txt` hardcoded filename
   - Fix: use `{USER_NAME}_identity_essay.txt` from env var

### Discord tokens in test_code (12 files):
9. All test files in `test_code/` with hardcoded Discord tokens
   - Fix: replace with `os.environ.get("DISCORD_TOKEN")` or remove tokens
   - Also: ROTATE all exposed tokens immediately

## Steps
1. For each hardcoded venv path: replace with `sys.executable` or `shutil.which("python3")` or env var `PYTHON_BIN`
2. For chieh_identity_essay.txt: make filename dynamic using USER_NAME env var
3. For Discord tokens: replace with env var reads, rotate compromised tokens
4. Run `grep -rn "/home/chieh" jane/ jane_web/ agent_skills/ amber/ vault_web/` to find any remaining leaks
5. Run `grep -rn "chieh" jane/ jane_web/ agent_skills/ amber/ vault_web/ --include="*.py"` to find username references
6. Test that Docker build succeeds after changes
7. Verify no personal data in built image: `docker run --rm <image> find /app -name "*.db" -o -name ".env"`

## Verification
- `grep -rn "/home/chieh" jane/ jane_web/ agent_skills/ amber/ vault_web/` returns 0 results
- `grep -rn "chieh" jane/ jane_web/ agent_skills/ amber/ vault_web/ --include="*.py"` returns 0 results (except comments referencing the project)
- Docker images build successfully
- All services start and pass health checks after path changes

## Files Involved
- 7+ Python files with hardcoded paths
- 12 test files with Discord tokens
- jane/config.py (username reference)

## Notes
- This is a BLOCKER for any public Docker release
- The .dockerignore and Dockerfile RUN cleanup lines are already in place as a safety net
- But the source code itself should be clean — defense in depth
- After this job: the code should be distributable to anyone without revealing personal info
