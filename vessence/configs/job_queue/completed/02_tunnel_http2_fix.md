# Job: Switch Cloudflare Tunnel to HTTP/2 — Prevent Stream Resets

Status: complete
Completed: 2026-03-24 00:15 UTC
Priority: 1
Model: sonnet
Created: 2026-03-23

## Objective
Switch the Cloudflare tunnel from QUIC to HTTP/2 protocol to prevent stream resets on long-lived SSE connections. QUIC aggressively drops idle streams (~100s), causing "stream was reset" errors on Android.

## Fix
Add `--protocol http2` to the cloudflared tunnel command in the systemd service file.

## Steps
1. Read `/home/chieh/.config/systemd/user/vault-tunnel.service`
2. Add `--protocol http2` to the `ExecStart` cloudflared command
3. `systemctl --user daemon-reload`
4. `systemctl --user restart vault-tunnel.service`
5. Verify tunnel reconnects: `tail -20 /home/chieh/ambient/vessence-data/logs/vault_tunnel.log`
6. Test from Android — send a message, verify no stream reset errors
7. Monitor tunnel logs for 10 minutes to confirm no more "stream canceled by remote" errors

## Rollback
Remove `--protocol http2` and restart if HTTP/2 causes issues.

## Files Involved
- `/home/chieh/.config/systemd/user/vault-tunnel.service`

## Notes
- HTTP/2 is more tolerant of long-lived connections than QUIC
- The 15s SSE keepalive (already in place) should be sufficient under HTTP/2
- If HTTP/2 still resets, fallback plan: short-lived SSE with auto-reconnect (60s max per connection)
