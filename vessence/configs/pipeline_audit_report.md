# Pipeline Audit Report — 2026-04-20 01:15

- Prompts audited: **13**
- Elapsed: 269s
- Classification failures: **6**
- Response failures: **8**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 13

## Classification breakdown
- error: 13

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| <jane_architecture>
Authoritative snapshot of Jane's system. Use this before gue | error | weather |
| <jane_architecture>
Authoritative snapshot of Jane's system. Use this before gue | error | others |
| <jane_architecture>
Authoritative snapshot of Jane's system. Use this before gue | error | others |
| <class_protocol name="get_time">
These are runtime instructions for handling a g | error | others |
| <class_protocol name="todo_list">
These are runtime instructions for handling a  | error | others |
| <class_protocol name="todo_list">
These are runtime instructions for handling a  | error | others |

## Response failures (top 20) — usually need code changes
- **<jane_architecture>
Authoritative snapshot of Jane's system. Use this before gue** (error/stage3): 

Air quality is good right now — the AQI is 38, which is well in the safe range. PM2.5 is at 3.5, PM10 is 3.9, and ozone is at 78. Nothing to worry a
- **<jane_architecture>
Authoritative snapshot of Jane's system. Use this before gue** (error/stage3): 

[ACK]Let me pull up your full list.[/ACK]you've got two things: dealing with some important emails and handling the university credit card bills.

N
- **<memory_verify priority="critical">
This turn's question depends on prior conver** (error/stage3): 

Yep, that's everything on your personal lists. Nine items across urgent, home, and clinic. Students is clear right now.
- **<jane_architecture>
Authoritative snapshot of Jane's system. Use this before gue** (error/stage3): 

The cache was already provided in the escalation context, so I can answer directly.

You've got eight personal items across four categories. Two urg
- **<jane_architecture>
Authoritative snapshot of Jane's system. Use this before gue** (error/stage3): Here's your full list. Urgent: deal with some important emails and handle the university credit card bills. Nothing for students. Home has three: move
- **<class_protocol name="get_time">
These are runtime instructions for handling a g** (error/stage3): You've got one thing on the calendar today: setting up a room for a makeup exam, from 10 AM to 11 AM.
- **<class_protocol name="todo_list">
These are runtime instructions for handling a ** (error/stage3): 

I can't add categories directly — the todo list lives in your Google Doc, and categories are based on the headers in that doc. You'd need to add a n
- **<class_protocol name="todo_list">
These are runtime instructions for handling a ** (error/stage3): OK, I read the handler. Here's what happened: Stage 2 asked you "which category?" and set a follow-up waiting for your answer. But your reply — "what 
