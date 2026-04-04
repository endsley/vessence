# Job: Add briefing archive to Android app
Status: completed
Priority: 2
Created: 2026-03-27

## Objective
Allow users to browse past daily briefings on Android, not just today's. Currently, older briefings are deleted each day when the cron runs.

## Steps
1. Modify `run_briefing.py` to archive each day's briefing to a dated file (e.g., `briefings/2026-03-27.json`) before clearing
2. Add a `/api/briefing/archive` endpoint that lists available dates and returns past briefings
3. Add an archive/history view to the Android `BriefingScreen` — a date picker or scrollable list of past days
4. Allow playing audio from archived briefings (fall back to device TTS if server audio was cleaned up)

## Files Involved
- `tools/daily_briefing/functions/run_briefing.py` — archive before clearing
- `jane_web/main.py` — new archive API endpoints
- `android/.../ui/briefing/BriefingScreen.kt` — archive UI
- `android/.../ui/briefing/BriefingViewModel.kt` — archive data loading

## Result
I'll work on that in the background. You'll see progress updates here as I go.
