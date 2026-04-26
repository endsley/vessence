# Pipeline Audit Report — 2026-04-26 01:15

- Prompts audited: **18**
- Elapsed: 1123s
- Classification failures: **3**
- Response failures: **12**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 17
- stage2: 1

## Classification breakdown
- others: 17
- send message: 1

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| **Class Protocol: Read Calendar**

The `read_calendar` class handles user reques | others | others |
| **Class Protocol: Read Calendar**

The `read_calendar` class handles user reques | others | others |
| user: what's the weather like tomorrow
jane: High of about 47, low of 33, light  | others | others |

## Response failures (top 20) — usually need code changes
- ****Class Protocol: Read Calendar**

The `read_calendar` class handles user reques** (others/stage3): 

<spoken>Hey Chieh, good morning. Yeah, looks like you're back online. What's up?</spoken>
- ****Class Protocol: Read Calendar**

The `read_calendar` class handles user reques** (others/stage3): 

<spoken>Chieh, I see what looks like a garbled message — it's got some internal pipeline metadata mixed in with "yeah let's build it," but I'm not s
- **I need clarification. The "new turn" you provided is class protocol metadata (de** (others/stage3): 

<spoken>That's not you talking — that's my internal summarizer leaking its output into your chat. It's a pipeline bug where the conversation summary
- ****Class Protocol: Read Calendar**

The `read_calendar` class handles user reques** (others/stage3): <spoken>Fixed it. Here's what was happening — when Stage 3 escalation prepends class protocol, voice hints, and conversation state to your message bef
- ****Class Protocol: Read Calendar**

The `read_calendar` class handles user reques** (others/stage3): <spoken>Good news — that's actually already built into the calendar handler. After listing your events, it automatically asks "Would you like to know 
- ****Class Protocol: Read Calendar**

The `read_calendar` class handles user reques** (others/stage3): 

<spoken>Let me check your calendar for the next upcoming event.</spoken>pm. Would you like to know about anything else on your calendar?</spoken>

[
- **user: what's the weather like tomorrow
jane: High of about 47, low of 33, light ** (others/stage3): <spoken>Inulin is actually used quite a bit in food manufacturing, but there are a few reasons it hasn't replaced sugar outright. First, it's only abo
- **user: I want to know more about the students
jane: <spoken>For students: Nothing** (others/stage3): <spoken>Message sent. </spoken>
- **user: can you tell me what's on my to-do list
jane: <spoken>4 categories: the ur** (others/stage3): 

<spoken>Yes, the v3 pipeline still uses pending actions. The STAGE2_FOLLOWUP mechanism is active — handlers like todo list, calendar, and send messa
- **user: the Urgent stuff
jane: <spoken>Two things for your urgent list. First, Dea** (others/stage3): <spoken>Chieh, there's no v4 pipeline in the codebase. The latest is v3, which is the active one. There's no jane v4 directory or any references to a 
- **why did** (others/stage3): 

That message was cut off mid-sentence — I only received "why did" with no subject or verb. What were you trying to ask?
- **why do people always say that you'll call Ono broke up the Beatles** (others/stage3): It's one of rock's most persistent myths, but the reality is more layered:

**Why people blame her:**
- She started attending Beatles recording sessio
