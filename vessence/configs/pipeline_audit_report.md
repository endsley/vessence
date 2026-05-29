# Pipeline Audit Report — 2026-05-29 01:14

- Prompts audited: **5**
- Elapsed: 287s
- Classification failures: **3**
- Response failures: **4**
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
| for the module span_A.q2, I would like you to not mention the augmented matrix s | others | others |
| also, for each question please write a hint section that's helpful fo the studen | todo list | others |

## Response failures (top 20) — usually need code changes
- **I'm currently you are using cold text as the third brain right** (read messages/stage3): Yes, Chieh. If “cold text” means Codex, then right now I’m Jane running through the Codex/standing-brain path, with Vessence memory and instructions l
- **codex timing** (others/stage3): [ACK]Chieh, I need one clarification on what “codex timing” refers to.[/ACK]

Do you mean Codex response latency, a timing issue in the Vessence Codex
- **for the module span_A.q2, I would like you to not mention the augmented matrix s** (others/stage3): Chieh, I verified `span_A.q2`: the visible prompt already omits “augmented,” “Equivalently,” `A \alpha`, and the augmented matrix display. The remaini
- **also, for each question please write a hint section that's helpful fo the studen** (todo list/stage3): Got it, Chieh. Send me the questions or the file path, and I’ll add a concise `Hint` section under each one that guides the approach without giving aw
