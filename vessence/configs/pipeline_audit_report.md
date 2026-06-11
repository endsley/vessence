# Pipeline Audit Report — 2026-06-11 01:13

- Prompts audited: **6**
- Elapsed: 1188s
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
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help, but I need to know what we’re paying first.[/ACK]

What is “it”: a bill, invoice, ticket, subscription, or something else? Sen
- **right now, you are using the same codex process for each prompt instead of spawn** (others/stage3): [ACK]Chieh, I’ll verify the current Stage 3 brain launch path quickly.[/ACK]I found the relevant implementation: Stage 3 has a dedicated `standing_cod
- **currently, the waterlily site is web only meant for browsers on laptops and comp** (others/stage3): [ACK]Chieh, I’ll inspect the Waterlily and education projects first, then adapt the Waterlily UI for mobile across the site; this will take a bit.[/AC
