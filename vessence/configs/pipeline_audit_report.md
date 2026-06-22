# Pipeline Audit Report — 2026-06-22 01:08

- Prompts audited: **6**
- Elapsed: 1024s
- Classification failures: **3**
- Response failures: **4**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 6

## Classification breakdown
- others: 4
- web_automation: 1
- todo list: 1

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| help pay it | web_automation | others |
| right now, you are using the same codex process for each prompt instead of spawn | others | others |
| use the source code as your guide | todo list | others |

## Response failures (top 20) — usually need code changes
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help pay it, but I need one quick detail first.[/ACK]
Which bill or invoice do you mean, and where should it be paid from? I won’t s
- **right now, you are using the same codex process for each prompt instead of spawn** (others/stage3): [ACK]Chieh, I’ll verify the Stage 3 brain process behavior against the code quickly.[/ACK]I found the switch points: Stage 3 delegates through `jane_p
- **use the source code as your guide** (todo list/stage3): [ACK]Understood, Chieh — I’ll use the source code as the guide for repo work.[/ACK]
- **currently, the waterlily site is web only meant for browsers on laptops and comp** (others/stage3): `
