# Pipeline Audit Report — 2026-06-06 01:10

- Prompts audited: **6**
- Elapsed: 132s
- Classification failures: **2**
- Response failures: **3**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 6

## Classification breakdown
- others: 3
- web_automation: 2
- greeting: 1

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| please set up this payment for me on the local browser | web_automation | others |
| help pay it | web_automation | others |

## Response failures (top 20) — usually need code changes
- **what was your result** (greeting/stage3): Chieh, I don’t have a prior result visible in this thread. Which result are you asking about? [[AWAITING:which_result
- **please set up this payment for me on the local browser** (web_automation/stage3): [ACK]Chieh, I can help with the payment setup, but I need one detail first.[/ACK]

Which site or bill is this for? I can walk you through it or help f
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help with the payment, but I need one quick detail first.[/ACK]

What are we paying: which bill, invoice, or person? If there’s a li
