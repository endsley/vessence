# Pipeline Audit Report — 2026-05-28 01:16

- Prompts audited: **5**
- Elapsed: 331s
- Classification failures: **2**
- Response failures: **3**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 5

## Classification breakdown
- others: 2
- read messages: 1
- greeting: 1
- todo list: 1

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| I'm currently you are using cold text as the third brain right | read messages | read messages |
| also, for each question please write a hint section that's helpful fo the studen | todo list | others |

## Response failures (top 20) — usually need code changes
- **I'm currently you are using cold text as the third brain right** (read messages/stage3): Yes, Chieh. This is Jane running through the Codex/standing-brain path, with memory/context injected. If by “cold text” you meant “Codex,” then yes.
- **codex timing** (others/stage3): [ACK]Chieh, I need one quick clarification on what “codex timing” refers to.[/ACK]

Do you mean Codex response latency, a timeout setting, task durati
- **also, for each question please write a hint section that's helpful fo the studen** (todo list/stage3): [ACK]Got it, Chieh — I can add hint sections, but I need the target questions/file first.[/ACK]

Send me the questions or point me to the file, and I’
