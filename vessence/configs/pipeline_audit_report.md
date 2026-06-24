# Pipeline Audit Report — 2026-06-24 01:13

- Prompts audited: **6**
- Elapsed: 1040s
- Classification failures: **2**
- Response failures: **2**
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
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help pay it, but I need the bill details first.[/ACK]

Which bill or payment are we handling, and where should I open it? [[AWAITING
- **use the source code as your guide** (todo list/stage3): Understood, Chieh. I’ll treat the source code as the authority and verify behavior against it before making claims or changes.
