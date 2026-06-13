# Pipeline Audit Report — 2026-06-13 01:12

- Prompts audited: **6**
- Elapsed: 1137s
- Classification failures: **2**
- Response failures: **3**
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
| use the source code as your guide | todo list | others |

## Response failures (top 20) — usually need code changes
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help pay it, but I need one detail first.[/ACK]
What are we paying, and where should I pay it? [[AWAITING:payment_details
- **right now, you are using the same codex process for each prompt instead of spawn** (others/stage3): [ACK]Chieh, I’ll verify the Stage 3 brain process behavior from the runtime code quickly.[/ACK]I found the likely path: Stage 3 escalates through `jan
- **use the source code as your guide** (todo list/stage3): [ACK]Got it, Chieh — I’ll ground this in the source code.[/ACK]
