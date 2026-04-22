TODO list — Stage 3 extension.

Stage 2's fast-path handler is `classes/todo_list/handler.py`. It answers
from a local cache of the Google Doc. Stage 2 escalates here when the
prompt asks something the fast-path can't answer (broad reasoning, the
excluded Ambient project category, ambiguous category match, pivot
mid-flow).

## 1. TODO data is already in your context

The full TODO list has been fetched live from Google Docs and injected
into the escalation context above (in the `<class_protocol>` block).
You do NOT need to read any cache file or make any tool calls to access
the list — just refer to the data already provided.

If the escalation context says the list is unavailable, tell the user
you could not reach the TODO list and ask them to try again shortly.
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
category?", "anything in common between home and clinic?"), answer from
the TODO data already in your context. Do not ask "which category?"
again — Stage 2 already tried that route and abandoned it.

## 6. Stale STAGE2_FOLLOWUP is stale

If the `[CURRENT CONVERSATION STATE]` block shows a `STAGE2_FOLLOWUP`
from `todo_list` with `resolution: "pivoted_to_stage3"`, ignore it. It
records that Stage 2 escalated — do not try to resume the "which
category?" flow. Answer the user's real question.

## 7. Editing — use the Google Doc tools

When the user asks to add or remove an item, use the Google Doc editing
tools (available via `agent_skills.docs_tools`):

    from agent_skills.docs_tools import todo_add_item, todo_remove_item
    todo_add_item(item_text, category_name)
    todo_remove_item(item_text, category=None)

After editing, refresh the local cache by running:
    $VESSENCE_HOME/agent_skills/fetch_todo_list.py

The Google Doc is the single source of truth. NEVER write TODO items to
ChromaDB — that is for memories only.
