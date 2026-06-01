# Pipeline Audit Report — 2026-06-01 01:18

- Prompts audited: **5**
- Elapsed: 278s
- Classification failures: **1**
- Response failures: **3**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 5

## Classification breakdown
- others: 3
- greeting: 1
- todo list: 1

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| also, for each question please write a hint section that's helpful fo the studen | todo list | others |

## Response failures (top 20) — usually need code changes
- **codex timing** (others/stage3): Chieh, do you mean Codex response latency, or do you want me to time a specific command/task? [[AWAITING:codex_timing_scope
- **also, for each question please write a hint section that's helpful fo the studen** (todo list/stage3): Got it, Chieh. I’ll add a helpful, student-facing `Hint` section for each question that nudges the solving approach without giving away the answer.
- **you have access to my education software and I would like you to make some chang** (others/stage3): [ACK]Chieh, I can make those mobile student UI changes once you give me the exact screens and desired behavior.[/ACK]

Send me the specific changes: w
