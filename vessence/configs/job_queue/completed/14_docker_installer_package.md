# Job: Build Cross-Platform Docker Installer Package

Status: complete
Completed: 2026-03-24 14:15 UTC
Notes: Built vessence-installer-0.0.41.zip (1.3 GB) containing docker-compose.yml, .env.example, traefik.yml, Docker images tar.gz, install.sh (Linux/Mac), install.bat (Windows), README.md. Copied to marketing_site/downloads/. Added download link to PUBLIC_RELEASE_DOWNLOADS. Needs jane-web restart to activate download link.
Priority: 2
Model: opus
Created: 2026-03-24

## Objective
Create a downloadable installer package that bundles Docker images + docker-compose.yml + install scripts for Windows, Mac, and Linux. Users download one zip, extract, and run a script to get Vessence running.

## Context
- Docker images are built and exported to `dist/vessence-docker-0.0.41.tar.gz` (1.3 GB)
- `docker-compose.yml` exists at repo root
- `.env.example` exists
- `traefik/traefik.yml` is needed for the reverse proxy
- Currently only the raw tar.gz is available — no orchestration files or install instructions

## Package Structure
```
vessence-0.0.41/
├── docker-compose.yml
├── .env.example
├── traefik/
│   └── traefik.yml
├── images/
│   └── vessence-images.tar.gz
├── install.bat          (Windows)
├── install.sh           (Linux/Mac)
├── INSTALL-windows.md
├── INSTALL-mac.md
├── INSTALL-linux.md
└── README.md
```

## Steps
1. Create the package directory structure
2. Copy docker-compose.yml, .env.example, traefik/traefik.yml
3. Write `install.bat` for Windows:
   - Check Docker Desktop is installed
   - Load images from tar.gz
   - Copy .env.example to .env
   - Run `docker compose up -d`
   - Open browser to http://localhost:3000
4. Write `install.sh` for Linux/Mac:
   - Check docker and docker compose are installed
   - Same flow as Windows script
   - Make executable
5. Write INSTALL docs for each platform (prerequisites, troubleshooting)
6. Package into `dist/vessence-installer-0.0.41.zip`
7. Add to website download links

## Verification
- Zip file contains all required files
- `install.sh` runs on Linux without errors (test on this machine)
- Download link works on website
- README explains the one-click install process

## Files Involved
- `dist/` — output
- `docker-compose.yml` — copy into package
- `.env.example` — copy into package
- `traefik/traefik.yml` — copy into package
- `jane_web/main.py` — add download link for installer zip

## Notes
- The tar.gz is 1.3 GB — the zip will be similar size
- Windows users need Docker Desktop with WSL2
- Mac users need Docker Desktop
- Linux users need docker + docker compose plugin
- The onboarding wizard (port 3000) handles .env setup — install scripts just need to get containers running
