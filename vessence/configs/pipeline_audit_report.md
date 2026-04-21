# Pipeline Audit Report — 2026-04-21 01:16

- Prompts audited: **30**
- Elapsed: 529s
- Classification failures: **7**
- Response failures: **18**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 20
- stage2: 10

## Classification breakdown
- others: 14
- clinic schedules info: 6
- read email: 4
- unclear: 2
- weather: 1
- read messages: 1
- end conversation: 1
- get time: 1

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| is she working on Monday | clinic schedules info | others |
| who's coming in tomorrow | clinic schedules info | others |
| how about tomorrow | clinic schedules info | others |
| casual look like tomorrow | weather | others |
| ping | others | others |
| scary mixed up | unclear | others |
| how can you enforce yourself to do this | unclear | others |

## Response failures (top 20) — usually need code changes
- **who's coming in tomorrow** (clinic schedules info/stage2): On Wednesday she has 8 active patients: John Meeks, Mock Patient, Prabitha Natarajan, Suprama Datta, and 4 more. Cancelled: Prabitha Natarajan, Meliss
- **how about tomorrow** (clinic schedules info/stage2): She has 8 active patients on Wednesday, with 2 cancellations (10 total booked). Would you like to know about another day?
- **casual look like tomorrow** (weather/stage3): Tomorrow she has 10 slots on the books. Two are cancelled — Melissa Solomon at 8 AM and Prabitha Natarajan at 11. That leaves 8 active patients, start
- **what does my schedule look like tomorrow** (others/stage3): Your calendar is clear tomorrow — nothing scheduled for Wednesday.
- **what is my clinic schedule look like tomorrow** (clinic schedules info/stage2): She has 8 active patients on Wednesday, with 2 cancellations (10 total booked). Would you like to know about another day?
- **ping** (others/stage3): Hey Chieh, I'm here.
- **scary mixed up** (unclear/stage2): Sorry, could you say that again?
- **any cancellations** (end conversation/stage2): Ok.
- **can you check my latest email from my wife** (read email/stage3): 

[ACK]Checking your email for messages from Kathia.[/ACK]warded you the Mulberry Forest April Break Enrichment Week details — looks like it's from Em
- **can you read my latest email from my wife again** (read email/stage3): 

<spoken>Sure. Kathia forwarded the Mulberry Forest April Break Enrichment Week email. The program runs 9 to 3 at Whip Hill Park in Stoneham. Kids ne
- **for the first patient I would like to know more details about the patient** (others/stage3): The first active patient on Wednesday is Caile Hanlon at 8 AM. It's a follow-up visit, but unfortunately there are no health concerns, recommendations
- **can you answer my previous question** (others/stage3): This is a fresh conversation — I don't have any previous messages from you here. What was the question? Happy to help.
- **can you delete it for me** (others/stage3): Found it. There are **350 entries** in `long_term_knowledge`, all from `conversation_archivist` — raw conversation snippets. These are the junk entrie
- **no I would like to know more details about the first patient** (others/stage3): 

Let me pull up whatever details are in memory about Melissa Solomon's appointment.ay (Apr 21) — **cancelled**. Also had an 8:00 AM Wednesday (Apr 22
- **okay is that done for both stage 2 and stage 3** (others/stage3): 

Good question — let me verify both paths.

**Stage 2** (the handler): Yes, confirmed. `_names_for_day()` in `handler.py:157` sorts by `_parse_time()
- **how can you enforce yourself to do this** (unclear/stage2): Sorry, could you say that again?
- **are you enforcing the stage 3 thing we just talk about** (others/stage3): 

Honestly — it's a prompt instruction, not code enforcement. Opus *should* follow it, but there's no guarantee it will sort correctly every time. The
- **okay then** (others/stage3): Sounds good — what's next?ke to do next?
