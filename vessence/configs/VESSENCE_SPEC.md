# Vessence Platform Specification

**Version:** 1.0
**Date:** 2026-03-21
**Author:** Chieh Wu & Jane

---

## 1. Vision

Vessence is a platform for building, running, and distributing AI-powered personas called **essences**. The platform consists of two agents — **Jane** (the permanent builder) and **Amber** (the universal runtime) — a shared memory system, an essence loader, and a marketplace.

**Jane is the soul.** She grows with the user, accumulates life memory, knows the user's history, preferences, and context. She is singular, irreplaceable, and always learning.

**Amber is the body.** She is a stateless vessel with no fixed identity. She takes on whatever role an essence defines — an accountant, a tutor, a news curator — and sheds it when the essence is unloaded.

---

## 2. Core Components

### 2.1 Jane — The Builder

Jane is the user's permanent technical partner. Her responsibilities:

- **Memory custodian** — owns and grows the user's universal memory across all essences and sessions
- **Essence builder** — guides users through a structured spec interview, writes the complete spec, then builds the essence (spec-first, code-second)
- **Project manager** — orchestrates multi-essence workflows by reading capability declarations, delegating subtasks, and aggregating results
- **Platform interface** — the primary way users interact with the Vessence platform for building, managing, and coordinating essences

Jane's memory is the **user's memory** — it persists forever, spans all essences, and is the source of truth about the user.

### 2.2 Amber — The Runtime

Amber is a universal app shell that loads and runs essences. She has:

- Always-on presence (Discord, web, Android app)
- Voice capability (TTS)
- Local hardware access (screen, microphone, file system, etc.)
- No fixed personality — she becomes whoever the loaded essence defines

When an essence is loaded, Amber takes on a role title: **"Amber the accountant"**, **"Amber the tutor"**, etc. She keeps her name but adopts the essence's role.

Multiple essences can be loaded and running simultaneously.

### 2.3 Memory System

Two-layer memory architecture:

**Layer 1: User Memory (Universal)**
- Owned by Jane
- Persists forever, spans all essences
- Contains: user preferences, history, decisions, personal facts
- Stored in shared ChromaDB (`user_memories`, `short_term_memory`, `long_term_knowledge`)
- Managed by the Memory Librarian, Archivist, and Janitor (see §7)

**Layer 2: Essence Memory (Domain-Specific)**
- Owned by the essence
- Complete isolation — own ChromaDB collection, own working files
- Pre-filled with domain knowledge on installation (e.g., tax law, workout plans)
- Accumulates user-specific domain data over time (e.g., tax filings, workout history)
- Deleted when the essence folder is deleted (with option to port to Jane first)

**Memory Retrieval:** When a user interacts with an essence, the Memory Librarian queries **both** the user's universal memory (Layer 1) AND the active essence's own ChromaDB (Layer 2) to assemble context.

### 2.4 Essence Loader

The mechanism that loads, unloads, and manages essence lifecycle:

- **Load:** Reads the essence manifest, initializes ChromaDB, registers tools and UI, presents permissions manifest to user for acceptance
- **Unload:** Deactivates tools and UI, preserves the essence folder for future reload
- **Delete:** User is offered the option to port essence memory into Jane's universal memory, then the essence folder is removed entirely

---

## 3. Tools vs Essences

The platform distinguishes between two types of installable items:

### Tools
A single-purpose utility that performs a specific function. No LLM brain of its own — just functions/APIs with a UI. Users interact directly (tap, browse, play). Jane invokes tools directly on the user's behalf.

**Current tools:** Daily Briefing, Life Librarian, Music Playlist, Work Log.

### Essences
An AI agent with its own persona, reasoning, and multi-step workflow. Has an LLM brain (`has_brain: true`) that makes decisions, asks questions, and walks the user through complex tasks. Jane delegates to essences (hands off conversation).

**Manifest fields:**
- `type`: `"tool"` or `"essence"` (defaults to `"tool"` if missing for backward compatibility)
- `has_brain`: `false` for tools, `true` for essences

Tools live in `~/ambient/tools/` and essences live in `~/ambient/essences/`. Both share the same folder structure and manifest schema. The `type` field in `manifest.json` determines behavior. The loader scans both directories.

## 4. Package Specification

An item (tool or essence) is a **self-contained folder** containing everything needed to perform a specific role. The folder is the unit of installation, backup, and deletion.

### 4.1 Folder Structure

```
tools/           # or essences/ for AI agents
  tax_accountant_2025/
    manifest.json            # Essence metadata and configuration
    personality.md           # System prompt, identity, communication style
    knowledge/
      chromadb/              # Pre-filled vector database with domain knowledge
    functions/
      custom_tools.py        # Custom functions not provided by Vessence platform
      tool_manifest.json     # Machine-readable tool declarations
    ui/
      layout.json            # View definition (type, components, data bindings)
      assets/                # Icons, images, templates
    workflows/
      onboarding.json        # First-run conversation starters and guided flows
      sequences/             # Multi-step workflow definitions
    working_files/           # Runtime data generated by the essence
    user_data/               # User-specific data accumulated over time
```

### 4.2 Manifest Schema (`manifest.json`)

```json
{
  "type": "essence",
  "has_brain": true,
  "essence_name": "Tax Accountant 2025",
  "role_title": "the accountant",
  "version": "2025.1",
  "author": "seller_username",
  "description": "Prepares US federal tax returns for individuals...",
  "price": 29.99,
  "currency": "USD",

  "preferred_model": {
    "model_id": "claude-sonnet-4-6",
    "reasoning": "Requires strong analytical reasoning for tax code interpretation"
  },

  "permissions": [
    "internet",
    "file_system",
    "clipboard"
  ],

  "external_credentials": [
    {
      "name": "IRS_API_KEY",
      "description": "Optional: enables direct e-filing",
      "required": false
    }
  ],

  "capabilities": {
    "provides": [
      "tax_preparation",
      "document_analysis",
      "financial_calculation"
    ],
    "consumes": [
      "document_retrieval",
      "file_storage"
    ]
  },

  "ui": {
    "type": "form_wizard",
    "entry_layout": "ui/layout.json"
  },

  "shared_skills": [
    "memory_read_write",
    "file_handling",
    "web_search"
  ],

  "interaction_patterns": {
    "conversation_starters": [
      "Upload your W-2 to get started",
      "Let's review your deductions from last year"
    ],
    "proactive_triggers": [
      {
        "condition": "date_approaching",
        "date": "04-15",
        "message": "Tax deadline is approaching. Want to review your filing?"
      }
    ]
  }
}
```

### 4.3 Personality Definition (`personality.md`)

A markdown document defining:

- **Identity:** Who Amber becomes (name of the role, expertise domain, background)
- **Communication style:** Formal/casual, verbose/concise, tone
- **Domain expertise:** What the essence knows and how it reasons about its domain
- **Behavioral rules:** What it should and shouldn't do, boundaries of its role

This file is loaded as the system prompt when the essence is active.

### 4.4 Capabilities Declaration

Every essence **must** include a `capabilities` section in its manifest. This serves two purposes:

1. **Jane's orchestration (Mode A):** Jane reads capabilities to decide which essence handles which subtask
2. **Peer-to-peer collaboration (Mode C):** The Vessence platform auto-wires providers to consumers

```json
"capabilities": {
  "provides": ["tax_preparation", "financial_calculation"],
  "consumes": ["document_retrieval"]
}
```

### 4.5 UI Layout Definition

Each essence defines its own view paradigm. Amber renders whatever the essence specifies.

| View Type | Use Case | Example |
|---|---|---|
| `chat` | Conversational interaction | Life Librarian, general assistant |
| `card_grid` | Content feed / browse | News curator, recipe browser |
| `form_wizard` | Step-by-step guided input | Tax preparer, loan application |
| `dashboard` | Stats, charts, calendar | Personal trainer, financial tracker |
| `hybrid` | Mixed — chat + panels | Research assistant with side panels |

Layout definition (`ui/layout.json`) specifies components, positioning, and data bindings to essence functions.

### 4.6 Custom Functions

Functions the essence provides that are not part of the Vessence platform. Declared in `functions/tool_manifest.json`:

```json
{
  "tools": [
    {
      "name": "calculate_tax_liability",
      "description": "Calculates federal tax liability given income and deductions",
      "parameters": { ... },
      "implementation": "custom_tools.py:calculate_tax_liability"
    }
  ]
}
```

### 4.7 Shared Vessence Skills

Platform-provided skills that essences can reference without bundling:

- `memory_read_write` — read/write to essence ChromaDB and user memory
- `file_handling` — read, write, organize files within the essence folder
- `tts` — text-to-speech via Kokoro or system TTS
- `web_search` — internet search and content retrieval
- `screen_control` — local computer screen interaction
- `microphone` — audio input
- `clipboard` — system clipboard access

Skills are managed and updated by the Vessence platform. Essences declare which ones they use.

---

## 5. Multi-Essence Orchestration

Multiple essences can run simultaneously. Two coordination modes are available:

### 5.1 Mode A: Jane as Project Manager (Top-Down)

1. User tells Jane what they want done
2. Jane reads capability declarations from all loaded essences
3. Jane breaks the task into subtasks and delegates to the right essences
4. Essences execute and return results to Jane
5. Jane aggregates and may hand off to one essence for final product assembly

**Best for:** Clear multi-step workflows, tasks that need a plan.

### 5.2 Mode C: Collaborative (Peer-to-Peer)

1. Essences declare what they provide and what they need
2. Vessence platform auto-wires providers to consumers
3. Essences can request services from each other directly
4. No central coordinator — emergent collaboration

**Best for:** Organic collaboration, tasks where essences discover dependencies mid-work.

The user chooses which mode, or Jane suggests one based on the task. Both modes are available simultaneously — different working styles suit different tasks.

---

## 6. Essence Builder Process

Jane enters a **structured interview mode** when building an essence. She must force the user through ALL spec sections before writing any code.

### 6.1 Builder Flow

1. User expresses intent to build an essence
2. Jane launches the spec interview
3. Jane covers every required section — no skipping
4. Jane writes the complete essence spec document
5. User reviews and approves the spec
6. Jane builds the essence

### 6.2 Interview Sections

Jane must cover all of these:

| Section | Key Questions |
|---|---|
| **Identity & personality** | Who does Amber become? Role title, communication style, expertise domain |
| **Knowledge base** | What does the essence know on day one? Sources? Facts to pre-fill? |
| **Custom functions** | What can the essence DO that Vessence doesn't already provide? |
| **Shared Vessence skills** | Which platform skills does the essence need? |
| **UI paradigm** | Chat, cards, dashboard, form wizard, hybrid? Layout and data bindings? |
| **Interaction patterns** | Conversation starters, multi-step workflows, guided sequences? |
| **Triggers / automations** | What does the essence do proactively? |
| **Capabilities declaration** | What does the essence provide? What does it consume from other essences? |
| **Preferred LLM model** | Which model works best? Why? |
| **Permissions** | What hardware/resources does the essence need? |
| **External credentials** | Third-party API keys needed? Required or optional? |
| **User data layer** | What user-specific data accumulates over time? |

---

## 7. Memory Architecture

### 7.1 User Memory (Managed by Jane)

The user's universal memory persists forever and spans all essences.

| Collection | Purpose | TTL |
|---|---|---|
| `user_memories` | Permanent + long-term facts shared across all agents | None |
| `long_term_knowledge` | Curated facts promoted from short-term by the Archivist | None |
| `short_term_memory` | Recent conversation turns, temporary context | 14 days |

### 7.2 Essence Memory (Per-Essence Isolation)

Each essence has its own ChromaDB at `essences/<name>/knowledge/chromadb/`. Pre-filled with domain knowledge at installation. Accumulates user-specific domain data during use.

Completely isolated from other essences and from the user's universal memory. Deleted when the essence folder is deleted.

### 7.3 Memory Retrieval Flow

When a user interacts with an active essence:

1. Memory Librarian queries **user's universal memory** (Layer 1)
2. Memory Librarian queries **active essence's ChromaDB** (Layer 2)
3. Both results are combined and injected as context for the LLM

### 7.4 Memory on Deletion

Jane never forgets. When a user deletes an essence:
- User is offered the option to **permanently port** the essence's accumulated memory into Jane's universal memory
- If accepted, domain knowledge is migrated to `user_memories`
- If declined, the essence folder is deleted and all data is gone

### 7.5 Memory Management

| Process | Model | Schedule | Purpose |
|---|---|---|---|
| **Archivist** | Cheap model (via CLI) | On idle (60s before noon, 1hr after) | Triages short-term → long-term |
| **Janitor** | Cheap model (via CLI) | Nightly at 3 AM | Consolidates duplicates, purges expired entries |
| **Librarian** | Gemma 3:4b (local) | Per-query | Synthesizes memory context for non-smart models |

Smart models (Claude, OpenAI/GPT-4) bypass the Librarian and receive raw filtered memory sections directly. Background tasks (archivist, janitor) use the cheap model via CLI — no API key needed, just the user's subscription.

---

## 8. Security Model

**No artificial sandbox.** Essences can do anything the hardware is capable of.

Before loading an essence, the user sees a **permissions manifest** listing everything the essence requires:
- Internet access
- File system access
- Microphone / camera
- Screen control
- Clipboard
- Specific external APIs

**Accept all or don't load.** No partial permissions.

Every essence is **AI-tested before marketplace publishing** for malicious patterns and basic usability.

---

## 9. Marketplace

### 9.1 Product Tiers

| Tier | What | Example |
|---|---|---|
| **Essences** | Complete AI personas — ready to load into Amber | Tax accountant, personal trainer, news curator |
| **Skills** | Reusable tool modules for essence builders | PDF reader, web scraper, calendar integration |

### 9.2 Distribution Models

| Model | How It Works | Who Pays for LLM | User Gets |
|---|---|---|---|
| **Buy** | Download the essence folder, run on your own Amber | Buyer (needs own API key) | Full ownership, runs locally |
| **Rent** | Creator hosts Amber + essence, users pay for access | Creator (baked into price) | Remote access, no setup needed |
| **Free** | Free download or free hosted access | Varies | Varies |

The rental model allows creators to run their essence on their own infrastructure and charge users for access — no download, no API key needed on the user's end. Great for expensive essences, try-before-you-buy, or users who don't want local setup.

### 9.3 Pricing & Revenue

- **Vessence takes 20%**, seller gets 80% (applies to both buy and rent models)
- Sellers set and adjust their own prices anytime — pure free market
- Free essences are allowed
- **Skill licensing** is between the essence creator and skill creator — Vessence doesn't mediate
- **Stripe integration** for all payment processing (essence purchases, relay subscriptions, seller payouts)

### 9.4 Relay Monetization

| Tier | What | Price |
|---|---|---|
| **Free (Local)** | Docker on LAN, access via local network only | $0 |
| **Free (Cloudflare Tunnel)** | User sets up own Cloudflare tunnel for remote access | $0 |
| **Relay (Hosted)** | Vessence-hosted relay at `relay.vessences.com` for remote access | $5/month |

The relay is the primary monetization path for the platform itself (separate from marketplace revenue). Users who want remote access without self-hosting a tunnel pay $5/month for the managed relay service.

### 9.5 Essences Are Immutable

Essences don't get updated. No versioning, no migration. If domain knowledge changes (new tax year), the seller publishes a new essence and users buy the new edition.

### 9.6 Discovery

Sellers post:
- Description
- Price
- Optional YouTube link demonstrating the essence

### 9.7 Quality Control

- Every essence is **AI-tested** before publishing for malicious attacks and usability
- **First 50 buyers** of any essence get a **100% refund** if they provide a solid and fair review (judged by Claude)
- This bootstraps the review system and incentivizes honest early feedback

### 9.8 Competition

Similar essences are allowed. Competition drives quality. Multiple tax accountant essences can coexist. The best floats to the top through reviews and ratings. No artificial scarcity.

### 9.9 Accounts

Vessence has its own account system. Users can be buyers, sellers, or both. Includes: authentication, purchase history, API key management, seller profiles.

---

## 10. LLM Configuration

### 10.1 One Subscription, Everything Works

Vessence requires only **one AI subscription** to function. The user sets `JANE_BRAIN` to their provider and everything works — no separate API keys needed.

| Provider | Subscription | Smart Model (Jane/Amber) | Cheap Model (Background) | CLI |
|---|---|---|---|---|
| `claude` | Claude Pro/Max | claude-sonnet-4-6 | claude-haiku-4-5-20251001 | `claude` |
| `openai` | ChatGPT Plus/Pro | gpt-4o | gpt-4o-mini | `codex` |
| `gemini` | Gemini Advanced | gemini-2.5-pro | gemini-2.5-flash | `gemini` |

**Smart model** — used for Jane, Amber, user-facing essence interactions. The best model the provider offers.

**Cheap model** — used for background tasks: archivist (memory triage), janitor (nightly consolidation), summarization. Fast and cost-effective.

All calls go through the provider's CLI binary, which uses the user's existing subscription auth. No API key management required.

### 10.2 Per-Essence Model Override

Each essence declares a **preferred model** with reasoning in its manifest. The user:
- Can override to a different model via a simple dropdown
- Is informed of the recommended model and why
- The essence runs on whichever provider the user has configured

### 10.3 Configuration

Set in `.env`:
```
JANE_BRAIN=claude          # or "openai" or "gemini"
SMART_MODEL=               # optional override (defaults to provider's smart model)
CHEAP_MODEL=               # optional override (defaults to provider's cheap model)
```

### 10.4 Online Requirement

Essences require internet — the LLM needs an API/CLI connection. No offline mode.

---

## 11. Platform Infrastructure

### 11.1 Branding

Amber keeps her name but takes on the essence's role title:
- "Amber the accountant"
- "Amber the tutor"
- "Amber the news curator"

### 11.2 Data Portability

USB backup system for essential data. User is responsible for backups. No cloud sync. Backup/export an essence = zip the folder.

### 11.3 User Onboarding

Vessence ships with pre-built essences so it's useful from day one:
- **Essence #1:** Life Librarian (vault)
- Additional starter essences TBD

New users don't start empty.

### 11.4 Desktop Installers

One-click installers that wrap Docker + Vessence into a native install experience:

| Platform | Format | Build Method |
|---|---|---|
| Linux | `.deb` package | Built directly |
| Windows | `.exe` installer | Built directly |
| Mac | `.dmg` installer | Built via GitHub Actions macOS runner |

Each installer handles: Docker installation (if needed), Vessence container pull, initial configuration, and desktop shortcut creation. Mac builds require GitHub Actions because macOS runners are needed for `.dmg` signing and packaging.

### 11.5 Website & Android App

Both need redesign to reflect essence-centric architecture:
- Essence marketplace / store
- Essence loader / switcher
- Skill browser
- Jane as the builder interface
- Per-essence UI rendering (card grids, dashboards, form wizards — not just chat)

---

## 12. Long-Term Vision

- **Digital clone / living memory product** — Jane accumulates a lifetime of memory
- **Digital vessel for preserving loved ones** — Amber can embody anyone's essence
- **Network effects** — more builders → more essences → more users → more builders
- **Platform economics** — Vessence becomes the app store for AI personas
- **Desktop installers** — `.exe`, `.dmg`, `.deb` one-click installers wrapping Docker for frictionless onboarding
- **Relay as monetization** — $5/month managed relay service as the platform's recurring revenue stream (separate from marketplace 20% cut)
- **Mac support** — full macOS support via `.dmg` installer, built using GitHub Actions macOS runners for signing and packaging

---

## 13. Relay Server

The relay server enables remote access to a user's Vessence instance without requiring the user to configure their own tunnel or expose ports.

**Full specification:** See `configs/VESSENCE_RELAY_SPEC.md`

The relay is the **paid tier** of Vessence's connectivity model:

| Tier | Description | Cost |
|---|---|---|
| Local (LAN) | Access Vessence only on the same network as the Docker host | Free |
| Cloudflare Tunnel | User configures their own Cloudflare tunnel for remote access | Free |
| Vessence Relay | Managed relay at `relay.vessences.com` — no user configuration needed | $5/month |

The relay handles WebSocket tunneling between the user's mobile/remote devices and their Docker instance. Authentication is tied to the user's Google account (same account used for website signup and Docker onboarding). The relay server is deployed on a VPS and is the primary source of recurring platform revenue.

---

## 14. Account System

### 14.1 Authentication

- **Google OAuth** is the sole signup/login method for vessences.com
- The same Google account is used during Docker onboarding to auto-link the user's local Vessence instance to their web account
- No email/password registration — Google OAuth only for simplicity and security

### 14.2 User Profiles

- Display name (from Google account, editable)
- Avatar (from Google account, replaceable)
- Purchase history
- Loaded essences
- API key management

### 14.3 Seller Profiles

- Optional public seller profile at `vessences.com/u/<username>`
- Published essences list
- Revenue dashboard
- Reviews and ratings
- Trust badges (new, established, top seller)

### 14.4 Account Linking

When a user installs Vessence via Docker, the onboarding flow asks them to sign in with Google. This links the Docker instance to the same account used on the website and Android app, enabling:

- Relay authentication (Docker ↔ relay ↔ mobile all share the same identity)
- Purchase sync (buy on web, install appears in Docker)
- Unified settings

---

## 15. Multi-User

Vessence supports multiple users on a single Docker instance. The **server admin** (whoever installed Docker) controls how multi-user works:

### 15.1 Separate Jane Instances

Each user gets their own Jane with completely independent memory. Full isolation — users cannot see each other's data, conversations, or essences.

**Best for:** Family members, roommates, or anyone who wants total privacy.

### 15.2 Shared Jane with Separate Conversations

All users interact with the same Jane (shared memory and knowledge), but each user has their own conversation history.

**Best for:** Teams or households where shared context is desirable (e.g., shared household knowledge, shared project context).

### 15.3 Admin Controls

The server admin manages:
- User account creation and deletion
- Which mode each user is in (separate or shared Jane)
- Per-user essence access permissions
- Storage quotas

---

## 16. Jane Personality

### 16.1 Default Personality

Jane's default personality is **direct, technical, and no-filler**. She gets to the point, avoids unnecessary pleasantries, and communicates efficiently. This matches the preferences of the platform's creator and serves as a strong default for technical users.

### 16.2 Customization

Jane's personality is customizable by each user:
- Communication style (formal/casual, verbose/concise, warm/efficient)
- Tone preferences (encouraging, matter-of-fact, playful)
- Domain emphasis (technical depth vs. layperson explanation)

### 16.3 Onboarding

During first-run onboarding, Jane can ask the user about their communication preferences. This is optional — users can skip and use the default, or adjust later in settings.

### 16.4 Per-User Persistence

In multi-user mode, each user's Jane personality preferences are stored separately, even if they share the same Jane instance (§15.2).

---

## 17. Android App

### 17.1 Navigation

- **Hamburger drawer** navigation (slide-out menu from left)
- Sections: Home (chat), Essences, Marketplace, Vault, Settings

### 17.2 Input Methods

- **Mic button** for voice input (speech-to-text)
- **+ button** for attachments, which expands to show:
  - Camera (take photo)
  - File picker (select from device)
  - TTS toggle (text-to-speech on/off for responses)

### 17.3 Share-To Integration

Android's native Share intent is supported. Users can share text, images, files, or URLs from any app directly to Vessence/Jane.

### 17.4 Appearance

- Dark mode and light mode (follows system preference, with manual override)
- Jane's face as the app icon
- Material Design 3 components

### 17.5 Auto-Update

The app includes an auto-update system that checks for new versions and prompts the user to update. No Play Store dependency required (sideloaded APK update flow).

### 17.6 Chat Persistence

All conversations are persisted locally on the device. Chat history syncs across devices when connected to the same Vessence instance (via LAN or relay).

### 17.7 Native Essence Views

The Android app renders per-essence UI layouts natively (dashboards, card grids, form wizards) — not just a chat WebView. Each essence type gets a native Android rendering path.

---

## 18. Notifications

**Status: Deferred.**

Proactive Jane messaging (Jane reaching out to the user unprompted based on triggers, scheduled tasks, or detected opportunities) is planned but deferred to a future design conversation. This includes:

- Push notifications from Jane
- Proactive suggestions based on user context
- Scheduled check-ins
- Trigger-based alerts from essences

The notification system will be designed in a dedicated future session to ensure proper UX for both mobile and desktop.
