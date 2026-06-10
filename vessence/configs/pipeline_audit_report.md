# Pipeline Audit Report — 2026-06-10 01:13

- Prompts audited: **6**
- Elapsed: 976s
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
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help with the payment once I know which bill this is.[/ACK]
What are we paying: a bill, invoice, credit card, tuition, or something 
- **right now, you are using the same codex process for each prompt instead of spawn** (others/stage3): [ACK]Chieh, I’ll verify the Stage 3 brain process model from the runtime code quickly.[/ACK]I found two relevant paths: the v2 Stage 3 wrapper delegat
- **currently, the waterlily site is web only meant for browsers on laptops and comp** (others/stage3): [ACK]Chieh, I’ll compare the education project’s mobile patterns against Waterlily and then implement responsive mobile UIs across the site; this will
