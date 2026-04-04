# Amber Troubleshooting Registry

This file tracks historical issues, failure modes, and verified fixes for the Amber Assistant system.

## 1. Process & Connectivity Issues
| Date | Issue | Root Cause | Verified Fix |
| :--- | :--- | :--- | :--- |
| 2026-03-14 | Amber not responding to mentions | Model `gemini-2.0-flash` discontinued for new users | Updated `agent.py` to use `gemini-2.0-flash-lite`. |
| 2026-03-14 | Bridge crash: `name 're' is not defined` | Missing `import re` in `discord_bridge.py` | Added `import re` to the top of the file. |
| 2026-03-15 | Stale Session `ValueError` | `adk web` running without `--session_service_uri memory://` causing SQLite sync conflicts | Updated `amber-brain.service` with correct flags and restarted server. |
| 2026-03-15 | Wrapper Crash | `jane_session_wrapper.py` missing error handling for memory updates | Wrapped `add_message` calls in `try-except` blocks. |
| 2026-03-15 | Watchdog DBUS Failure | Cron environment missing `$DBUS_SESSION_BUS_ADDRESS` | Exported correct bus path in `bot_watchdog.sh`. |
| 2026-03-14 | Bot "blind" to guild messages | "Message Content Intent" likely disabled in Discord Dev Portal | Temporarily swapped to Jane's token which has active intents. |
| 2026-03-14 | Channel ID mismatch | Bot listening on a channel ID that didn't exist in the current guild | Updated `DISCORD_CHANNEL_ID` via `discover_channels.py`. |

## 2. Memory & Intelligence Issues
| Date | Issue | Root Cause | Verified Fix |
| :--- | :--- | :--- | :--- |
| 2026-03-14 | `localvector` unsupported URI | `agent_skills/services.py` not loading before memory init | Created root `services.py` to ensure early registration. |
| 2026-03-14 | Memory merging too noisy | Comparing unrelated facts (grocery list vs coding) | Implemented "Layered Memory" with Topic/Subtopic tagging. |

## 3. Tool & Skill Issues
| Date | Issue | Root Cause | Verified Fix |
| :--- | :--- | :--- | :--- |
| 2026-03-14 | LiteLLM proxy failing | Missing `backoff` and `litellm[proxy]` extras | Installed `litellm[proxy]` in the ADK venv. |
| 2026-03-14 | Gemma identity confusion | No persona instruction in local query script | Updated `gemma_query.py` with explicit "You are Jane" system prompt. |

---
## Diagnostic Script Requirements (for `amber_health_check.py`):
- [ ] Check process existence (Brain & Bridge).
- [ ] Check port 8000 listening.
- [ ] Ping Gemini API with the *currently configured* model.
- [ ] Verify `import re` and other critical imports in bridge.
- [ ] Simulate a `/run` request to the Brain to see if it produces a valid JSON response.
- [ ] Verify Discord Token and Channel ID validity.
