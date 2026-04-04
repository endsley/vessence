# Job: Zero-Downtime Deployment — Reverse Proxy with Health Check

Status: complete
Priority: 3
Created: 2026-03-22

## Objective
Enable zero-downtime server restarts. When deploying code changes, start a new server instance, health-check it, then swap traffic — no dropped requests.

## Design (Option 3: Reverse Proxy)
1. Run nginx or caddy as the front-facing proxy (Cloudflare tunnel points to proxy)
2. Proxy forwards to uvicorn on port 8081
3. On deploy: start new uvicorn on port 8082, health-check `/health`, swap upstream, stop old

## Deploy Script
```bash
#!/bin/bash
# 1. Start new server on alternate port
NEW_PORT=8082
uvicorn main:app --port $NEW_PORT &
# 2. Wait for health
until curl -sf http://127.0.0.1:$NEW_PORT/health; do sleep 1; done
# 3. Swap nginx upstream
sed -i "s/127.0.0.1:8081/127.0.0.1:$NEW_PORT/" /etc/nginx/conf.d/jane.conf
nginx -s reload
# 4. Stop old server
kill $(pgrep -f "uvicorn.*8081")
```

## Files Involved
- New: nginx config for Jane web proxy
- New: `deploy.sh` script
- Update: Cloudflare tunnel to point to nginx instead of uvicorn directly
- Update: `jane-web.service` to work with the deploy script
