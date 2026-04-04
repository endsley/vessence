# Job: Briefing UX improvements — read options, archive per-article, archive viewer
Status: completed
Priority: 1
Created: 2026-03-28

## Objective
Improve the Daily Briefing experience on Android with visible read-aloud options, per-article archiving, and an archive browser.

## Steps
1. **Brief/Full audio buttons on each article card** — Add two small audio buttons (Brief / Full) directly on each ArticleCard in the grid, not just in the detail sheet. Users should be able to tap play without opening the article.
2. **Archive button per article** — Add a dismiss/archive button (swipe or icon) on each article card. Tapping it marks the article as "heard/read" and moves it to an archive section. Archived articles disappear from the main feed.
3. **Archive viewer** — Add an "Archive" tab or section at the top of the briefing screen (or a button in the top bar) that shows all archived articles. User can browse, re-read, or play audio from the archive.
4. **Persist archive state** — Store archived article IDs in SharedPreferences (or server-side) so they survive app restarts.
5. **Read All should skip archived articles** — The "Read All (Brief/Full)" FAB should only read non-archived articles.

## Files Involved
- `android/.../ui/briefing/BriefingScreen.kt` — ArticleCard layout, archive UI
- `android/.../ui/briefing/BriefingViewModel.kt` — archive state management
- Possibly `jane_web/main.py` — server-side archive API if we want cross-device sync
