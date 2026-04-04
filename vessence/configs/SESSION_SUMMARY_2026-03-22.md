# Session Summary — 2026-03-22

## Completed Today (in this session)

### Infrastructure
1. Fixed 64KB streaming crash (chunk-based NDJSON reading)
2. Jane web moved to systemd service (`jane-web.service`) — no more nohup conflicts
3. Docker installed + NVIDIA Container Toolkit configured (GPU in Docker works)
4. Context window monitor: auto-rotates Claude session at 70% capacity
5. Self-healing audit: runs every 6h, idle-only, fixes issues automatically in yolo mode
6. Essence scheduler: centralized cron for all essences (`cron/jobs.json`)
7. Essence isolation framework: dynamic route mounting, generic tool API
8. Memory janitor upgraded to Opus 4.6 with stricter merge rules (threshold 5)
9. Default Vessence models changed to all-Anthropic (Haiku cheap, Sonnet smart, Opus janitor)

### Daily Briefing Essence
10. News fetcher fixed: googlenewsdecoder resolves Google News URLs to real articles
11. Haiku summarization (short + long) for all articles
12. Tag-based redesign: multi-tag matching, category filters, relevance sorting by tag count
13. Cron changed to every 8 hours, idle-only, daily reset
14. XTTS-v2 audio generation (Docker + GPU, Barbora MacLean voice)
15. 13 female voice samples generated for comparison
16. DeepSeek R1:32b set as personal summarization model (via BRIEFING_SUMMARY_MODEL env var)

### Android App (v0.0.24 → v0.0.38)
17. Collapsible "Jane worked through N steps" status logs
18. Bubble splitting: new work cycle = new bubble
19. Copy button on both Jane and user bubbles
20. Session pre-warm on every app launch
21. Prompt Queue management bottom sheet
22. TTS voice picker with preview
23. Auto-listen after TTS (6s timeout, Android SpeechRecognizer fallback)
24. Smart auto-scroll (only when near bottom)
25. Update banner moved to ViewModel (persists across recomposition)
26. Download progress in Android status bar (DownloadManager)
27. Settings sync between server and Android
28. Jane's photo everywhere (login, empty state, top bar, essence list)
29. "New Session" text button replaces + icon
30. Essence ordering: Jane first, Work Log last
31. Header: "Jane Your personal genie" on one row
32. Version number shown in essence list
33. Briefing article cards show tag chips + tag count
34. Briefing audio: server XTTS-v2 with WiFi prefetch cache
35. Stop audio FAB works for single article + read-all

### Web (jane.html)
36. Collapsible status logs on completed bubbles
37. Bubble splitting for new work cycles
38. Copy button on Jane and user messages
39. Queue panel (slide-out drawer)
40. Voice input on queue panel
41. Smart auto-scroll (only when near bottom)
42. Essence ordering: Jane first, Work Log last
43. Header subtitle: "Your personal assistant · TTS on/off"

### Server / Backend
44. `/api/prompts/*` endpoints (list, add, delete, reorder, retry)
45. `/api/app/settings` GET/PUT for synced settings
46. `/api/app/installed` for logging APK installs to work log
47. `/api/tts/generate` XTTS-v2 endpoint with caching
48. `/api/briefing/audio/{id}/{type}` serve pre-generated audio
49. `/api/essence/{name}/tool/{tool_name}` generic essence tool API
50. `/essence/{name}` dynamic page routing for essences
51. Essence tools injected into Jane's system prompt via context_builder
52. New session properly kills persistent Claude CLI session
53. Work log: removed essence load/unload spam

### Preferences Saved to ChromaDB
- Always present permanent solutions first, not quick fixes
- When discovering bugs: immediately fix + add defensive code
- Before asking user questions: search memory/CLI/online first
- XTTS-v2 voice: Barbora MacLean
- Briefing summarization: DeepSeek R1:32b (personal), Haiku (Vessence default)
- Always bump version on every APK build
- Always update CHANGELOG.md before building (enforced by Gradle)
- Don't auto-compile APK — batch changes, build only when asked
- Job queue = implement everything start to finish, don't stop between jobs

## Pending Jobs (not yet implemented)
| # | Job | Priority |
|---|---|---|
| 01 | Docker E2E Test | ready (Docker installed) |
| 12 | Briefing Audio Smart Cache (WiFi prefetch) | 2 |
| 13 | Life Librarian Performance (5 optimizations) | 2 |
| 14 | Tools vs Essences Refactor | 1 |
| 15 | Web Prompt Queue UI verification | 2 |

## Pending Code Changes (not yet in APK)
- New Session kills Claude CLI session + auto-reinitializes
- Voice input auto-sends in empty chat state
- Update banner uses ViewModel state (won't flash/disappear)
- Briefing summarization model configurable via env var

## Current Model Assignments
| Task | My Model | Vessence Default | Where |
|---|---|---|---|
| Jane brain | Claude Sonnet 4.6 | Claude Sonnet 4.6 | persistent_claude.py |
| Conversation summarization | qwen2.5-coder:14b (Ollama) | Claude Haiku 4.5 | conversation_manager.py |
| Memory librarian | gemma3:4b (Ollama) | Claude Haiku 4.5 | search_memory.py |
| Memory janitor | Claude Opus 4.6 | Claude Opus 4.6 | janitor_memory.py |
| Briefing summarization | deepseek-r1:32b (Ollama) | Claude Haiku 4.5 | news_fetcher.py |
| Nightly audit | Claude via automation_runner | Claude via automation_runner | nightly_audit.py |
| TTS (chat) | Device TTS (instant) | Device TTS | AndroidTtsManager |
| TTS (briefing) | XTTS-v2 Barbora MacLean (GPU) | VITS p273 | tts_generator.py |
