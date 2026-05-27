# Pipeline Audit Report — 2026-05-27 01:17

- Prompts audited: **10**
- Elapsed: 1033s
- Classification failures: **3**
- Response failures: **2**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 10

## Classification breakdown
- others: 6
- todo list: 2
- read messages: 1
- greeting: 1

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| hey Jane, can you take a look at the ~/code/waterlily project for me | todo list | others |
| I'm currently you are using cold text as the third brain right | read messages | read messages |
| also, for each question please write a hint section that's helpful fo the studen | todo list | others |

## Response failures (top 20) — usually need code changes
- **codex timing** (others/stage3): [ACK]Chieh, I need one clarification on what Codex timing you mean.[/ACK]

Do you mean Codex response latency, timing for a code task, or a timing/log
- **also, for each question please write a hint section that's helpful fo the studen** (todo list/stage3): [ACK]Chieh, I can add hint sections, but I need the target questions or file first.[/ACK]

Point me to the assignment/file, or paste the questions her
