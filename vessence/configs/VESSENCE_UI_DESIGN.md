# Vessence UI Design Document

**Version:** 1.0
**Date:** 2026-03-21
**Author:** The user & Jane

---

## Table of Contents

1. [Design Principles](#1-design-principles)
2. [Website Design](#2-website-design)
3. [Android App Design](#3-android-app-design)
4. [Shared UI Concepts](#4-shared-ui-concepts)
5. [Navigation Flows](#5-navigation-flows)

---

## 1. Design Principles

- **Essence-centric:** Every screen revolves around essences — finding them, loading them, using them, building them
- **Progressive disclosure:** Show only what the user needs at each step; advanced options available but never in the way
- **Zero-chrome in use:** When a user is interacting with an essence, the platform UI disappears — the essence owns the viewport
- **Consistent shell, variable content:** The outer navigation shell stays constant; the inner content area transforms per essence
- **Mobile-first parity:** Android app and website share the same information architecture; layouts adapt to form factor

---

## 2. Website Design

### 2.1 Landing / Marketing Page

**What the user sees:**

```
┌─────────────────────────────────────────────────────┐
│  [Logo] Vessence          [Store] [Docs] [Sign In]  │
├─────────────────────────────────────────────────────┤
│                                                     │
│         AI that becomes what you need.               │
│                                                     │
│    One platform. Infinite roles. Your memory.        │
│                                                     │
│         [Get Started]    [Browse Essences]           │
│                                                     │
├─────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐             │
│  │ Amber   │  │ Jane    │  │ Market  │             │
│  │ loads   │  │ builds  │  │ place   │             │
│  │ any     │  │ custom  │  │ of      │             │
│  │ role    │  │ essences│  │ ready-  │             │
│  │         │  │ for you │  │ made AI │             │
│  └─────────┘  └─────────┘  └─────────┘             │
├─────────────────────────────────────────────────────┤
│  "How it works" — 3-step visual:                    │
│  1. Browse or build an essence                      │
│  2. Load it into Amber                              │
│  3. Amber becomes that role — with your memory      │
├─────────────────────────────────────────────────────┤
│  Featured Essences carousel (4-6 cards)             │
│  [Card: icon, name, tagline, price, avg rating]     │
├─────────────────────────────────────────────────────┤
│  Testimonials / review highlights                   │
├─────────────────────────────────────────────────────┤
│  Footer: About, Docs, Terms, Contact                │
└─────────────────────────────────────────────────────┘
```

**Interactions:**
- "Get Started" → account creation flow
- "Browse Essences" → marketplace page
- Featured essence cards are clickable → essence detail page
- Sign In → dashboard

**Data sources:**
- Featured essences: curated list from admin + algorithmic top-rated
- Testimonials: pulled from review system, highest-rated

---

### 2.2 Marketplace / Store Page

**What the user sees:**

```
┌─────────────────────────────────────────────────────┐
│  [Logo] Vessence   [Store] [Dashboard] [Avatar ▼]   │
├─────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────┐       │
│  │ 🔍 Search essences and skills...         │       │
│  └──────────────────────────────────────────┘       │
│                                                     │
│  [Essences ▼]  [Skills ▼]  [Sort: Popular ▼]       │
│                                                     │
│  Categories (horizontal pill bar):                  │
│  [All] [Finance] [Health] [Education] [Creative]    │
│  [Productivity] [Research] [Entertainment] [Dev]    │
│                                                     │
│  Filter sidebar (collapsible on mobile):            │
│  ├─ Price: Free / Paid / All                        │
│  ├─ Model: Buy / Rent / All                         │
│  ├─ Rating: 4+, 3+, All                             │
│  └─ Model req: Claude / GPT / Gemini / Any          │
│                                                     │
│  Results grid (3 columns):                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │ [icon]   │ │ [icon]   │ │ [icon]   │            │
│  │ Tax      │ │ Fitness  │ │ News     │            │
│  │ Account. │ │ Coach    │ │ Curator  │            │
│  │ ★★★★☆   │ │ ★★★★★   │ │ ★★★★☆   │            │
│  │ $29.99   │ │ Free     │ │ $5/mo    │            │
│  │ Buy      │ │ Buy      │ │ Rent     │            │
│  │ 142 revs │ │ 89 revs  │ │ 211 revs │            │
│  └──────────┘ └──────────┘ └──────────┘            │
│                                                     │
│  [Load more...]                                     │
└─────────────────────────────────────────────────────┘
```

**Interactions:**
- Search is live-filtering with debounce (300ms)
- Category pills are toggle-selectable (multi-select allowed)
- Each card click → essence detail page
- Sort options: Popular, Newest, Price (low-high), Price (high-low), Rating
- Toggle between Essences and Skills tabs

**Data sources:**
- `GET /api/marketplace/essences?category=&sort=&price=&page=`
- `GET /api/marketplace/skills?category=&sort=&page=`
- Card data: `manifest.json` fields (essence_name, description, price, author) + aggregated rating + review count

---

### 2.3 Essence Detail Page

**What the user sees:**

```
┌─────────────────────────────────────────────────────┐
│  [Logo] Vessence   [Store] [Dashboard] [Avatar ▼]   │
├─────────────────────────────────────────────────────┤
│  ← Back to Store                                    │
│                                                     │
│  ┌────────────────────────────────────────────┐     │
│  │  [Large Icon]                              │     │
│  │                                            │     │
│  │  Tax Accountant 2025                       │     │
│  │  by seller_username                        │     │
│  │  ★★★★☆ 4.3  (142 reviews)                 │     │
│  │                                            │     │
│  │  $29.99  ·  Buy (download)                 │     │
│  │                                            │     │
│  │  [Buy Now]   [Add to Wishlist]             │     │
│  └────────────────────────────────────────────┘     │
│                                                     │
│  Tabs: [Overview] [Reviews] [Seller] [Technical]    │
│                                                     │
│  ─── Overview ───                                   │
│  Description (from manifest.description):           │
│  "Prepares US federal tax returns for individuals.  │
│   Guides you through W-2 upload, deduction review,  │
│   and generates a complete filing."                 │
│                                                     │
│  YouTube demo (embedded player, if provided):       │
│  ┌──────────────────────────────┐                   │
│  │      ▶ Video Preview         │                   │
│  └──────────────────────────────┘                   │
│                                                     │
│  Key details:                                       │
│  ├─ UI Type: Form Wizard                            │
│  ├─ Recommended Model: Claude Sonnet 4              │
│  │   "Requires strong analytical reasoning for      │
│  │    tax code interpretation"                      │
│  ├─ Permissions: Internet, File System, Clipboard   │
│  ├─ Provides: tax_preparation, document_analysis    │
│  └─ External API: IRS_API_KEY (optional)            │
│                                                     │
│  ─── Reviews ───                                    │
│  Sort: [Most Recent ▼]                              │
│  ┌────────────────────────────────────────┐         │
│  │ ★★★★★  user123  ·  2026-03-15         │         │
│  │ "Saved me hours. Caught a deduction    │         │
│  │  I would have missed."                 │         │
│  │ [Helpful (12)]                         │         │
│  └────────────────────────────────────────┘         │
│  [Refund-review badge] on early reviews             │
│                                                     │
│  ─── Technical ───                                  │
│  Capabilities provided / consumed                   │
│  Shared skills used                                 │
│  Conversation starters                              │
│  Proactive triggers                                 │
└─────────────────────────────────────────────────────┘
```

**Interactions:**
- "Buy Now" → payment flow → download essence folder → auto-redirect to dashboard
- For Rent essences: "Subscribe" button with monthly price displayed
- Tab navigation (Overview / Reviews / Seller / Technical) is in-page, no reload
- YouTube embed plays inline
- Review pagination with infinite scroll
- "Helpful" button on reviews (one vote per user)
- Seller tab shows seller profile, other published essences

**Data sources:**
- `GET /api/essences/{id}` — full manifest + metadata
- `GET /api/essences/{id}/reviews?sort=&page=`
- `GET /api/sellers/{username}/essences`
- YouTube link from seller-provided metadata

---

### 2.4 User Dashboard

**What the user sees:**

```
┌─────────────────────────────────────────────────────┐
│  [Logo] Vessence   [Store] [Dashboard] [Avatar ▼]   │
├──────────┬──────────────────────────────────────────┤
│ Sidebar  │  My Essences                             │
│          │                                          │
│ Essences │  Currently Loaded (active):              │
│ ──────── │  ┌──────┐ ┌──────┐ ┌──────┐             │
│ My       │  │Tax   │ │File  │ │News  │             │
│ Essences │  │Acct  │ │Archv │ │Curr  │             │
│          │  │[●]   │ │[●]   │ │[●]   │             │
│ Purchase │  │[Open] │ │[Open]│ │[Open]│             │
│ History  │  └──────┘ └──────┘ └──────┘             │
│          │                                          │
│ Jane     │  Available (downloaded, not loaded):     │
│ Builder  │  ┌──────┐ ┌──────┐                      │
│          │  │Recipe│ │Tutor │                      │
│ Settings │  │Browsr│ │Math  │                      │
│ ──────── │  │[Load]│ │[Load]│                      │
│ API Keys │  └──────┘ └──────┘                      │
│ Models   │                                          │
│ Profile  │  [+ Browse Store]                        │
│ Billing  │                                          │
│          │  ─────────────────────────────            │
│ Seller   │  Recent Activity                         │
│ ──────── │  · Tax Acct: "Deadline reminder sent"    │
│ (if      │  · File Archv: "3 files organized"       │
│  seller) │  · News: "Morning briefing ready"        │
└──────────┴──────────────────────────────────────────┘
```

**Interactions:**
- "Open" on a loaded essence → switches to the main app view with that essence active
- "Load" on an available essence → triggers essence loader (permissions prompt → load)
- Unload via right-click context menu or long-press (shows Unload / Delete options)
- "Delete" shows confirmation with option to port memory to Jane
- Purchase History shows all transactions with download-again links
- API Keys section: add/edit/delete keys per provider (Anthropic, OpenAI, Google)
- Model selection: default model preference (overridable per essence)

**Data sources:**
- `GET /api/user/essences` — list of owned essences + load status
- `GET /api/user/purchases`
- `GET /api/user/api-keys` (masked display, only last 4 chars shown)
- Essence activity: from essence working_files / proactive trigger logs

---

### 2.5 Seller Dashboard

**What the user sees:**

```
┌─────────────────────────────────────────────────────┐
│  [Logo] Vessence   [Store] [Dashboard] [Avatar ▼]   │
├──────────┬──────────────────────────────────────────┤
│ Sidebar  │  Seller Dashboard                        │
│          │                                          │
│ (same as │  Revenue Overview                        │
│  user    │  ┌─────────────────────────────────┐     │
│  sidebar │  │  This Month: $1,247.60          │     │
│  + sell  │  │  All Time:   $8,932.00          │     │
│  section)│  │  Pending:    $312.40            │     │
│          │  │  [Revenue chart — last 6 months] │     │
│ Publish  │  └─────────────────────────────────┘     │
│ New      │                                          │
│          │  Published Essences                      │
│ My       │  ┌───────────────────────────────────┐   │
│ Listings │  │ Tax Accountant 2025               │   │
│          │  │ $29.99 · 142 sales · ★4.3         │   │
│ Revenue  │  │ Revenue: $3,415.20                │   │
│          │  │ [View Reviews] [View Stats]        │   │
│ Reviews  │  ├───────────────────────────────────┤   │
│          │  │ Fitness Coach Pro                  │   │
│ Payouts  │  │ Free · 89 downloads · ★4.8        │   │
│          │  │ [View Reviews] [View Stats]        │   │
│          │  └───────────────────────────────────┘   │
│          │                                          │
│          │  Recent Reviews (across all essences)    │
│          │  ┌─────────────────────────────────┐     │
│          │  │ ★★★★★ on Tax Acct · 2h ago      │     │
│          │  │ "Excellent. Found $800 in..."    │     │
│          │  │ [Reply]                          │     │
│          │  └─────────────────────────────────┘     │
└──────────┴──────────────────────────────────────────┘
```

**Interactions:**
- "Publish New" → opens Jane builder interface in publish mode
- Per-essence stats: sales over time chart, geographic distribution, model usage breakdown
- Review management: seller can reply to reviews (public replies)
- Payout settings: bank/payment info, payout schedule
- Price adjustment: click price on any listing to edit inline (takes effect immediately)

**Data sources:**
- `GET /api/seller/revenue?period=month`
- `GET /api/seller/essences` — with sales, revenue, rating per listing
- `GET /api/seller/reviews?page=`
- `GET /api/seller/payouts`

---

### 2.6 Jane Builder Interface

**What the user sees:**

```
┌─────────────────────────────────────────────────────┐
│  [Logo] Vessence   [Store] [Dashboard] [Avatar ▼]   │
├──────────┬──────────────────────────────────────────┤
│          │  Jane — Essence Builder                   │
│ Progress │                                          │
│ ──────── │  ┌──────────────────────────────────┐    │
│ ✓ Ident. │  │  Chat with Jane                  │    │
│ ✓ Know.  │  │                                  │    │
│ ● Funcs  │  │  Jane: "What custom functions    │    │
│ ○ Skills │  │  does your essence need? These    │    │
│ ○ UI     │  │  are things Amber can't already   │    │
│ ○ Inter. │  │  do with platform skills."        │    │
│ ○ Trigg. │  │                                  │    │
│ ○ Capab. │  │  You: "It needs to calculate     │    │
│ ○ Model  │  │  compound interest and generate   │    │
│ ○ Perms  │  │  amortization tables."           │    │
│ ○ Creds  │  │                                  │    │
│ ○ Data   │  │  Jane: "Got it. I'll create two  │    │
│          │  │  functions:                       │    │
│ ──────── │  │  1. calculate_compound_interest   │    │
│ [Preview │  │  2. generate_amortization_table   │    │
│  Spec]   │  │                                  │    │
│          │  │  Any other calculations needed?"  │    │
│          │  │                                  │    │
│          │  │  ┌────────────────────────────┐   │    │
│          │  │  │ Type your response...      │   │    │
│          │  │  └────────────────────────────┘   │    │
│          │  └──────────────────────────────────┘    │
└──────────┴──────────────────────────────────────────┘
```

**Progress sidebar** tracks the 12 interview sections from the spec (section 5.2). Each shows:
- `✓` completed
- `●` in progress
- `○` not started

**After interview completes — Spec Preview:**

```
┌─────────────────────────────────────────────────────┐
│  Spec Preview                                       │
│                                                     │
│  Essence: Loan Calculator Pro                       │
│  Role: "the loan advisor"                           │
│  UI Type: hybrid (chat + calculator panel)          │
│  Model: Claude Sonnet 4                             │
│                                                     │
│  [Full spec displayed as formatted document]        │
│                                                     │
│  [Approve & Build]   [Edit Spec]   [Back to Chat]   │
└─────────────────────────────────────────────────────┘
```

**After approval — Build Progress:**

```
┌─────────────────────────────────────────────────────┐
│  Building: Loan Calculator Pro                      │
│                                                     │
│  ✓ Creating folder structure                        │
│  ✓ Writing personality.md                           │
│  ✓ Writing manifest.json                            │
│  ● Building custom functions (2 of 2)               │
│  ○ Generating knowledge base                        │
│  ○ Creating UI layout                               │
│  ○ Writing onboarding workflow                      │
│  ○ Running AI quality tests                         │
│                                                     │
│  [progress bar ████████░░░░░░░░ 45%]                │
│                                                     │
│  Build log (collapsible):                           │
│  > Writing calculate_compound_interest...           │
│  > Function validated successfully                  │
│  > Writing generate_amortization_table...           │
└─────────────────────────────────────────────────────┘
```

**Interactions:**
- Chat is the primary interface during the interview; Jane drives the conversation
- Progress sidebar items are clickable to revisit completed sections
- "Preview Spec" available at any time (shows current state, incomplete sections flagged)
- "Approve & Build" disabled until all sections are completed
- Build progress is real-time with expandable log
- After build completes: "Load Now" and "Publish to Marketplace" buttons appear

**Data sources:**
- Interview state: maintained in session (which sections completed, answers collected)
- Build progress: WebSocket or SSE stream from build process
- Spec preview: generated from collected interview answers

---

### 2.7 Main App View (Essence in Use)

**What the user sees:**

```
┌─────────────────────────────────────────────────────┐
│  Essence Switcher (tab bar):                        │
│  [Tax Acct ●] [File Archv ●] [News ●] [+ Add]      │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────────────────────────────────┐       │
│  │                                          │       │
│  │     Essence-specific content area        │       │
│  │     (rendered per UI type — see §2.8)    │       │
│  │                                          │       │
│  │                                          │       │
│  │                                          │       │
│  │                                          │       │
│  └──────────────────────────────────────────┘       │
│                                                     │
│  Bottom bar:                                        │
│  [Model: Claude Sonnet 4 ▼]  [⚙ Essence Settings]  │
└─────────────────────────────────────────────────────┘
```

**Interactions:**
- Tab bar shows all currently loaded essences; click to switch
- Green dot `●` on tab = essence is loaded and active
- `+ Add` opens a quick-load panel (owned essences not yet loaded)
- Model dropdown allows overriding the preferred model for this session
- Essence Settings: permissions review, unload, delete (with memory port option)
- Content area is fully controlled by the essence's UI definition

**Data sources:**
- Loaded essences list: runtime state from essence loader
- Active essence: determines which content to render
- Model selection: user preference overriding manifest.preferred_model

---

### 2.8 Per-Essence UI Rendering

Each essence declares a `ui.type` in its manifest. The platform renders accordingly:

#### Chat View (`type: "chat"`)

```
┌──────────────────────────────────────────┐
│  Amber the file archivist                │
│                                          │
│  [Conversation starters as chips:]       │
│  [Organize my downloads] [Find a file]   │
│                                          │
│  Amber: "What would you like to          │
│  organize today?"                        │
│                                          │
│  You: "Sort my desktop files"            │
│                                          │
│  Amber: "I found 47 files on your        │
│  desktop. Here's how I'd organize..."    │
│                                          │
│  ┌──────────────────────────────┐        │
│  │ Message...            [Send] │        │
│  │ [📎 Attach] [🎤 Voice]       │        │
│  └──────────────────────────────┘        │
└──────────────────────────────────────────┘
```

#### Card Grid View (`type: "card_grid"`)

```
┌──────────────────────────────────────────┐
│  Amber the news curator                  │
│                                          │
│  [Filter: All] [Tech] [Finance] [World]  │
│                                          │
│  ┌──────────┐ ┌──────────┐              │
│  │ [image]  │ │ [image]  │              │
│  │ AI chip  │ │ Fed rate │              │
│  │ shortage │ │ decision │              │
│  │ impacts  │ │ expected │              │
│  │ 2h ago   │ │ 4h ago   │              │
│  │ [Read]   │ │ [Read]   │              │
│  └──────────┘ └──────────┘              │
│  ┌──────────┐ ┌──────────┐              │
│  │ ...      │ │ ...      │              │
│  └──────────┘ └──────────┘              │
│                                          │
│  Chat overlay (collapsed):               │
│  [💬 Ask about the news...]              │
└──────────────────────────────────────────┘
```

#### Form Wizard View (`type: "form_wizard"`)

```
┌──────────────────────────────────────────┐
│  Amber the accountant                    │
│                                          │
│  Step 2 of 5: Income Sources             │
│  [●━━●━━●━━○━━○]                         │
│                                          │
│  W-2 Income                              │
│  ┌─────────────────────────────┐         │
│  │ Employer: [____________]    │         │
│  │ Wages:    [$___________]    │         │
│  │ Federal:  [$___________]    │         │
│  └─────────────────────────────┘         │
│                                          │
│  [+ Add another W-2]                     │
│                                          │
│  Amber says: "Don't forget to include    │
│  any freelance income under 1099s."      │
│                                          │
│  [← Back]              [Next Step →]     │
└──────────────────────────────────────────┘
```

#### Dashboard View (`type: "dashboard"`)

```
┌──────────────────────────────────────────┐
│  Amber the fitness coach                 │
│                                          │
│  ┌──────────────┐ ┌──────────────┐      │
│  │ This Week    │ │ Streak       │      │
│  │ 4/5 workouts │ │ 12 days      │      │
│  └──────────────┘ └──────────────┘      │
│                                          │
│  ┌──────────────────────────────┐        │
│  │ Progress Chart               │        │
│  │ [line chart: weight/reps]    │        │
│  └──────────────────────────────┘        │
│                                          │
│  Today's Workout:                        │
│  □ Bench Press  3x10 @ 135lb            │
│  □ Squat        4x8  @ 185lb            │
│  ☑ Deadlift     3x5  @ 225lb            │
│                                          │
│  [💬 Chat with coach]                    │
└──────────────────────────────────────────┘
```

#### Hybrid View (`type: "hybrid"`)

```
┌──────────────────────────────────────────┐
│  Amber the research assistant            │
│                                          │
│  ┌─────────────────┬────────────────┐    │
│  │ Chat            │ Side Panel     │    │
│  │                 │                │    │
│  │ You: "Find     │ Sources:       │    │
│  │ papers on       │ ┌────────────┐ │    │
│  │ transformer     │ │ Paper 1    │ │    │
│  │ efficiency"     │ │ Smith 2025 │ │    │
│  │                 │ │ [Open]     │ │    │
│  │ Amber: "Found  │ ├────────────┤ │    │
│  │ 12 relevant     │ │ Paper 2    │ │    │
│  │ papers..."      │ │ Lee 2026   │ │    │
│  │                 │ │ [Open]     │ │    │
│  │                 │ └────────────┘ │    │
│  │                 │                │    │
│  │ [Message...]    │ [Notes panel]  │    │
│  └─────────────────┴────────────────┘    │
└──────────────────────────────────────────┘
```

**Data sources for all view types:**
- Layout structure: `ui/layout.json` from the essence package
- Data bindings: layout.json maps UI components to essence functions and data fields
- Conversation starters: `manifest.interaction_patterns.conversation_starters`
- Dynamic content: returned by essence custom functions or shared skills

---

## 3. Android App Design

### 3.1 Home Screen

**What the user sees:**

```
┌─────────────────────────┐
│ ≡  Vessence        [👤]  │
├─────────────────────────┤
│                         │
│  Loaded Essences        │
│                         │
│  ┌───────────────────┐  │
│  │ [icon] Tax Acct   │  │
│  │ ● Active          │  │
│  │ Claude Sonnet 4   │  │
│  │              [→]  │  │
│  ├───────────────────┤  │
│  │ [icon] File Archv │  │
│  │ ● Active          │  │
│  │ Gemini Flash      │  │
│  │              [→]  │  │
│  ├───────────────────┤  │
│  │ [icon] News Curr  │  │
│  │ ● Active          │  │
│  │ GPT-4o            │  │
│  │              [→]  │  │
│  └───────────────────┘  │
│                         │
│  Available              │
│  ┌───────────────────┐  │
│  │ [icon] Recipe     │  │
│  │ ○ Not loaded      │  │
│  │           [Load]  │  │
│  └───────────────────┘  │
│                         │
│  [+ Browse Store]       │
│                         │
├─────────────────────────┤
│ [Home] [Store] [Jane] [⚙]│
└─────────────────────────┘
```

**Interactions:**
- Tap an active essence → opens the per-essence view for that essence
- "Load" button → triggers essence loader flow (permissions → activate)
- Long-press an essence → context menu: Unload, Delete (with memory port), Info
- Pull-to-refresh updates essence status and proactive notifications
- FAB or "+ Browse Store" → navigate to Store tab

**Data sources:**
- Local essence folder scan: `essences/` directory
- Load state: runtime essence loader status
- Model info: from each essence's manifest.preferred_model (or user override)

---

### 3.2 Essence Store (Mobile)

**What the user sees:**

```
┌─────────────────────────┐
│ ←  Essence Store   [🔍]  │
├─────────────────────────┤
│                         │
│  [Search bar]           │
│                         │
│  [Essences] [Skills]    │
│                         │
│  Categories:            │
│  [All][Finance][Health] │
│  [Education][Creative]  │
│                         │
│  Featured               │
│  ┌──────┐ ┌──────┐     │
│  │[icon]│ │[icon]│ ←→  │
│  │Tax   │ │Coach │     │
│  │★4.3  │ │★4.8  │     │
│  │$29.99│ │Free  │     │
│  └──────┘ └──────┘     │
│                         │
│  Popular                │
│  ┌───────────────────┐  │
│  │[ic] News Curator  │  │
│  │    ★4.4 · $5/mo   │  │
│  │    Rent · 211 rev  │  │
│  ├───────────────────┤  │
│  │[ic] Study Buddy   │  │
│  │    ★4.6 · $9.99   │  │
│  │    Buy · 67 revs   │  │
│  └───────────────────┘  │
│                         │
├─────────────────────────┤
│ [Home] [Store] [Jane] [⚙]│
└─────────────────────────┘
```

**Interactions:**
- Featured section is a horizontal scrollable carousel
- Popular section is a vertical list with infinite scroll
- Tap any essence → mobile essence detail page (same info as web, vertical layout)
- Search icon expands full-screen search with filters
- Category pills are horizontally scrollable

**Data sources:**
- Same API endpoints as web marketplace
- Featured: curated + algorithmic
- Images cached locally for performance

---

### 3.3 Essence Loader (Mobile)

When a user taps "Buy" or "Load," they enter the loader flow:

```
Step 1: Purchase (if not owned)
┌─────────────────────────┐
│  Tax Accountant 2025    │
│  $29.99                 │
│                         │
│  [Google Pay]           │
│  [Credit Card]          │
│  [Vessence Balance]     │
│                         │
│  [Complete Purchase]    │
└─────────────────────────┘

Step 2: Download
┌─────────────────────────┐
│  Downloading...         │
│                         │
│  Tax Accountant 2025    │
│  ████████░░░░  67%      │
│  12.4 MB / 18.5 MB      │
│                         │
│  Installing knowledge   │
│  base...                │
└─────────────────────────┘

Step 3: Permissions
┌─────────────────────────┐
│  Permissions Required   │
│                         │
│  Tax Accountant 2025    │
│  needs access to:       │
│                         │
│  ☐ Internet             │
│    API calls and web    │
│    search               │
│                         │
│  ☐ File System          │
│    Read/write files     │
│    for tax documents    │
│                         │
│  ☐ Clipboard            │
│    Copy/paste data      │
│                         │
│  All permissions are    │
│  required. Accept all   │
│  or cancel.             │
│                         │
│  [Accept All & Load]    │
│  [Cancel]               │
└─────────────────────────┘

Step 4: Activation
┌─────────────────────────┐
│  ✓ Ready                │
│                         │
│  Amber the accountant   │
│  is loaded and ready.   │
│                         │
│  Model: Claude Sonnet 4 │
│  (recommended)          │
│                         │
│  [Open Now]             │
│  [Back to Home]         │
└─────────────────────────┘
```

**Interactions:**
- Step 1 is skipped for free essences or already-owned essences
- Step 2 shows real-time download progress; cancelable
- Step 3 is all-or-nothing — no partial permissions
- Step 4 confirms successful load; "Open Now" goes directly to the essence view
- If the user lacks an API key for the required model, a prompt appears between steps 3 and 4 to add one

**Data sources:**
- Purchase: `POST /api/purchases`
- Download: `GET /api/essences/{id}/download` (streamed)
- Permissions: parsed from `manifest.json` permissions array
- Activation: local essence loader initializes ChromaDB, registers tools

---

### 3.4 Per-Essence Views (Mobile)

Mobile essence views adapt the same 5 paradigms to a single-column layout.

**Chat (mobile):** Full-screen chat with input at bottom. Voice input button prominent. Conversation starters shown as tappable chips above the first message.

**Card Grid (mobile):** Single-column card list with pull-to-refresh. Category filter as horizontally scrollable chips at top. Tap card to expand full detail. Chat accessible via a floating action button.

**Form Wizard (mobile):** Full-width form fields. Step indicator as a horizontal progress bar at top. "Back" and "Next" buttons fixed at bottom. Amber's contextual tips appear as dismissible cards between form sections.

**Dashboard (mobile):** Vertically stacked stat cards and charts. Scrollable. Workout checklist or similar interactive elements are full-width. Chat with coach accessible via FAB.

**Hybrid (mobile):** Chat is the primary view. Side panel content is accessible via a slide-out drawer (swipe from right edge) or via a toggle button in the top bar. When a source or reference is mentioned in chat, it is tappable to open the drawer to that item.

---

### 3.5 Jane Builder (Mobile)

```
┌─────────────────────────┐
│ ←  Jane Builder    [📋]  │
├─────────────────────────┤
│                         │
│  Progress: 3/12         │
│  [●●●○○○○○○○○○]        │
│                         │
│  Current: Custom Funcs  │
│                         │
│  ┌───────────────────┐  │
│  │ Jane: "What       │  │
│  │ custom functions   │  │
│  │ does your essence  │  │
│  │ need?"             │  │
│  │                   │  │
│  │ You: "Compound    │  │
│  │ interest calc and  │  │
│  │ amortization."     │  │
│  │                   │  │
│  │ Jane: "Got it..." │  │
│  └───────────────────┘  │
│                         │
│  ┌───────────────────┐  │
│  │ Message...  [Send]│  │
│  └───────────────────┘  │
│                         │
├─────────────────────────┤
│ [Home] [Store] [Jane] [⚙]│
└─────────────────────────┘
```

**Interactions:**
- Progress bar is tappable — opens a bottom sheet listing all 12 sections with status
- Clipboard icon in top bar → opens spec preview as a full-screen modal
- After spec approval, build progress replaces the chat view
- Build completion shows "Load Now" and "Publish" buttons
- Same flow as web, adapted to single-column

**Data sources:**
- Same as web builder interface
- Session state persisted so user can leave and return

---

### 3.6 Settings (Mobile)

```
┌─────────────────────────┐
│ ←  Settings              │
├─────────────────────────┤
│                         │
│  Account                │
│  ┌───────────────────┐  │
│  │ Profile           │  │
│  │ Email & Password  │  │
│  │ Seller Account    │  │
│  └───────────────────┘  │
│                         │
│  API Keys               │
│  ┌───────────────────┐  │
│  │ Anthropic         │  │
│  │ sk-...4f2a  [Edit]│  │
│  ├───────────────────┤  │
│  │ OpenAI            │  │
│  │ Not set    [Add]  │  │
│  ├───────────────────┤  │
│  │ Google AI         │  │
│  │ AI...8x3k  [Edit]│  │
│  ├───────────────────┤  │
│  │ Ollama (local)    │  │
│  │ localhost:11434   │  │
│  └───────────────────┘  │
│                         │
│  Default Model          │
│  ┌───────────────────┐  │
│  │ [Claude Sonnet 4▼]│  │
│  │ Used when essence │  │
│  │ has no preference │  │
│  └───────────────────┘  │
│                         │
│  Data                   │
│  ┌───────────────────┐  │
│  │ Backup Essences   │  │
│  │ Export Memory      │  │
│  │ Clear Cache        │  │
│  └───────────────────┘  │
│                         │
│  Purchase History  [→]  │
│  About Vessence    [→]  │
│                         │
├─────────────────────────┤
│ [Home] [Store] [Jane] [⚙]│
└─────────────────────────┘
```

**Interactions:**
- API key fields are masked; tap "Edit" to reveal/modify (requires device auth)
- Model dropdown shows only models for which the user has a valid API key (plus local Ollama models)
- "Backup Essences" creates a zip of the essences folder, shareable via system share sheet
- "Export Memory" exports Jane's universal memory as a portable file
- "Seller Account" opens seller dashboard if enabled, or enrollment flow if not

**Data sources:**
- `GET /api/user/profile`
- `GET /api/user/api-keys`
- Local Ollama model list: `GET http://localhost:11434/api/tags`
- Default model preference: stored locally + synced to server

---

## 4. Shared UI Concepts

### 4.1 Essence Switcher

The essence switcher is the primary navigation between loaded essences. It adapts per platform:

| Platform | Implementation | Behavior |
|---|---|---|
| **Web** | Horizontal tab bar below the top nav | Tabs show essence icon + short name; green dot for active; click to switch; `+ Add` at end |
| **Android** | Bottom sheet or horizontal scroll at top of home screen | Tap to open; swipe between essences; long-press for options |

Design rules:
- Maximum 8 tabs visible; overflow goes into a "More" menu
- Active essence tab is visually distinguished (bold text, underline, or filled background)
- Each tab shows a status indicator: `●` loaded, `○` available, `⟳` loading
- Switching is instant — essence state is preserved in memory

### 4.2 Permissions Acceptance

Permissions are displayed before loading any essence. The UI follows a consistent pattern across platforms:

```
┌──────────────────────────────────┐
│  [Essence Icon]                  │
│  [Essence Name] needs:           │
│                                  │
│  ● Internet Access               │
│    "API calls to tax services"   │
│                                  │
│  ● File System                   │
│    "Read/write tax documents"    │
│                                  │
│  ● Clipboard                     │
│    "Copy calculated results"     │
│                                  │
│  ─────────────────────────────── │
│  All permissions required.       │
│  This essence was AI-tested      │
│  for safety on [date].           │
│                                  │
│  [Accept All & Load]  [Cancel]   │
└──────────────────────────────────┘
```

Design rules:
- No checkboxes — all-or-nothing acceptance (per spec section 7)
- Each permission has a short human-readable explanation (derived from manifest context)
- AI-tested badge shown with test date for trust signal
- On web: rendered as a modal dialog
- On Android: rendered as a full-screen bottom sheet

### 4.3 Model Selection Dropdown

Available everywhere an essence is active (main app view bottom bar, essence settings):

```
┌──────────────────────────┐
│  Model                   │
│  ┌────────────────────┐  │
│  │ Claude Sonnet 4  ▼ │  │
│  └────────────────────┘  │
│                          │
│  Dropdown:               │
│  ┌────────────────────┐  │
│  │ ★ Claude Sonnet 4  │  │  ← recommended (star icon)
│  │   Claude Haiku     │  │
│  │   Claude Opus 4    │  │
│  │ ──────────────     │  │
│  │   GPT-4o           │  │
│  │   GPT-4            │  │
│  │ ──────────────     │  │
│  │   Gemini Flash     │  │
│  │   Gemini Pro       │  │
│  │ ──────────────     │  │
│  │   gemma3:4b (local)│  │
│  └────────────────────┘  │
│                          │
│  "Recommended: Claude    │
│   Sonnet 4 — strong      │
│   analytical reasoning"  │
└──────────────────────────┘
```

Design rules:
- Grouped by provider, separated by dividers
- Recommended model has a star icon and appears first in its group
- Models without a configured API key are grayed out with "(no key)" label
- Recommendation reason shown as helper text below the dropdown
- Selection persists per essence (stored in user preferences, not in the essence)

### 4.4 Reviews and Ratings Display

Reviews follow a consistent card format across marketplace, detail pages, and seller dashboard:

```
┌────────────────────────────────────┐
│  ★★★★★  username123               │
│  March 15, 2026                    │
│                                    │
│  "Saved me hours on my tax filing. │
│  Caught a deduction I would have   │
│  missed completely."               │
│                                    │
│  [Helpful (12)]                    │
│                                    │
│  [Refund Review badge]  ← if applicable
│                                    │
│  Seller reply:                     │
│  "Thank you! Glad it helped."      │
└────────────────────────────────────┘
```

Aggregate ratings (shown on cards and detail header):

```
★★★★☆ 4.3  (142 reviews)

Rating breakdown (detail page):
★★★★★  ████████████████  72%
★★★★☆  ████████         18%
★★★☆☆  ███               6%
★★☆☆☆  █                 2%
★☆☆☆☆  █                 2%
```

Design rules:
- "Refund Review" badge distinguishes first-50-buyer reviews (per spec section 8.5); displayed but not called out negatively — these are legitimate reviews from incentivized early adopters
- "Helpful" count drives sort order for "Most Helpful" sort option
- Seller replies are indented beneath the review
- One review per user per essence
- Edit/delete own review available via kebab menu

### 4.5 Multi-Paradigm Renderer

The renderer is the core component that reads `ui/layout.json` and produces the correct view. It works identically on web and Android (with responsive layout adjustments).

**Rendering pipeline:**

```
manifest.json → ui.type
                  ↓
              layout.json → component tree
                  ↓
              renderer maps components to native widgets:
                  ↓
    ┌─────────────────────────────────────────┐
    │ Component        │ Web          │ Mobile │
    │ ─────────────────┼──────────────┼────────│
    │ chat_panel       │ <ChatPanel>  │ ChatV. │
    │ card_grid        │ CSS Grid     │ RecycV │
    │ form_field       │ <input>      │ TextIn │
    │ chart            │ Chart.js     │ MPChar │
    │ progress_bar     │ <progress>   │ ProgBr │
    │ side_panel       │ flex column  │ Drawer │
    │ stat_card        │ <div>        │ CardV. │
    │ checklist        │ <ul>         │ RecycV │
    │ media_embed      │ <iframe>     │ WebVw  │
    └─────────────────────────────────────────┘
```

**layout.json structure:**

```json
{
  "type": "hybrid",
  "panels": [
    {
      "id": "main_chat",
      "component": "chat_panel",
      "position": "left",
      "width": "60%"
    },
    {
      "id": "sources",
      "component": "card_grid",
      "position": "right",
      "width": "40%",
      "data_source": "functions.search_papers",
      "card_template": {
        "title": "{{result.title}}",
        "subtitle": "{{result.author}} · {{result.year}}",
        "action": {"label": "Open", "function": "functions.open_paper"}
      }
    }
  ]
}
```

Design rules:
- The renderer is a platform-level component, not per-essence
- Essences declare layout; the renderer enforces responsive behavior
- On mobile, multi-panel layouts collapse: side panels become drawers, grids become single-column
- Unknown component types fall back to a generic content block
- Chat is always available as a fallback — even non-chat essences have a chat FAB or overlay

### 4.6 External Credentials Prompt

When an essence requires external API keys (like IRS_API_KEY), the user is prompted on first load:

```
┌──────────────────────────────────┐
│  External API Key                │
│                                  │
│  Tax Accountant 2025 can use:    │
│                                  │
│  IRS_API_KEY (optional)          │
│  "Enables direct e-filing"      │
│                                  │
│  ┌──────────────────────────┐    │
│  │ Enter key: [__________]  │    │
│  └──────────────────────────┘    │
│                                  │
│  [Save]  [Skip for now]         │
└──────────────────────────────────┘
```

- Required credentials block loading until provided
- Optional credentials show "Skip for now" and can be added later via essence settings
- Keys are stored encrypted in user profile, never in the essence folder

---

## 5. Navigation Flows

### 5.1 New User Flow

```
Landing Page
    ↓
[Get Started]
    ↓
Create Account (email, password)
    ↓
API Key Setup
  "Add at least one LLM API key to get started"
  [Anthropic] [OpenAI] [Google] [Skip — use local Ollama]
    ↓
Dashboard (with pre-installed Life Librarian essence loaded)
    ↓
Onboarding tooltip: "This is your first essence. Try it out,
or browse the store for more."
```

### 5.2 Buy and Load Essence Flow

```
Store Page → Browse/Search
    ↓
Essence Detail Page → Review info, watch demo
    ↓
[Buy Now]
    ↓
Payment (web: Stripe / Android: Google Pay)
    ↓
Download essence package
    ↓
Permissions prompt (accept all or cancel)
    ↓
External credentials prompt (if any)
    ↓
Essence loaded → redirected to main app view with new essence active
```

### 5.3 Build Essence Flow

```
Dashboard → [Jane Builder] (sidebar or bottom nav)
    ↓
Jane: "Let's build an essence. What role should Amber take on?"
    ↓
Interview (12 sections, tracked in progress sidebar/bar)
    ↓
[Preview Spec] → review generated spec document
    ↓
[Approve & Build]
    ↓
Build progress (real-time updates)
    ↓
Build complete
    ↓
[Load Now] — load into local Amber
[Publish to Marketplace] — opens publish form:
  - Set price (or free)
  - Add YouTube demo link (optional)
  - Write description
  - [Submit for AI Testing]
    ↓
AI testing (automated, results in minutes)
    ↓
Published to marketplace (or returned with issues to fix)
```

### 5.4 Rent Essence Flow

```
Store Page → Essence Detail (rental listing)
    ↓
[Subscribe — $5/mo]
    ↓
Payment setup (recurring)
    ↓
No download — essence runs on creator's infrastructure
    ↓
Permissions prompt (network access only for remote essences)
    ↓
Essence appears in loaded list, connects to remote Amber
    ↓
Interact as normal (latency may be slightly higher)
```

### 5.5 Delete Essence Flow

```
Essence context menu → [Delete]
    ↓
"Do you want to save this essence's learned data
 to your permanent memory?"
    ↓
[Yes, save to Jane] → memory ported to user_memories collection
[No, delete everything] → essence folder removed
    ↓
Essence removed from loaded list and dashboard
```

### 5.6 Android Bottom Navigation

```
[Home]   [Store]   [Jane]   [Settings]
  │         │        │          │
  │         │        │          └→ API keys, models, profile,
  │         │        │             billing, data management
  │         │        │
  │         │        └→ Jane builder interface (chat)
  │         │           Build new essences
  │         │           View/edit in-progress builds
  │         │
  │         └→ Marketplace browser
  │            Search, categories, featured
  │            Essence detail + purchase
  │
  └→ Home screen
     Loaded essences (tap to open)
     Available essences (tap to load)
     Proactive notifications
```

### 5.7 Web Top Navigation

```
[Logo/Home]  [Store]  [Dashboard]  [Avatar ▼]
                                      │
                                      ├→ Profile
                                      ├→ Seller Dashboard
                                      ├→ Settings
                                      └→ Sign Out

Dashboard sidebar:
├─ My Essences (loaded + available)
├─ Purchase History
├─ Jane Builder
├─ Settings
│   ├─ API Keys
│   ├─ Model Preferences
│   ├─ Profile
│   └─ Billing
└─ Seller (if enrolled)
    ├─ My Listings
    ├─ Revenue
    ├─ Reviews
    └─ Payouts
```
