# Pipeline Audit Report — 2026-06-25 01:09

- Prompts audited: **6**
- Elapsed: 1046s
- Classification failures: **3**
- Response failures: **1**
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
| you have access to the water lily Wellness project right | others | others |
| use the source code as your guide | todo list | others |

## Response failures (top 20) — usually need code changes
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help pay it, but I need to identify the bill first.[/ACK]

Which bill or site do you mean? Send the bill name, company, or a screens
