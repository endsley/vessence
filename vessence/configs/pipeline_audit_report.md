# Pipeline Audit Report — 2026-06-17 01:08

- Prompts audited: **6**
- Elapsed: 1099s
- Classification failures: **4**
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
| you have access to the water lily Wellness project right | others | others |
| right now, you are using the same codex process for each prompt instead of spawn | others | others |
| use the source code as your guide | todo list | others |

## Response failures (top 20) — usually need code changes
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help with the payment, but I need one quick detail first.[/ACK]
What are you trying to pay? Send the bill name, site, or a screensho
- **right now, you are using the same codex process for each prompt instead of spawn** (others/stage3): [ACK]Chieh, I’ll verify the current Stage 3 brain code path rather than guessing; this should be a quick check.[/ACK]I found the relevant Stage 3 rout
- **use the source code as your guide** (todo list/stage3): Understood, Chieh. I’ll treat the source code as the authority and verify behavior there before making claims or edits.
