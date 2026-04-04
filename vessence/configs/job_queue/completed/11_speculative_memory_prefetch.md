# Job: Speculative Memory Prefetch — Load Memory While User Is Idle

Status: complete
Completed: 2026-03-24 00:31 UTC
Notes: Prefetch cache in jane_proxy.py (60s TTL). POST /api/jane/prefetch-memory endpoint. Web fires prefetch after 2s idle on page load. Android fires in ChatViewModel init. Prefetch result used as memory_summary_fallback.
Priority: 2
Model: sonnet
Created: 2026-03-23

## Objective
Pre-fetch the user's most recent memory context while they're on the page but haven't typed yet. When they send a message, memory is already loaded.

## Design
- Web: after 2 seconds of page idle (no typing), fire a background fetch to `/api/jane/prefetch-memory`
- Server: new lightweight endpoint that queries ChromaDB with a generic "recent context" query and caches the result for 60 seconds
- When the actual message arrives, context_builder checks the prefetch cache first before querying ChromaDB
- If cache miss or stale, falls back to normal query (no degradation)

## Files Involved
- `jane_web/main.py` — new `/api/jane/prefetch-memory` endpoint
- `jane/context_builder.py` — check prefetch cache before ChromaDB query
- `vault_web/templates/jane.html` — fire prefetch on idle
- `android/.../ui/chat/ChatViewModel.kt` — fire prefetch on screen open

## Notes
- Prefetch query should be broad: "What does the user care about? Recent topics and context."
- Cache should be per-user, 60s TTL
- Don't prefetch on every keystroke — only on page idle
- If user types quickly and sends before prefetch completes, ignore the prefetch
