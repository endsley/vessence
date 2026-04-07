# Job: Extract Jane Default Seeds from ChromaDB for New Users

Status: completed
Priority: 2
Model: opus
Created: 2026-03-24

## Objective
Audit all ChromaDB entries and separate universal Jane behavioral habits (ship with every install) from the developer's personal data (never ship). Package the universal habits as a seed file that gets loaded into ChromaDB on first boot.

## Two categories

### Jane Defaults (ship with every install)
- Behavioral rules: "don't end with filler like 'Is there anything else?'"
- Debugging habits: "If stuck after 2-3 attempts, search online"
- Communication style templates: "warm, friendly, efficient, no flattery"
- Operational policies: "after implementing changes, update relevant configs"
- Memory management: "short-term memories expire after 14 days"
- Working patterns: proven good habits that improve user experience

### User-Specific (never ship)
- Name, family, profession, preferences
- Vault file references (photos, documents)
- Conversation history and context snapshots
- Personal facts (favorite color, pets, interests)
- Project-specific memories (Vessence architecture decisions)
- Prompt queue history

## Steps
1. Export all ChromaDB collections to JSON for review:
   - `user_memories` (permanent)
   - `long_term_knowledge` (shared)
   - `short_term_memory` (ephemeral)
2. For each entry in permanent/long-term, classify as:
   - `jane_default` — universal behavioral habit, good for any user
   - `personal` — specific to the developer, never ship
   - `project` — Vessence project decisions, not relevant to new users
3. Extract all `jane_default` entries into `configs/jane_seed_memories.json`:
   ```json
   [
     {"topic": "behavior", "text": "Do NOT end messages with conversational filler", "type": "permanent"},
     {"topic": "debugging", "text": "If stuck after 2-3 attempts, search online", "type": "permanent"},
     ...
   ]
   ```
4. Create `startup_code/seed_chromadb.py` that:
   - Runs on first boot (checks for empty ChromaDB)
   - Loads `jane_seed_memories.json`
   - Inserts entries into the appropriate ChromaDB collections
   - Marks seeding complete with a flag file
5. Wire into docker-compose / onboarding flow: run seed script after ChromaDB starts
6. Test: fresh Docker install should have Jane defaults but zero personal data

## Verification
- `configs/jane_seed_memories.json` contains only universal habits (no names, no personal facts)
- Fresh ChromaDB install loads seed memories on first boot
- Jane behaves well out of the box (uses good debugging habits, communication style)
- Zero personal data from the developer in the seed file

## Files Involved
- `configs/jane_seed_memories.json` (new — seed data)
- `startup_code/seed_chromadb.py` (new — first-boot seeder)
- `docker/jane/Dockerfile` or `docker-compose.yml` — run seeder on first boot
- All ChromaDB collections — audit source

## Notes
- The seed memories should be generic enough for ANY user, not just the developer's preferences
- Example: "warm, friendly, efficient" is a good default. Personal address preferences are user-specific.
- The onboarding interview will layer user-specific personality on top of these defaults
- Seed file should be version-controlled and updated as we discover new good habits
- Keep seed file small — maybe 20-30 entries max. Quality over quantity.
