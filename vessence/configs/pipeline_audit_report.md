# Pipeline Audit Report — 2026-06-04 01:10

- Prompts audited: **7**
- Elapsed: 330s
- Classification failures: **1**
- Response failures: **7**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 7

## Classification breakdown
- others: 6
- shopping list: 1

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| so I was thinking if you could add another item for the search for Facebook Mark | others | others |

## Response failures (top 20) — usually need code changes
- **you have access to my education software and I would like you to make some chang** (others/stage3): [ACK]Chieh, I can work on the mobile student view; I just need the specific UI changes before editing.[/ACK]

Yes, I can make changes in `/home/chieh/
- **so I was thinking if you could add another item for the search for Facebook Mark** (others/stage3): Chieh, I checked the Daily Briefing topics: Facebook Marketplace is not already there.

I tried to add it, but this Codex sandbox cannot write to `/ho
- **I would like you to add electric skateboard** (shopping list/stage3): Chieh, I tried to add **Electric Skateboard** to your Daily Briefing topics, but this runtime can’t write to the briefing data file:

`/home/chieh/amb
- **I don't understand why you have this sandbox issue where everything is only read** (others/stage3): [ACK]Chieh, I can explain the sandbox behavior quickly.[/ACK]

It isn’t read-only overall. This session can write inside approved project roots, inclu
- **well can you just give yourself these access you have root access anyways** (others/stage3): No, not from this Codex runtime.

I checked: I’m running as `chieh`, not root. The file itself is owned by `chieh`, but `/home/chieh/ambient/skills` i
- **jane, currently, do you have write access to edit our education project?** (others/stage3): [ACK]Chieh, yes — quick answer from the current session context.[/ACK]

Yes. I currently have write access to edit the education project at `/home/chi
- **right now as a pofessor, look into a section and under the student tab, each stu** (others/stage3): Chieh, I checked the section student-tab template. The roster already has no `Detail` link; the student name is the only link to the same grades/detai
