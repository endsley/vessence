# Job: Tunnel Connection Pooling — HTTP/2 Multiplexing + Keep-Alive

Status: complete
Completed: 2026-03-24 00:22 UTC
Priority: 2
Model: sonnet
Created: 2026-03-23
Related: Job #02 (Switch Tunnel to HTTP/2)

## Objective
Reduce TLS handshake overhead by enabling HTTP/2 multiplexing and keep-alive connections through the Cloudflare tunnel. Android especially benefits from frequent small polling requests.

## Design
- Ensure tunnel runs with `--protocol http2` (Job #02)
- Set uvicorn to support HTTP/1.1 keep-alive (already default)
- Android OkHttpClient: verify connection pool settings (max idle connections, keep-alive duration)
- Web: verify fetch API uses keep-alive (browser default)
- Consider increasing cloudflared `--proxy-keepalive-timeout` if available

## Files Involved
- `~/.config/systemd/user/vault-tunnel.service` — protocol flag
- `android/.../data/api/ApiClient.kt` — OkHttp connection pool config
- Cloudflare tunnel config — keepalive settings

## Notes
- This pairs with Job #02 (HTTP/2 switch) — do them together
- HTTP/2 multiplexing means multiple requests share one TCP connection
- Android's announcement polling (~every 5s) currently opens a new connection each time
- With pooling, all requests reuse the same connection = less latency per request
