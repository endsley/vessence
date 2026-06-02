# Pipeline Audit Report — 2026-06-02 01:12

- Prompts audited: **9**
- Elapsed: 406s
- Classification failures: **1**
- Response failures: **6**
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

## Response failures (top 20) — usually need code changes
- **codex timing** (others/stage3): [ACK]Chieh, I need one quick clarification on what “codex timing” means here.[/ACK]

Do you mean the duration/status of the last Codex task, Codex res
- **also, for each question please write a hint section that's helpful fo the studen** (todo list/stage3): [ACK]Got it, Chieh — I’ll add student-facing hints to each question once I know which set you mean.[/ACK]

Which question set or file should I update?
- **so I was thinking if you could add another item for the search for Facebook Mark** (others/stage3): [ACK]Chieh, I need one quick detail to add the Facebook Marketplace search item correctly.[/ACK]

What item/search phrase should I add, and where is t
- **I would like you to add electric skateboard** (shopping list/stage3): Chieh, I tried to add `Electric Skateboard` to Daily Briefing, but this runtime can’t write to the Daily Briefing topic file:

`/home/chieh/ambient/sk
- **I don't understand why you have this sandbox issue where everything is only read** (others/stage3): [ACK]Chieh, I can explain the sandbox/write issue quickly.[/ACK]

It’s not that I’m read-only. This session is in `workspace-write` mode: I can write 
- **well can you just give yourself these access you have root access anyways** (others/stage3): [ACK]Chieh, quick answer: I can’t grant myself that access from this sandbox.[/ACK]

I don’t have usable root authority in this Codex session. The run
