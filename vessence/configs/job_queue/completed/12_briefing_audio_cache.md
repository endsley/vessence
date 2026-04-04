# Job: Briefing Audio Smart Cache — WiFi Prefetch + Daily Cleanup

Status: complete
Completed: 2026-03-22
Notes: BriefingAudioCache.kt fully implements WiFi detection (isOnWifi), prefetchAll, downloadToCache, getCachedFile, and cleanupOldFiles. BriefingViewModel integrates all: cleanup on init, WiFi prefetch after article load, cache-first playback with server stream fallback.
Priority: 2
Created: 2026-03-22

## Objective
Automatically download all briefing audio files to the phone when on WiFi. Stream when on mobile data. Clear cached audio daily.

## Design

### WiFi Detection
- On briefing load, check `ConnectivityManager` for WiFi vs mobile
- WiFi: prefetch all audio files in background to app cache
- Mobile data: stream on demand (current behavior)

### Prefetch Flow (WiFi)
1. Briefing loads → fetch article list from API
2. For each article with audio, download `/api/briefing/audio/{id}/brief` to `context.cacheDir/briefing_audio/`
3. Show download progress (small indicator or silent)
4. When user taps speak → play from local cache (instant, no buffer)

### Stream Flow (Mobile)
- Same as current: `MediaPlayer` streams from URL directly

### Daily Cleanup
- On app startup, check if cached audio files are from yesterday or older
- Delete all files in `cacheDir/briefing_audio/` older than 1 day
- Matches the server-side daily reset of articles

## Files Involved
- `android/.../ui/briefing/BriefingViewModel.kt` — prefetch logic, cache-or-stream decision
- `android/.../util/BriefingAudioCache.kt` — new utility for download/cache/cleanup
- Uses `ConnectivityManager.getActiveNetwork()` for WiFi detection

## Key Code Locations
- `android/.../ui/briefing/BriefingViewModel.kt` — `speakArticle()` currently tries local cache then streams, needs WiFi detection for prefetch
- `android/.../util/BriefingAudioCache.kt` — already created with `isOnWifi()`, `prefetchAll()`, `cleanupOldFiles()`, `downloadToCache()`, `getCachedFile()`
- Server audio endpoint: `GET /api/briefing/audio/{article_id}/{summary_type}` in `jane_web/main.py`
- BriefingViewModel already calls `BriefingAudioCache.prefetchAll()` on WiFi after articles load — verify this works

## Notes
- Prefetch should be non-blocking — user can browse articles while audio downloads
- Show a small "Audio ready" badge on articles once their audio is cached
- If prefetch fails for some articles, fall back to streaming for those
- Cache size: ~10-20MB per day (24 articles × ~400KB each)
- The `BriefingAudioCache` utility is already written — this job is about testing and refining it
