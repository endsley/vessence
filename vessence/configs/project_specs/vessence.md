# Project Vessence — Spec

## Vision

**Vessel + Essence.** A container that holds someone's essence.

Vessence is not a chatbot wrapper. It is a platform for building a **digital clone and living memory of a person**. Over time, ChromaDB accumulates how a person thinks — their relationships, preferences, values, stories, opinions, and voice. The longer someone uses Vessence, the more of themselves lives inside it.

**The north star:** If a person dies, their loved ones have a digital memory they can interact with. A vessel that holds the essence of who that person was.

**Product arc:**
- Year 1: Personal assistant that knows you
- Year 3: Digital companion that thinks like you
- Year 10: A vessel loved ones can talk to after someone is gone

ChromaDB is the soul of the product. The chat interface, the vault, the Discord/Telegram bot — these are all just ways to interact with the memory. Without the memory, it's just another chatbot. With it, it becomes irreplaceable.

---

**Goal:** Package Project Ambient as a public, self-hostable personal AI system that anyone can run with minimal technical knowledge.

**Tagline:** Your own living memory. Private, growing, yours forever.

---

## Core Principles

- **One API key by default** — everything runs on Google Gemini (free tier covers most personal use)
- **One command to start** — `docker compose up` spins up the full core stack
- **No personal data** — ships with zero vault files, zero memories, zero identity essays
- **Full capability parity** — users get the complete system, nothing stripped except the developer's personal data
- **Blank-slate identity** — guided onboarding interview generates personalized identity essays on first run
- **Personal data separation** — all user-specific data lives in `user_profile.md`, never hardcoded in agent config files

---

## What's Included vs Excluded

### Included in Vessence
- Jane (Gemini CLI brain, swappable to Claude Code)
- Amber (Google ADK / gemini-2.5-flash)
- ChromaDB vector memory (full architecture: permanent, long-term, forgettable, librarian)
- Vault file system + vault web UI (Google Drive-style browser)
- Jane web UI (chat directly with Jane via browser)
- Fixed domain via Cloudflare named tunnel (permanent URL, no random strings)
- Nightly cron jobs (audit, janitor, memory synthesis, USB backup)
- Discord / Telegram: **removed as default** — optional add-on only

### Advanced Settings (opt-in, not required)
- Ollama local models — offline fallback + local memory synthesis; user configures model choice in settings
- Claude Code as Jane's brain — enter Anthropic API key to swap

### Excluded from Vessence (stay in Project Ambient only)
- Kokoro TTS — too complex to set up, not essential for core experience
- OmniParser computer vision / screen control — too complex, not essential
- Screen dimmer — too hardware-specific, not essential
- The developer's vault files, identity essays, ChromaDB data
- `user_profile.md` (personal — gitignored, each user fills in their own copy)

---

## Architecture

### Jane's Brain — Three Options

During onboarding, the user picks which CLI powers Jane. This is the only decision that affects what API keys are required.

| Option | API Keys Required | Jane's Model | Best For |
|---|---|---|---|
| **Gemini CLI** *(default)* | Google only (already required) | gemini-2.5-flash | Free, zero extra setup |
| **Claude Code** | Google + Anthropic | claude-sonnet-4-5 | Best coding & technical reasoning |
| **OpenAI CLI** | Google + OpenAI | gpt-4o | Users already paying for ChatGPT Plus |

The onboarding UI presents this as a radio button selection. Selecting Gemini shows no new fields. Selecting Claude or OpenAI reveals the corresponding API key field with inline validation.

Amber always runs on Google Gemini regardless of which CLI the user picks for Jane. The memory system, vault, and all background jobs always use Gemini as well.

### Default Stack (1 Google API key — Gemini option)

| Component | Model | Notes |
|---|---|---|
| Jane (CLI brain) | Gemini CLI / gemini-2.5-flash | Primary reasoning, coding, architecture |
| Amber (ADK agent) | gemini-2.5-flash | Vault tools, always-on companion |
| Memory librarian | gemini-2.5-flash-lite | Background memory synthesis, cheap |
| Memory searcher | gemini-2.5-flash-lite | Per-session context retrieval |
| Local fallback | qwen2.5-coder:14b via Ollama | Tier 2 only — offline mode |

### Advanced Stack (2 API keys — Claude or OpenAI option)
- Jane swapped to Claude Sonnet or GPT-4o by entering the corresponding key
- Everything else (Amber, memory, vault) stays on Gemini
- No reinstall needed — change brain anytime in Settings

---

## Feature Tiers

### Core (Docker, works on Windows / Mac / Linux)
- Jane + Amber chat (web UI + optional Discord/Telegram)
- ChromaDB memory system
- Vault file browser (web UI)
- Cloudflare tunnel (automatic public URL)
- Nightly cron jobs
- **Install:** `docker compose up`
- **Requires:** Docker, 1 Google API key

### Advanced Settings (opt-in via settings page, no reinstall needed)
- **Ollama** — enter Ollama server URL + model name; enables offline fallback and local memory synthesis (~10GB disk for default model)
- **Jane's brain** — change anytime: Gemini CLI (free), Claude Code (Anthropic key), or OpenAI CLI (OpenAI key)

---

## Hardware Requirements

Vessence outsources all LLM inference to Google Gemini (and optionally Anthropic). The local machine only runs: FastAPI, ChromaDB with a small embedding model, and Docker (on Windows/Mac).

### Minimum (outsourced LLMs — default)

| Platform | RAM | CPU | Storage | Network |
|---|---|---|---|---|
| Linux | 2 GB | Dual-core 2 GHz | 5 GB | 10 Mbps+ |
| Windows / Mac | 8 GB | Quad-core | 20 GB | 10 Mbps+ |

Windows/Mac require more RAM and storage because Docker Desktop runs a Linux VM overhead (~4 GB RAM, ~10 GB disk).

### Recommended (all platforms)

| RAM | CPU | Storage | Network |
|---|---|---|---|
| 8 GB | Quad-core 2.5 GHz+ | 50 GB | 25 Mbps+ |

50 GB covers: Docker images (~5 GB), ChromaDB growth over years, vault files (documents, photos, audio).

### GPU
**No GPU required** when running in outsourced-LLM mode. The only local ML workload is ChromaDB's embedding model (`all-MiniLM-L6-v2`, ~22 MB), which runs comfortably on CPU.

If the user enables Ollama (advanced setting), a GPU is recommended for inference speed but not required.

### Bottleneck
Network latency, not compute. Every Amber/Jane response roundtrips to Gemini API. A fast CPU does nothing if the internet connection is slow.

### Raspberry Pi
A Raspberry Pi 4 (4 GB model) running Raspberry Pi OS (Linux) meets the minimum spec and can run Vessence in fully outsourced mode. Not officially supported but viable for technically confident users.

---

## Delivery & Install

### Decision: Level 1 — Docker Desktop + single compose file
Chosen for v1. Targets developer-adjacent users comfortable with installing an app and dragging a file. A native installer (Level 2) is a post-v1 milestone.

### What ships on Docker Hub
Vessence publishes pre-built images to Docker Hub so users never need the source repo:
- `vessence/amber` — Amber ADK agent
- `vessence/vault` — Vault web UI (FastAPI)
- `vessence/jane` — Jane bridge
- `vessence/chromadb` — ChromaDB (or use official `chromadb/chroma` image)

The GitHub repo remains public for contributors and power users who want to self-build.

### User Install Flow (v1)

**Step 1 — Install Docker Desktop** *(one-time)*
- Download from [docker.com/get-started](https://docker.com/get-started)
- Run the installer (Windows: `.exe` / Mac: `.dmg` / Linux: one-liner on the download page)
- Launch Docker Desktop and wait for "Running" status

**Step 2 — Download one file**
- Go to `github.com/endsley/vessence` (or `vessence.ai` when live)
- Download `docker-compose.yml` — one click, ~20 lines

**Step 3 — Start Vessence via Docker Desktop GUI**
- Open Docker Desktop
- Drag `docker-compose.yml` into the window (or File → Open Compose File)
- Click **Start** — Docker pulls all images and starts all services
- Browser opens automatically to `http://localhost:3000/setup`

*Terminal alternative for power users:* navigate to the folder and run `docker compose up`

### What happens when Docker starts (detailed breakdown)

When the user clicks Start in Docker Desktop (or runs `docker compose up`), the following happens automatically:

**Phase 1 — Image Pull** *(first run only, ~3–5 min on 25 Mbps)*

Docker downloads all pre-built images from Docker Hub. No compilation, no pip install — the images are already built:

| Image | Size (approx) | What it is |
|---|---|---|
| `vessence/chromadb` | ~800 MB | ChromaDB + sentence-transformers embedding model |
| `vessence/amber` | ~600 MB | Google ADK + Amber agent code + all Python deps |
| `vessence/vault` | ~400 MB | FastAPI vault web UI + all Python deps |
| `vessence/jane` | ~200 MB | Gemini CLI bridge |
| **Total** | ~2 GB | Subsequent starts: 0 downloads, instant |

Subsequent starts skip this phase entirely — images are cached locally.

**Phase 2 — Container Startup** *(~10–20 seconds)*

Docker starts all containers in dependency order:
1. `chromadb` starts first — listens on `localhost:8001`
2. `amber` starts — connects to ChromaDB, loads embedding model into RAM, listens on `localhost:8000`
3. `vault` starts — connects to ChromaDB and Amber, listens on `localhost:8080`
4. `jane` starts — initializes Gemini CLI bridge, listens on `localhost:8090`
5. `cloudflared` starts (if configured) — establishes Cloudflare tunnel for external access

**Phase 3 — First-Run Detection** *(instant)*

On startup, the `vault` container checks whether `$AMBIENT_HOME/.env` exists. If it does not, the browser is opened to `http://localhost:3000/setup` (onboarding). If it does exist, normal operation begins immediately.

**Phase 4 — Onboarding** *(~3–5 minutes, user-driven)*

User fills in the setup form (see Onboarding Web UI section below). On submit:
1. API keys are validated with live test calls
2. `.env` is written to `$AMBIENT_HOME/`
3. Guided identity interview runs (generates `user_profile.md`)
4. ChromaDB is initialized with blank collections
5. All services are signaled to reload with the new configuration
6. Browser redirects to `http://localhost:3000` (main vault UI)

### Day-to-day
- Vessence starts automatically whenever Docker Desktop is running
- To stop: click Stop in Docker Desktop (or `docker compose down`)
- To update: click Pull in Docker Desktop (or `docker compose pull && docker compose up`)

---

## Onboarding Web UI (First Run)

A locally-hosted setup page (FastAPI) that launches automatically on first run.

---

### Step 0 — Welcome Screen

The first screen is not a form. It is an introduction.

**Purpose:** Let the user understand what Vessence is before they're asked to configure anything. Should feel inspiring and personal — not like a README or a terms-of-service screen.

**What to communicate:**

> **What is Vessence?**
> Vessence is a living memory and personal companion that runs entirely on your machine.
> Unlike cloud assistants that forget you between sessions, Vessence grows with you — the more you use it, the more it knows you.
>
> It's not a chatbot. It's a vessel that holds your essence: how you think, who you love, what you're working on, what matters to you.

> **Meet Jane**
> Jane is your technical brain. She's the one you bring hard problems to — code, research, architecture, writing. She thinks like a knowledgeable friend, not a corporate assistant. Direct, capable, and on your side.

> **Meet Amber**
> Amber is your always-on companion. She manages your vault, answers voice messages, keeps your memories, and is simply there. Warm, present, and growing more herself the longer she knows you.

> **Your memory is yours**
> Everything runs locally. Your conversations, your files, your memories — none of it leaves your machine unless you choose to share it. Your data is not used to train anything. It belongs to you.

**UI notes:**
- Full-bleed dark screen, no form fields
- Amber and Jane introduced with small avatar portraits
- One CTA at the bottom: **"Let's set it up →"**
- Estimated setup time shown: "~3 minutes"

---

### Step 0.5 — System Requirements Check

Immediately after the welcome screen, before showing any configuration fields, run an automatic system check. This is a non-blocking diagnostic — the user cannot fail it and does not fill in any fields. It simply shows them what Vessence detected about their machine.

**Purpose:** Build trust (Vessence is checking things for you), surface potential problems before they become install failures, and set correct expectations.

**Checks to run (client-side + container-reported):**

| Check | How | Pass condition |
|---|---|---|
| Available RAM | Docker container reads `/proc/meminfo` | ≥ 2 GB (Linux) / ≥ 6 GB (Win/Mac) |
| Available disk | `shutil.disk_usage($AMBIENT_HOME)` | ≥ 5 GB free |
| Internet connectivity | Lightweight ping to `generativelanguage.googleapis.com` | HTTP 200 or 400 (key-gated) |
| Google AI Studio reachable | Same ping | Reachable |
| Docker version | `docker version` output captured by bridge | Docker ≥ 24 |
| ChromaDB running | Internal health check | `/api/v1/heartbeat` returns 200 |

**UI notes:**
- Each check shows a spinner → green checkmark (pass) or yellow warning (borderline) or red X (fail)
- All checks run in parallel — whole page resolves in < 2 seconds
- Warnings are informational, not blockers. Red failures show a one-line fix hint.
- Example warning: *"Only 4.2 GB disk free — you can continue but your vault will fill up faster than expected."*
- Example failure: *"Can't reach Google's API servers — check your internet connection before continuing."*
- One CTA at bottom: **"Continue to setup →"** (enabled even with warnings, disabled only on network failure)

---

### Field Specifications

Each field must include:
- A plain-English explanation of **what it does** (one sentence)
- **Where to get it** — direct link, exact steps, what to click
- **What happens if you skip it** (for optional fields)
- An inline **validation indicator** (✅ valid / ❌ invalid) on paste/blur

---

**Field: Google API Key** *(required)*

> What it does: Powers both Amber and Jane — all conversations, memory synthesis, and file understanding run on Gemini using this key.
>
> Free tier is generous enough for personal use (covers millions of tokens/month).
>
> How to get it:
> 1. Go to [aistudio.google.com](https://aistudio.google.com)
> 2. Sign in with your Google account
> 3. Click **"Get API key"** in the top left
> 4. Click **"Create API key"** → copy it here
>
> Looks like: `AIzaSy...` (39 characters)

---

**Field: Your Name** *(required)*

> What it does: Amber and Jane will use this to address you in conversation and build your personal memory around your identity.
>
> Just your first name is fine. You can change it later.

---

**Field: Cloudflare Domain** *(optional)*

> What it does: Gives you a permanent public URL for your vault and chat interface (e.g. `amber.yourdomain.com`). Without this, Vessence still works but your URL changes every restart.
>
> You need: a domain you own that is managed by Cloudflare DNS.
>
> How to set it up:
> 1. Go to [dash.cloudflare.com](https://dash.cloudflare.com)
> 2. Add your domain (or transfer it to Cloudflare)
> 3. In the left sidebar: **Zero Trust → Networks → Tunnels → Create tunnel**
> 4. Choose "Cloudflared" → name it "vessence" → copy the tunnel token
>
> **Skip this** if you don't own a domain — Vessence will use a free `trycloudflare.com` URL instead. You can set this up later in Settings.

---

**Field: Cloudflare Tunnel Token** *(required if domain is set)*

> What it does: Authenticates your Cloudflare tunnel so your vault is securely exposed at your domain without opening firewall ports.
>
> Where to find it: In the Cloudflare Zero Trust dashboard, when you create a tunnel (step 4 above), the token appears in the install command after `--token`. It looks like `eyJh...` (a long JWT string).

---

**Jane's Brain** *(radio selection — shown in required section, not collapsed)*

> What it does: Chooses which AI CLI powers Jane's reasoning, coding, and research. Pick the one that matches the API keys you have.

Three choices presented as radio buttons with brief descriptions:

| Choice | Description shown in UI | Extra field shown |
|---|---|---|
| ◉ **Gemini** *(selected by default)* | Free — already covered by your Google API key above. No extra setup. | None |
| ○ **Claude Code** | Best coding and technical reasoning. Requires an Anthropic API key (~$5–20/month depending on usage). | Anthropic API Key |
| ○ **OpenAI** | Familiar if you already use ChatGPT. Requires an OpenAI API key. | OpenAI API Key |

**Field: Anthropic API Key** *(shown only if Claude Code is selected)*

> What it does: Powers Jane using Claude Sonnet — Anthropic's best model for coding and technical work.
>
> How to get it:
> 1. Go to [console.anthropic.com](https://console.anthropic.com)
> 2. Sign in or create an account
> 3. Go to **API Keys → Create Key**
> 4. Copy the key here
>
> Looks like: `sk-ant-...`
>
> Note: Anthropic offers pay-as-you-go pricing. Personal use typically costs $5–20/month.

**Field: OpenAI API Key** *(shown only if OpenAI is selected)*

> What it does: Powers Jane using GPT-4o — a good choice if you already have an OpenAI account.
>
> How to get it:
> 1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
> 2. Click **Create new secret key**
> 3. Copy the key here
>
> Looks like: `sk-proj-...`

---

**Advanced Section** *(collapsed by default, "Configure later in Settings")*

Each advanced field follows the same pattern — expanded explanation + exact steps:

| Field | What it does | Where to get it |
|---|---|---|
| Ollama Server URL | Enables offline fallback + local memory synthesis without sending data to Google | Install Ollama from [ollama.com](https://ollama.com), then enter `http://localhost:11434` |
| Discord Bot Token | Sends Amber's responses to a Discord channel on your phone | [discord.com/developers](https://discord.com/developers) → New Application → Bot → Reset Token |
| Discord Channel ID | The specific channel where Amber posts | In Discord: right-click channel → Copy Channel ID (requires Developer Mode in settings) |

---

### UI Design Requirements

- **Progress indicator** at top: Step 1 of 3 (Required → Optional → Advanced)
- **"Test" button** next to API key fields — makes a lightweight API call to confirm the key works before saving
- **Show/hide toggle** on all secret fields (eye icon)
- **Inline help tooltips** (?) on every label that expand to the full explanation on click/hover
- **No field is left unexplained** — if a user has to open a browser tab to figure out what a field means, the UI has failed
- **Error messages are actionable** — not "Invalid API key" but "This doesn't look like a Google API key (should start with AIzaSy and be 39 characters). Get one at aistudio.google.com."

---

After submission:
1. Validates all keys with live API test calls before writing anything
2. Writes `.env` into `$AMBIENT_HOME`
3. Runs guided identity interview (generates personalized identity essays)
4. Initializes ChromaDB with blank slate
5. Starts all Docker services
6. Shows success screen with the vault URL, chat URL, and a "What to do next" checklist
7. Automatically opens **two browser tabs** — one for Vault/Amber, one for Jane

---

### Step 4 — Success Screen + First Launch

After all services are confirmed running, the onboarding page shows a success screen and opens two tabs automatically via JavaScript (`window.open()`).

**Tab 1 — Vault / Amber** (`vault.localhost` or `vault.yourdomain.com`)

Opens to a first-time welcome overlay (dismissed with one click, never shown again):

> **This is your Vault — powered by Amber**
>
> Amber is your always-on companion. She lives here.
>
> Drop files into the Vault and she'll remember them. Ask her questions and she'll search your memories. Send her a voice message and she'll respond. The longer you use Vessence, the more Amber knows you.
>
> **Try saying:** *"Hey Amber, I just moved to Austin, Texas."* or *"Save this photo for me."*

**Tab 2 — Jane Chat** (`jane.localhost` or `jane.yourdomain.com`)

Opens to a first-time welcome overlay:

> **This is Jane — your technical brain**
>
> Jane is who you bring hard problems to. Code, research, architecture, writing, analysis — she thinks like a knowledgeable friend, not a corporate assistant. Direct, capable, and on your side.
>
> Jane and Amber share the same memory. Anything you tell Amber, Jane already knows.
>
> **Try asking:** *"What can you help me with?"* or *"Review this code for me."*

**UI notes for both overlays:**
- Dark modal with avatar portrait (Amber or Jane)
- Shown only once — a flag written to localStorage after dismissal
- Single CTA: **"Let's go →"**
- No forms, no fields — purely informational

---

## Chat Interface

The web UI is the primary interface — no Discord or Telegram needed.

- `vault.localhost` / `jane.localhost` — local access (always works, no account needed)
- `vault.yourdomain.com` / `jane.yourdomain.com` — external access via Cloudflare tunnel

Discord / Telegram are optional add-ons for users who want mobile push notifications, configurable in settings after setup. They are no longer required or part of the default onboarding.

---

### Accessing Vessence from Outside Your Home (Cloudflare)

By default, Vessence is only accessible on your local network (`vault.localhost`). To reach it from your phone, a coffee shop, or anywhere outside your home, you need a Cloudflare tunnel.

**Two options:**

| Option | Cost | What you need | What you get |
|---|---|---|---|
| **Cloudflare Free** | $0 | A domain (~$10/yr from any registrar) | Permanent public URL, HTTPS, DDoS protection |
| **Quick Tunnel** | $0 | Nothing | Temporary URL (changes every restart), no custom domain |

**Cloudflare Free is strongly recommended.** The only cost is a domain name (~$10/year from Namecheap, Google Domains, etc.). Once the domain is pointed to Cloudflare's nameservers (free), the tunnel itself is completely free — no monthly fee, no bandwidth limits for personal use.

**What the onboarding explains to users:**

> **Want to access Vessence from your phone or outside your home?**
>
> You'll need a Cloudflare tunnel. It's free — the only cost is a domain name (~$10/year).
>
> **Option A — Free temporary URL (no setup)**
> Skip this section. Vessence will generate a temporary `trycloudflare.com` URL you can use right now. It changes every time you restart Vessence.
>
> **Option B — Permanent URL with your own domain (recommended)**
> 1. Buy any domain (~$10/yr at Namecheap, Porkbun, etc.)
> 2. Go to cloudflare.com → add your domain → point nameservers to Cloudflare (free)
> 3. In Cloudflare Zero Trust → Tunnels → Create tunnel → copy the token
> 4. Paste the token here → your vault will be at `vault.yourdomain.com` permanently
>
> Cloudflare's free plan covers all personal use — no bandwidth limits, no monthly fee.

---

## User Profile Pattern

All personal data about the instance owner lives in **one file**: `$AMBIENT_HOME/user_profile.md`.

### What goes in user_profile.md
- Name and preferred address
- Family members
- Profession and background
- Preferences (colors, hobbies, rituals)
- Communication rules (tone, titles to avoid, relationship style)
- Relationship to the agents

### What stays in CLAUDE.md / GEMINI.md
Only operational and behavioral instructions — protocols, commands, environment paths, update rules. Zero personal data inline.

### How it works
Both `CLAUDE.md` and `GEMINI.md` list `$AMBIENT_HOME/user_profile.md` as step 1 of their Initialization section. Jane and Amber read it every session — knowing how to address the user, their preferences, and how they want the relationship to feel — without any of that being hardcoded into system prompt files.

### For Vessence users
The repo ships `user_profile.template.md` — a blank form with sections and hints. The onboarding identity interview fills it in and writes it to `$AMBIENT_HOME/user_profile.md`. The file is added to `.gitignore` so personal data is never committed.

```
$AMBIENT_HOME/
  user_profile.md           ← filled in, gitignored (personal, never committed)
  user_profile.template.md  ← blank template, committed to repo
  CLAUDE.md                 ← operational only, safe to commit
  .gemini/GEMINI.md         ← operational only, safe to commit
```

---

## Pre-Release Checklist (Sanitization Audit)

Before first public release, audit and remove all personal data:

- [x] Personal data extracted from `CLAUDE.md` and `GEMINI.md` into `user_profile.md`
- [x] `user_profile.template.md` shipped as blank template in repo
- [x] `user_profile.md` added to `.gitignore`
- [ ] Remove all vault files (`vault/images/`, `vault/documents/`, `vault/audio/`)
- [ ] Remove ChromaDB data (`vector_db/`)
- [ ] Remove identity essays (`vault/documents/*_identity_essay.txt`)
- [ ] Remove all `.env` files (keep `.env.example` with annotated placeholders)
- [ ] Audit all Python files for hardcoded personal values:
  - [ ] `screen_dimmer.py` — Medford MA coordinates (excluded from Vessence anyway)
  - [ ] Any hardcoded personal names
  - [ ] Any hardcoded paths that assume `/home/chieh/`
- [ ] Replace `/home/chieh/` paths with environment variable `$AMBIENT_HOME`
- [ ] Remove `how_to_restore_jane.md` personal restore instructions
- [ ] Scrub git history of any committed secrets

---

## Key Open Questions

1. **Repo name:** `endsley/vessence` or `endsley/project-ambient`?
2. **License:** MIT (fully open) or source-available with attribution?
3. **Hosted option?** Should there be a "Vessence Cloud" where users don't need to self-host at all?
4. **Identity interview:** How deep? Just name + relationship status, or full personality/preference session?
5. **Update mechanism:** How do Vessence users get future improvements? Git pull? Auto-update script?
