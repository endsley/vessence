# Job: Rebuild Docker Package v0.0.43 with All Session Changes

Status: completed
Priority: 1
Model: opus
Created: 2026-03-24

## Objective
Rebuild Docker images incorporating all changes from this session: standing brain, brain thoughts streaming, essence mode, instant commands, outage fixes, guide page, work log policy, TTS improvements, and security hardening.

## Steps
1. Bump version to 0.0.43 in build.gradle.kts and CHANGELOG
2. Build Jane image: `docker build -t vessence/jane:latest -f docker/jane/Dockerfile .`
3. Build Onboarding image: `docker build -t vessence/onboarding:latest -f docker/onboarding/Dockerfile .`
4. Security scan both images (no .db, no .env, no /home/chieh paths)
5. Export: `docker save vessence/jane:latest vessence/onboarding:latest | gzip > dist/vessence-docker-0.0.43.tar.gz`
6. Verify size is under 300 MB
7. Build installer zip with updated install scripts (docker pull chromadb)
8. Copy to marketing_site/downloads/
9. Update download links in main.py
10. Rebuild Android APK v0.0.43 if needed

## Verification
- Download package under 300 MB
- All new features work in Docker (standing brain, instant commands, guide page)
- No personal data in images
- Download links work on website

## Files Involved
- docker/jane/Dockerfile
- docker/onboarding/Dockerfile
- docker-compose.yml
- jane_web/main.py (download links)
- configs/CHANGELOG.md
- dist/ (output)
