# Job: Rebuild Slim Docker Package and Update Downloads

Status: complete
Completed: 2026-03-24 19:55 UTC
Notes: Jane image 2.01 GB → 770 MB (no Node.js/CLIs, trimmed pip). Onboarding 265 MB → 139 MB (Alpine). Export: 210 MB compressed (was 1.3 GB). Amber removed. ChromaDB pulled from Docker Hub at install. 84% size reduction.
Priority: 1
Model: opus
Created: 2026-03-24

## Objective
Execute the Docker slim-down (job #18 changes) and rebuild/export the package for user download. Target: ~250 MB compressed download (down from 1.3 GB).

## Pre-conditions
- Job #18 Dockerfile changes already made (pip trimming, Alpine onboarding)
- .dockerignore already blocks APK and marketing files
- Amber container already removed from scope

## Steps
1. Remove amber service from `docker-compose.yml`
2. Change chromadb from `build:` to `image: chromadb/chroma:1.0.10`
3. Build Jane image: `docker build -t vessence/jane:latest -f docker/jane/Dockerfile .`
   - Verify pip trimming worked (no sympy, kubernetes, pygments, pillow, opentelemetry, pip)
   - Verify no APK in image
   - Verify no .db files in image
4. Build Onboarding image: `docker build -t vessence/onboarding:latest -f docker/onboarding/Dockerfile .`
   - Verify Alpine base (not Debian)
   - Verify pip removed
5. Check image sizes:
   - Jane should be ~380-420 MB
   - Onboarding should be ~100 MB
6. Security scan: `docker run --rm <image> find /app -name "*.db" -o -name ".env"`
7. Export: `docker save vessence/jane:latest vessence/onboarding:latest | gzip > dist/vessence-docker-0.0.42.tar.gz`
8. Build installer zip with docker-compose.yml, .env.example, traefik.yml, install scripts
9. Update `install.sh` / `install.bat` to include `docker pull chromadb/chroma:1.0.10`
10. Copy to marketing_site/downloads/ and update download links in main.py
11. Bump version to 0.0.42

## Verification
- `dist/vessence-docker-0.0.42.tar.gz` is under 300 MB
- `dist/vessence-installer-0.0.42.zip` is under 350 MB
- `docker compose up` works (Jane + Onboarding + ChromaDB pulled)
- Jane health check passes
- No personal data in any image
- Download links work on website

## Files Involved
- `docker-compose.yml`
- `docker/jane/Dockerfile`
- `docker/onboarding/Dockerfile`
- `install.sh` / `install.bat`
- `jane_web/main.py` (version + download links)
- `configs/CHANGELOG.md`
- `dist/` (output)
- `marketing_site/downloads/`
