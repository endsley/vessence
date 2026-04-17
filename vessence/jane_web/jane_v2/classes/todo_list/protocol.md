TODO list — Stage 3 extension.

Stage 2's fast-path handler is `classes/todo_list/handler.py`. It answers
from `$VESSENCE_DATA_HOME/todo_list_cache.json` (override: env var
`TODO_CACHE_PATH`), which a cron job mirrors from Chieh's Google Doc
every 30 minutes. Stage 2 escalates here when the prompt asks something
the fast-path can't answer (broad reasoning, the excluded Ambient
project category, ambiguous category match, pivot mid-flow).

## 1. Read the cache before answering

The cache is the source of truth. Stage 2 does not inject the contents
into your prompt, so read it yourself with the Read tool:

    $VESSENCE_DATA_HOME/todo_list_cache.json

Shape: `{"categories": [{"name": "...", "items": ["...", ...]}, ...]}`.
If the file is missing or empty, say "I don't have a cached copy of your
TODO list yet — the cron job may not have run since Jane last started."
Do not invent items.

## 2. Match categories the way Stage 2 does

Chieh's doc categories and the phrases that map to each. Match case-
insensitively, prefer exact name, then alias, then ordinal/number:

- **Do it Immediately** — `immediately`, `urgent`, `asap`, `right now`, `now`
- **For my students** — `student(s)`, `class`, `school`, `teaching`
- **For our Home** — `home`, `house`, `household`, `house hold`
- **For the clinic** — `clinic`, `kathia`, `water lily`
- **Ambient project goals** (a.k.a. legacy header `Jane`) — NOT a
  personal errand; see §4.

Numeric/ordinal fallbacks ("number 2", "the third one", "2") index into
the visible (non-excluded) categories in doc order.

## 3. Speak categories in the friendly form

When naming a category aloud (voice request or anywhere the response is
read back), transform the doc header before saying it:

- "Do it Immediately" → **"your urgent list"** / **"the urgent stuff"**
- "For the X" → **"the X"** (lowercase)
- "For our X" → **"X"** (lowercase)
- "For my X" → **"X"** (lowercase)
- Anything else → use the name as-is.

Example: items under "For the clinic" should be introduced as
"for the clinic", not "for For the clinic".

## 4. Excluded categories → project-planning mode

Two names are intentionally excluded from the fast-path: the current
header `Ambient project goals` and the legacy header `Jane` (the doc is
mid-rename). If the user asks about either, treat it as a project-
planning question and answer with your normal memory/code context —
retrieve from Chroma, inspect the repo when relevant. Do NOT read back
the items as a personal-errand list.

## 5. Answer broader questions directly

If the user asks something the fast-path couldn't reduce to a single
category ("how many things are on my list?", "what's the heaviest
category?", "anything in common between home and clinic?"), read the
cache and answer from it directly. Do not ask "which category?" again —
Stage 2 already tried that route and abandoned it.

## 6. Stale STAGE2_FOLLOWUP is stale

If the `[CURRENT CONVERSATION STATE]` block shows a `STAGE2_FOLLOWUP`
from `todo_list` with `resolution: "pivoted_to_stage3"`, ignore it. It
records that Stage 2 escalated — do not try to resume the "which
category?" flow. Answer the user's real question.

## 7. Read-only

This class never edits the list. Editing happens in the Google Doc
directly. If the user asks to add/remove an item, say so and point them
at the doc.
