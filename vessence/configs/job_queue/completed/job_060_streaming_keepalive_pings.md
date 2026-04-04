# Job #60: Streaming Keepalive Pings to Prevent Timeout

Priority: 1
Status: completed
Created: 2026-03-31

## Description
Claude Opus can think for extended periods without producing output, causing "Brain claude-opus-4-6 response timeout" errors on the Android app. Implement keepalive pings in the streaming path so clients stay connected during long computations.

### Problem
The timeout chain has mismatched limits:
- Android read timeout: 120s
- Standing brain chunk read: 300s
- Brain adapter: 600s
- FastAPI stream: 1800s

When Claude thinks silently for >120s, the Android client disconnects. When >300s, the standing brain kills the process.

### Solution: Keepalive Pings
1. **`standing_brain.py`**: In `_read_from_brain()`, replace the single 300s `wait_for` with a loop that checks every ~30s. If no output yet, send a keepalive SSE comment (`:\n\n`) downstream to keep the stream alive.
2. **`jane_proxy.py`**: In `stream_message()`, forward keepalive comments to the SSE response so the HTTP connection stays alive.
3. **Android `ApiClient.kt`**: No change needed — keepalives arriving every 30s will naturally prevent the 120s read timeout.

### Key Files
- `jane/standing_brain.py` — chunk read loop (~line 696-724)
- `jane_web/jane_proxy.py` — SSE stream generation
- `jane/brain_adapters.py` — execution profile timeouts

### Acceptance Criteria
- No more "response timeout" errors during long Claude Opus reasoning
- Keepalive pings (`:\n\n`) sent every 30s during silent computation
- Actual failures (process crash, real timeout) still detected within 60s
- Android app stays connected during 5+ minute reasoning tasks
