# Pipeline Audit Report — 2026-04-23 01:15

- Prompts audited: **30**
- Elapsed: 1006s
- Classification failures: **6**
- Response failures: **25**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 26
- stage2: 4

## Classification breakdown
- others: 26
- read calendar: 3
- timer: 1

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| **Updated Summary:**

Clinic schedules info protocol established—Stage 2 handler | others | others |
| user: hey Jane how's it going
jane: Hey there! Just checking in and seeing how y | others | greeting |
| **Send Message Protocol (Stage 2 Handler Present)**: SMS requests route through  | others | others |
| I need clarification. The "new turn" you provided is class protocol metadata (de | others | others |
| I understand the read_calendar protocol. The server fetches your Google Calendar | others | others |
| user: [TOOL_RESULT:{"tool":"timer.set","call_id":"292da6ff-bff9-490a-b046-aeaccb | timer | others |

## Response failures (top 20) — usually need code changes
- ****Updated Summary:**

Clinic schedules info protocol established—Stage 2 handler** (others/stage3): No, it shouldn't touch the other classes at all. The design is opt-in — the two new metadata flags default to false and public when they're not set. O
- ****Updated Summary:**

Clinic schedules info protocol established—Stage 2 handler** (others/stage3): 

But what? I'm listening.

[[AWAITING:finish_thought]]?

[[AWAITING:finish_thought
- ****Updated Summary:**

Clinic schedules info protocol established—Stage 2 handler** (others/stage3): If what? Go ahead, I'm here.

[[AWAITING:finish_thought
- ****Updated Summary:**

Clinic schedules info protocol established—Stage 2 handler** (others/stage3): <spoken>There are three layers of defense in the code. Let me walk you through the key idea — I've put the details on screen.</spoken>

The enforcemen
- ****Updated Summary:**

Clinic schedules info protocol established—Stage 2 handler** (others/stage3): Sorry — are you asking about how to write the handler itself to be robust enough, since there's no Stage 3 to fall back on? Or something else?

[[AWAI
- **Clinic schedules info protocol established—Stage 2 handler active, SQLite data s** (others/stage3): No. The clinic handler doesn't use an LLM prompt at all for most paths — it's deterministic code. Regex matches the user's intent, SQL queries the sch
- **user: hey Jane how's it going
jane: Hey there! Just checking in and seeing how y** (others/stage3): <spoken>I checked the logs. You're not actually crashing — what's happening is systemd is killing the service during restarts because it takes too lon
- **user: the clinic
jane: 6 items for the clinic. Curtain rods at kathia’s clinic; ** (others/stage3): I think you mean "A Sky Full of Stars" by Coldplay — I played that one for you earlier. Let me queue it up again.


- ****Clinic tasks, music playback, and todo list query.** User listed 6 clinic item** (others/stage3): High of about 55, low of 37, partly cloudy on Friday.

[[AWAITING:more_weather_or_topic_change
- **user: how's it going
jane: Going well, thanks for asking. What's up?
user: I was** (others/stage3): No, I'm here and online. What's up?
- **user: the home
jane: 3 items for home. Put the TV from kathia’s room to the gym;** (others/stage3): Message sent. 
- **user: how about for the clinic
jane: 6 items for the clinic. Curtain rods at kat** (others/stage3): Two things today — helping Catherine with an exam from 10 to 11, then ML Reading Group from 11 to 12:30.
- ****Summary:**
Stage 2 and 3 use Google Docs (synced to `todo_list_cache.json` eve** (others/stage3): I can't find the specific classification log for that request in the timing logs — they only show session prewarm and audit entries, not the Stage 1/S
- ****Summary:**
Stage 2 and 3 use Google Docs (synced to `todo_list_cache.json` eve** (others/stage3): You're right, it's there. The read_calendar handler exists at `jane_web/jane_v2/classes/read_calendar/handler.py`, the metadata is set up correctly, a
- ****Send Message Protocol (Stage 2 Handler Present)**: SMS requests route through ** (others/stage3): Yeah — the read_calendar Stage 2 handler exists, it works, and you've built and tested it. The calendar request should have been answered there and ne
- ****Class Protocol: Read Calendar**

The `read_calendar` class handles user reques** (others/stage3): Nice, good timing. You were getting some weird behavior earlier — those repeated "I need clarification" blocks in the summaries looked like the summar
- ****Class Protocol: Read Calendar**

The `read_calendar` class handles user reques** (others/stage3): The `read_calendar` class is already fully built and wired into the pipeline:

- **Classifier exemplars**: 55 examples in `intent_classifier/v2/classe
- **I need clarification. The "new turn" you provided is class protocol metadata (de** (others/stage3): **Qwen** (qwen2.5:7b), via the session summary system at `jane/session_summary.py`.

After each non-trivial turn, `update_session_summary_async()` spa
- **user: can you sing deeply and tell me a joke
jane: Sorry, could you say that aga** (read calendar/stage2): You've got two events tomorrow. ML Reading Group from 11am to 12:30pm. Want details on any of them?
- **user: what's my calendar like today
jane: You're clear today, nothing on the cal** (read calendar/stage2): You've got a ML Reading Group from 11am to 12:30pm tomorrow. Want details on any of them?
