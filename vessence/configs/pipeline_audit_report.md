# Pipeline Audit Report — 2026-04-24 01:15

- Prompts audited: **20**
- Elapsed: 477s
- Classification failures: **7**
- Response failures: **16**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 17
- stage2: 3

## Classification breakdown
- others: 17
- unclear: 3

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| **Send Message Protocol (Stage 2 Handler Present)**: SMS requests route through  | others | send message |
| **Class Protocol: Read Calendar**

The `read_calendar` class handles user reques | others | others |
| I need clarification. The "new turn" you provided is class protocol metadata (de | others | others |
| I understand the read_calendar protocol. The server fetches your Google Calendar | unclear | weather |
| I understand the read_calendar protocol. The server fetches your Google Calendar | unclear | weather |
| user: what's the weather like tomorrow
jane: High of about 47, low of 33, light  | others | others |
| user: okay what is on my to do list
jane: 4 categories: the urgent stuff, studen | others | others |

## Response failures (top 20) — usually need code changes
- **user: the home
jane: 3 items for home. Put the TV from kathia’s room to the gym;** (others/stage3): Message sent. 
- **user: how about for the clinic
jane: 6 items for the clinic. Curtain rods at kat** (unclear/stage2): <spoken>Sorry, I didn't understand that, can you say it again or clarify?</spoken>
- ****Summary:**
Stage 2 and 3 use Google Docs (synced to `todo_list_cache.json` eve** (others/stage3): 

[ACK]Let me check how calendar requests are currently routed.[/ACK]ane_web/jane_v2/classes/read_calendar/handler.py`) and metadata, and `"read calen
- ****Summary:**
Stage 2 and 3 use Google Docs (synced to `todo_list_cache.json` eve** (others/stage3): 

[ACK]Let me double-check the v3 classifier — that might be where it's missing.[/ACK]ich has `READ_CALENDAR` exemplars from `intent_classifier/v2/cla
- ****Send Message Protocol (Stage 2 Handler Present)**: SMS requests route through ** (others/stage3): 

Yes — you were pointing out that the summary injected into context had stale info saying "this class has no Stage 2 handler" for read_calendar, whic
- ****Class Protocol: Read Calendar**

The `read_calendar` class handles user reques** (others/stage3): 

Hey Chieh. Yeah, looks like the context window cycled — those repeated "clarification" blocks are the summarizer getting confused and looping on its
- ****Class Protocol: Read Calendar**

The `read_calendar` class handles user reques** (others/stage3): 

[ACK]Got it — let me figure out what exactly needs building here.[/ACK]

Can you clarify what you'd like to build? From our earlier conversation the
- **I need clarification. The "new turn" you provided is class protocol metadata (de** (others/stage3): 

That's the **context summarizer** — it runs between my standing brain (Opus) and the pipeline. When the conversation gets long, it compresses earlie
- ****Class Protocol: Read Calendar**

The `read_calendar` class handles user reques** (others/stage3): The fix has three layers of defense:

1. **`_strip_injected_metadata()`** — strips `<class_protocol>`, `[EXTRACTED PARAMS]`, `[CURRENT CONVERSATION ST
- ****Class Protocol: Read Calendar**

The `read_calendar` class handles user reques** (others/stage3): 

Got it — you want the calendar handler to always offer the detail follow-up after listing events. Let me check if that's already happening.

Looking
- ****Class Protocol: Read Calendar**

The `read_calendar` class handles user reques** (others/stage3): Your next event is trash removal on Monday April 28th at 7pm. Want details on any of your upcoming events?
- **I understand the read_calendar protocol. The server fetches your Google Calendar** (unclear/stage2): <spoken>Sorry, I didn't understand that, can you say it again or clarify?</spoken>
- **I understand the read_calendar protocol. The server fetches your Google Calendar** (unclear/stage2): <spoken>Sorry, I didn't understand that, can you say it again or clarify?</spoken>
- **user: what's the weather like tomorrow
jane: High of about 47, low of 33, light ** (others/stage3): 

Good question. Inulin (a soluble fiber from chicory root) actually *is* used as a sugar substitute in a lot of products — protein bars, low-sugar ic
- **user: okay what is on my to do list
jane: 4 categories: the urgent stuff, studen** (others/stage3): 

Hey Chieh — what's up? Did something go wrong, or are you reacting to something I said?

[[AWAITING:what_happened
- **user: what's on Maya to do list
jane: <spoken>4 categories: the urgent stuff, st** (others/stage3): Hmm — the calendar API is showing no events for today, which means those two events (helping Catherine with her exam and the ML Reading Group) may hav
