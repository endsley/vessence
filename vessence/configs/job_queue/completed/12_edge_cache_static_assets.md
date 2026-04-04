# Job: Edge-Cache Static Assets via Cloudflare

Status: complete
Completed: 2026-03-24 00:18 UTC
Priority: 2
Model: sonnet
Created: 2026-03-23

## Objective
Set proper Cache-Control headers on static assets (images, CSS, JS, fonts) so Cloudflare caches them at the edge. Page loads become instant, saving bandwidth for chat streams.

## Design
- Add Cache-Control headers to static file routes in jane_web/main.py
- Static assets (jane face, amber face, CSS, JS): `Cache-Control: public, max-age=86400` (1 day)
- HTML pages: `Cache-Control: no-cache` (always fresh)
- API responses: `Cache-Control: no-store` (never cache)
- Briefing images: `Cache-Control: public, max-age=3600` (1 hour)

## Files Involved
- `jane_web/main.py` — add middleware or per-route headers
- `vault_web/main.py` — same for vault routes

## Notes
- Cloudflare automatically respects Cache-Control headers
- Verify with `curl -I` that headers are set correctly
- No Cloudflare dashboard config needed — just server-side headers
