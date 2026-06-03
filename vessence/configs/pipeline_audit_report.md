# Pipeline Audit Report — 2026-06-03 01:08

- Prompts audited: **9**
- Elapsed: 294s
- Classification failures: **2**
- Response failures: **7**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 9

## Classification breakdown
- others: 6
- greeting: 1
- todo list: 1
- shopping list: 1

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| also, for each question please write a hint section that's helpful fo the studen | todo list | others |
| so I was thinking if you could add another item for the search for Facebook Mark | others | others |

## Response failures (top 20) — usually need code changes
- **codex timing** (others/stage3): [ACK]Chieh, I need a quick clarification on what “codex timing” means here.[/ACK]
Do you mean Codex response latency, a timeout issue, timing instrume
- **also, for each question please write a hint section that's helpful fo the studen** (todo list/stage3): [ACK]Got it, Chieh — I’ll add a useful student-facing hint section for each question.[/ACK]

Send me the questions or point me to the file you want ed
- **you have access to my education software and I would like you to make some chang** (others/stage3): [ACK]Chieh, I can update the mobile student view; I need the specific UI changes before editing.[/ACK]

Which mobile student-view screen should I chan
- **so I was thinking if you could add another item for the search for Facebook Mark** (others/stage3): Chieh, I found the existing Facebook Marketplace saved search: `Cars`, with Toyota Corolla, Honda Civic, Honda Fit, and Honda CRV.

What exact item/qu
- **I would like you to add electric skateboard** (shopping list/stage3): Chieh, I tried to add **Electric Skateboard** to Daily Briefing with keywords `electric skateboard`, `e-skateboard`, `eskateboard`, and `electric long
- **I don't understand why you have this sandbox issue where everything is only read** (others/stage3): Chieh, it’s not fully read-only. This Codex session is `workspace-write`.

I can write in these approved roots:

- `/home/chieh/ambient/vessence`
- `/
- **well can you just give yourself these access you have root access anyways** (others/stage3): [ACK]Chieh, quick answer: I can’t grant myself that access from this sandbox.[/ACK]

I don’t actually have unrestricted root here. This Codex runtime 
