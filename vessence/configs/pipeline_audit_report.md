# Pipeline Audit Report — 2026-04-22 01:14

- Prompts audited: **30**
- Elapsed: 1154s
- Classification failures: **10**
- Response failures: **23**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 23
- stage2: 7

## Classification breakdown
- others: 19
- clinic schedules info: 6
- end conversation: 2
- read messages: 2
- send message: 1

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| then what did you not read it when I asked you for it | read messages | read messages |
| why did you not add a previously | others | others |
| okay you should for stage 3 use Google Docs as the truth | others | others |
| yes | end conversation | end conversation |
| user: what's the clinic schedule look like for Thursday
jane: She has 5 active p | clinic schedules info | others |
| user: what's the clinic schedule for Wednesday look like
jane: She has 8 active  | clinic schedules info | others |
| user: okay can you tell me more about patient number two
jane: I don't have deta | clinic schedules info | others |
| user: what's this Wednesday schedule look like
jane: She has 8 active patients o | clinic schedules info | others |
| user: what's the clinic schedule like for Thursday
jane: She has 5 active patien | clinic schedules info | others |
| **Updated Summary:**

Clinic schedules info protocol established—Stage 2 handler | others | others |

## Response failures (top 20) — usually need code changes
- **yeah** (end conversation/stage2): Ok.
- **yes please** (send message/stage3): 
- **I thought I asked you to add a new item** (others/stage3): 

You're right — I did add it. Here's the confirmation from the system: **"Added item to For the clinic: Add texting capability to the laptop"**. It's
- **then what did you not read it when I asked you for it** (read messages/stage3): 

You're right, that's on me. Let me read the clinic list for you now.oden block for the door at the clinic
3. Create a clinic Gmail account
4. Put mi
- **why did you not add a previously** (others/stage3): 

[ACK]Fair point — let me look at exactly what happened.[/ACK]

Let me trace what actually happened in this conversation to give you a straight answe
- **we should not have multiple sources of the same data right it should just use th** (others/stage3): You're right. Here's how it works now:

- **Writes** (add/remove) go directly to Google Docs via the API — Docs is the source of truth
- **Reads** hit
- **okay we definitely already have a to-do list on Google Docs and Stage 2 has been** (others/stage3): 

[ACK]Let me check how Stage 3 handles todo-related queries.[/ACK]ndler.py` reads the cache directly and handles add/remove/read operations with zero
- **okay you should for stage 3 use Google Docs as the truth** (others/stage3): 

Understood. I'll update the job spec — Stage 3 should read directly from the Google Doc API (via `docs_tools`), not the cache file. Google Docs is t
- **okay so right now if we escalate to stage 3 stage 3 is going to use the Google D** (others/stage3): No, not yet. Right now Stage 3's `protocol.md` tells Opus to read the local **cache file** (`todo_list_cache.json`). And even that is unreliable since
- **yes** (end conversation/stage3): 

[ACK]On it — implementing the Stage 3 TODO context injection now.[/ACK]hes directly from Google Docs using the existing `fetch_doc_text()` and `pars
- **user: what's the clinic schedule look like for Thursday
jane: She has 5 active p** (clinic schedules info/stage2): I don't have detail records for Thursday
jane this week.
- **user: what's the clinic schedule for Friday look like
jane: She has 5 active pat** (clinic schedules info/stage2): I don't have detail records for Friday look like
jane this week.
- **user: what's the clinic schedule for Wednesday look like
jane: She has 8 active ** (clinic schedules info/stage2): I have listed the patients in the chat for your view. Is there a specific patient you want more details of? If so tell me the patient ID.

1. 8:00am C
- **user: okay can you tell me more about patient number two
jane: I don't have deta** (clinic schedules info/stage2): I don't have detail records for okay can you tell me more patient number two this week this week.
- **user: what's this Wednesday schedule look like
jane: She has 8 active patients o** (clinic schedules info/stage2): I don't have detail records for these patients this week.
- **user: yes
jane: I have listed the patients in the chat for your view. Is there a** (others/stage3): There's no "CLS" column in the schedule database. Where are you seeing it — is it in the Jane App interface (Kathia's scheduling software), a spreadsh
- **user: what's the clinic schedule like for Thursday
jane: She has 5 active patien** (clinic schedules info/stage2): I don't have detail records for Thursday
jane this week.
- ****Updated Summary:**

Clinic schedules info protocol established—Stage 2 handler** (others/stage3): 

[ACK]Let me read job 82 and the current class architecture to assess the impact.[/ACK]age3 = False`, `privacy = None`. Every class that doesn't expl
- ****Updated Summary:**

Clinic schedules info protocol established—Stage 2 handler** (others/stage3): 

Looks like your message got cut off — what were you going to say? [[AWAITING:continue_thought]]ual claim to verify here. The message was cut off mid
- ****Updated Summary:**

Clinic schedules info protocol established—Stage 2 handler** (others/stage3): 

Looks like your message got cut off again — just "if." Take your time, I'm here when you're ready. [[AWAITING:complete_thought]]g to verify; the mes
