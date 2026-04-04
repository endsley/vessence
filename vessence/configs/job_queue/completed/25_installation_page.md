# Job: Add Installation Instructions Page to vessences.com

Status: completed
Priority: 1
Model: opus
Created: 2026-03-24

## Objective
Add a public installation page to the marketing site (vessences.com) with step-by-step setup instructions for Windows, Mac, and Linux. Include a visible link/button from the main landing page.

## What the page should cover

### Prerequisites
- Docker Desktop (Windows/Mac) or Docker Engine + Compose plugin (Linux)
- A Google API key (free tier) — required for Gemini brain
- Optional: Anthropic API key (Claude) or OpenAI API key

### Quick Install (3 steps)
1. Download the installer zip (link to /downloads/vessence-installer-0.0.42.zip)
2. Extract and run install.sh (Linux/Mac) or install.bat (Windows)
3. Open http://localhost:3000 for the onboarding wizard

### Platform-specific instructions

**Windows:**
- Install Docker Desktop (link)
- Enable WSL2 when prompted
- Extract zip, double-click install.bat
- Troubleshooting: "Docker not found" → restart after Docker install

**macOS:**
- Install Docker Desktop for Mac (link)
- Extract zip, open Terminal, run `chmod +x install.sh && ./install.sh`
- Note: Apple Silicon (M1/M2/M3) is supported

**Linux:**
- `curl -fsSL https://get.docker.com | sh`
- `sudo apt install docker-compose-plugin`
- Extract zip, run `./install.sh`

### What happens during install
- Docker images load (~210 MB)
- ChromaDB pulls from Docker Hub (~350 MB)
- Your chosen brain CLI installs on first boot (~200-400 MB)
- Onboarding wizard guides you through API key setup and preferences

### After install
- Jane chat: http://localhost (via Traefik) or http://localhost:8081
- Settings: http://localhost:3000
- Your data stays 100% local — nothing sent to Vessence servers

## Implementation
1. Create `marketing_site/install.html` — the installation page
2. Add a prominent "Install" or "Get Started" button/link on the landing page (`marketing_site/index.html`)
3. Style to match the existing marketing site theme
4. Include download buttons that link to `/downloads/vessence-installer-0.0.42.zip`
5. Add platform toggle tabs (Windows / Mac / Linux)

## Verification
- https://vessences.com/install.html loads (or /install route)
- Landing page has visible link to install page
- Download link works
- Instructions are accurate and complete
- Page looks good on mobile

## Files Involved
- `marketing_site/install.html` (new)
- `marketing_site/index.html` (add install link)
- `marketing_site/nginx/default.conf` (may need route if using clean URLs)
