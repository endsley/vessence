# Job: Use Vessence logo as Essences icon on onboarding page
Status: completed
Priority: 3
Created: 2026-03-27

## Objective
Replace the Essences emoji icon on the onboarding welcome page with the Vessence logo image, matching the branding used elsewhere on the site.

## Context
The onboarding setup.html welcome page (step 0) has three feature cards: Meet Jane, Essences, and Tools. Currently Essences uses the 🎨 emoji (&#127912;). The user wants it replaced with the Vessence logo picture — the same one used as the site logo.

## Pre-conditions
- Identify where the Vessence logo is stored (check marketing_site/ or vault images)
- The onboarding container serves static files from `onboarding/static/`

## Steps
1. Find the Vessence logo image (check `marketing_site/` for logo files, or ask the user if unclear)
2. Copy/resize the logo to `onboarding/static/vessence-logo.png` (keep it small, ~256px, under 100KB)
3. In `onboarding/templates/setup.html`, replace the Essences card emoji:
   ```html
   <div class="text-3xl mb-3">&#127912;</div>
   ```
   with an img tag:
   ```html
   <img src="/static/vessence-logo.png" alt="Essences" class="w-12 h-12 rounded-xl object-cover mb-3"
        onerror="this.outerHTML='<div class=&quot;text-3xl mb-3&quot;>&#127912;</div>'"/>
   ```
4. Verify the image loads on the onboarding page

## Verification
1. Open http://localhost:3000 and confirm the Essences card shows the Vessence logo instead of the emoji
2. Check the image fallback works (rename the file temporarily, reload — should show emoji)

## Files Involved
- `onboarding/templates/setup.html` (Essences feature card, around line 257)
- `onboarding/static/vessence-logo.png` (new file)
- Source logo from `marketing_site/` or vault

## Notes
- Jane's card already uses her picture (`/static/jane.png`), so this follows the same pattern
- The Tools card keeps its wrench emoji (&#128295;) unless the user says otherwise

## Result
I'll work on that in the background. You'll see progress updates here as I go.
