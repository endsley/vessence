# Job: Beautiful Onboarding UI Redesign

Status: completed
Priority: 1
Model: opus
Created: 2026-03-25

## Objective
Redesign the onboarding wizard (setup.html) to be visually stunning and make Google credential setup as frictionless as possible.

## Design Goals
- Beautiful, modern dark UI with smooth animations
- Icons for every step (use emoji or SVG icons)
- Neon purple accent color (user's favorite)
- Minimal text, maximum clarity
- Google OAuth should be one-click — no copy-pasting API keys manually if possible

## Steps to redesign

### Step 1: Welcome
- Full-screen dark gradient background
- Vessence logo/name large and centered with subtle glow
- "Meet Jane and Amber" — brief 1-sentence intro for each
- Single "Get Started" button with animation
- Privacy note: "Everything stays on your machine"

### Step 2: Google Sign-In
- Big friendly Google sign-in button (official Google branding colors)
- One-click OAuth flow — user clicks, Google popup, done
- Show what permissions are needed and why
- If OAuth isn't available, fall back to manual API key entry with clear instructions
- Include a link to get a free Google API key with step-by-step screenshots

### Step 3: Choose Your Brain
- Card-based selection: Claude / Gemini / OpenAI
- Each card has the provider's icon, a brief description, and pricing note
- Pre-select Gemini (free tier) as default
- API key input field appears below the selected card
- "Test Connection" button that verifies the key works

### Step 4: Personalize
- Name input (large, friendly)
- Optional: upload a profile photo
- Communication style selector (casual / professional / technical)

### Step 5: Ready!
- Celebration animation (confetti or subtle particles)
- "Open Jane" button that goes to the chat
- Quick links: "Browse Essences", "Explore Vault", "Settings"

## Visual Design
- Dark theme (#0f172a background)
- Neon purple accents (#7C3AED) for buttons and highlights
- Smooth step transitions (slide or fade)
- Progress indicator showing current step
- Rounded cards with subtle borders and hover effects
- Icons: use emoji + Lucide/Heroicons SVG where available
- Mobile responsive

## Implementation
- Rewrite `onboarding/templates/setup.html`
- Use Tailwind CSS (CDN) + Alpine.js for interactivity
- CSS animations for transitions between steps
- Keep the backend endpoints in `onboarding/main.py` — just make the frontend beautiful

## Verification
- Opens at http://localhost:3000
- All steps work and look polished
- Google sign-in works (or graceful fallback)
- Mobile responsive
- Dark theme consistent with Jane's UI

## Files Involved
- `onboarding/templates/setup.html` (rewrite)
- `onboarding/main.py` (may need new endpoints for OAuth)
- `onboarding/templates/success.html` (update to match new design)
