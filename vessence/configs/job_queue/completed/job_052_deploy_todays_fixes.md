# Job #52: Deploy Today's Code Fixes (Restart Required)

Priority: 1
Status: completed
Created: 2026-03-29

## Description
Restart jane-web.service to deploy all code changes made on 2026-03-28/29 that are sitting on disk but not live.

### Changes pending deployment:
1. Standing brain CWD fix — changed from VESSENCE_HOME to /tmp (prevents CLAUDE.md interference)
2. MAX_TURNS_BEFORE_REFRESH — increased from 20 to 1000
3. LOCAL_LLM_MODEL — fixed default from claude-haiku (non-existent in Ollama) to gemma3:4b
4. Thematic short-term memory — new system implemented and tested, replaces per-turn writes
5. Janitor memory fixes — is_permanent bug, backfill for new format, cross-session dedup, log retention
6. CODE_MAP hook removal — read_discipline_hook.py no longer blocks searches
7. Persistent Gemini CWD fix — changed to /tmp
8. Persistent Gemini startup timeout — increased to 90s
9. Gemini env key loading — loads both GOOGLE_API_KEY and GEMINI_API_KEY

### Verification after restart:
- Jane web responds on jane.vessences.com
- Multi-turn conversation works (no empty responses)
- Standing brain doesn't hit 20-turn refresh (now 1000)
- Thematic memory creates/updates theme entries in ChromaDB
