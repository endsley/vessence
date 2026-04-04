# Job: Life Librarian Performance — Fast Vault Loading on Android

Status: complete
Priority: 2
Created: 2026-03-22

## Objective
Make the Life Librarian (vault file browser) load fast on Android. Currently slow due to network latency through Cloudflare tunnel + loading all thumbnails at once.

## Improvements

### 1. Cache directory listings (5 min TTL)
- Cache `listDirectory()` results in memory for 5 minutes
- Show cached data instantly, refresh in background
- Invalidate cache on upload/delete/move operations
- Files: `VaultViewModel.kt`, `FileRepository.kt`

### 2. Lazy thumbnail loading (max 4 concurrent)
- Limit Coil's concurrent network requests to 4
- Configure in `ApiClient.getAuthenticatedImageLoader()` with custom dispatcher
- Thumbnails outside viewport don't load until scrolled to

### 3. Prefetch root directory on app launch
- In `ChatViewModel.init` or `HomeScreen`, fire `FileRepository.listDirectory("")` in the background
- Cache the result so when user taps Life Librarian, it shows instantly
- Files: `HomeScreen.kt` or `VessencesApp.kt`

### 4. Pagination for large folders
- Server: add `?offset=0&limit=30` params to `/api/files/list/{path}`
- Android: LazyColumn/LazyGrid with `LazyPagingItems` from Paging 3 library
- Load first 30 items, fetch more on scroll
- Files: `jane_web/main.py` (server), `VaultViewModel.kt` (client)

### 5. Local SQLite file index cache
- Store directory structure in local SQLite on the phone
- On load: show from SQLite instantly (0ms), refresh from server in background
- On refresh: diff server response with local cache, update only changed entries
- Store: path, name, type, size, modified_at, thumbnail_url
- Files: new `VaultCache.kt` utility + Room database or raw SQLite

## Implementation Order
1. #1 (cache) + #3 (prefetch) — biggest impact, least code
2. #2 (lazy thumbnails) — Coil config change
3. #5 (SQLite cache) — most work but enables offline browsing
4. #4 (pagination) — server + client changes

## Files Involved
- `android/.../ui/vault/VaultViewModel.kt` — caching, prefetch trigger
- `android/.../data/repository/FileRepository.kt` — in-memory cache
- `android/.../data/api/ApiClient.kt` — Coil concurrent limit
- `android/.../util/VaultCache.kt` — new SQLite cache
- `jane_web/main.py` or `vault_web/main.py` — pagination params
- `android/.../ui/home/HomeScreen.kt` — prefetch on launch
