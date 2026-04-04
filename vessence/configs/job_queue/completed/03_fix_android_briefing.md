# Job: Fix Android Daily Briefing

Status: complete
Completed: 2026-03-24 15:00 UTC
Notes: Root cause was corrupt JSON in latest_briefing.json — line 78 had a missing closing quote ("Europe, instead of "Europe",). This caused json.JSONDecodeError → HTTP 500 on /api/briefing/articles. Fixed the data file and added defensive JSON parsing (strict=False + control char cleanup) to _load_briefing() to prevent future occurrences. Affects both web and Android since they share the same API.
Blocked: 2026-03-24 12:10 UTC
Notes: Code review shows Android briefing code is structurally correct — fetches from /api/briefing/articles, parses cards/categories, model fields match with @SerializedName. 71 articles exist on disk. API requires auth (returns 401 without session cookie). Server is healthy. Cannot reproduce without the physical Android device. Likely causes: (1) Auth session expired on Android — user needs to re-login, (2) Server URL changed after power shutdown — check ApiClient.getJaneBaseUrl(), (3) Network/tunnel issue. Need Chieh to check: what error does the app show? Is it "Failed to load briefing" or a blank screen?
Priority: 1
Model: opus
Created: 2026-03-24

## Objective
The daily briefing feature on Android is not working. Investigate the root cause and fix it.

## Context
- The daily briefing web page works at `/briefing`
- API endpoints exist: `GET /api/briefing/articles`, `GET /api/briefing/topics`, etc.
- Android has `BriefingAudioCache.kt` which fetches from `/api/briefing/audio/{id}/{type}`
- The briefing cron was just changed from hourly to 2:10 AM daily with `gemma3:12b` model
- The web briefing page works, so the issue is likely Android-specific

## Pre-conditions
- Access to Android source: `~/ambient/vessence/android/`
- Web briefing API is functional (verify first)

## Steps
1. Verify web briefing API works: `curl http://localhost:8081/api/briefing/articles`
2. Check Android briefing UI code — find the Activity/Fragment/Composable that displays briefings
3. Check how Android fetches briefing data — is it calling the right API endpoint?
4. Check if there are auth issues (Android needs to pass session cookie/token)
5. Check Android logs for errors related to briefing
6. Fix the identified issue
7. Verify the fix compiles

## Verification
- `curl http://localhost:8081/api/briefing/articles` returns valid JSON
- Android briefing code compiles without errors
- Briefing data flow from API to Android UI is correct

## Files Involved
- `android/app/src/main/java/com/vessences/android/` — briefing-related UI and data files
- `android/app/src/main/java/com/vessences/android/util/BriefingAudioCache.kt`
- `jane_web/main.py` — briefing API endpoints
- `vault_web/templates/briefing.html` — web version for reference

## Notes
- The briefing model was just switched from deepseek-r1:32b to gemma3:12b
- Cron schedule changed from hourly to 2:10 AM daily
- TTS Docker image is not available (logs show "TTS Docker image not available — skipping audio generation")
- Check if the issue predates today's changes or was caused by them
