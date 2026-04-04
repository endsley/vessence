# Job #61: Android Briefing — Save Articles

Priority: 2
Status: completed
Created: 2026-03-31

## Description
Add save/bookmark functionality to the Android daily briefing screen, matching the web version. The backend API already exists.

## Result
- Added `SavedArticleEntry` data model to `BriefingModels.kt`
- Added save/unsave/fetch functions to `BriefingViewModel.kt` (API calls to `/api/briefing/saved`)
- Added bookmark icon to `ArticleCard` action row with category dropdown menu
- Saved state tracked via `savedArticleIds` set — filled bookmark when saved, outline when not
- Categories fetched from server, merged with defaults (Read Later, Important, Reference)
