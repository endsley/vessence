# Pipeline Audit Report — 2026-06-14 01:12

- Prompts audited: **6**
- Elapsed: 1160s
- Classification failures: **2**
- Response failures: **1**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 4
- ?: 1

## Classification breakdown
- others: 3
- web_automation: 1
- todo list: 1

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| help pay it | web_automation | others |
| you have access to the water lily Wellness project right | others | others |

## Response failures (top 20) — usually need code changes
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help with the payment, but I need one quick detail.[/ACK]

What are we paying: which bill or service? Don’t send card numbers or pas
