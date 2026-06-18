# Pipeline Audit Report — 2026-06-18 01:09

- Prompts audited: **7**
- Elapsed: 1155s
- Classification failures: **4**
- Response failures: **4**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 7

## Classification breakdown
- others: 4
- web_automation: 1
- todo list: 1
- end conversation: 1

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| help pay it | web_automation | others |
| right now, you are using the same codex process for each prompt instead of spawn | others | others |
| use the source code as your guide | todo list | others |
| how about the one before that | end conversation | end conversation |

## Response failures (top 20) — usually need code changes
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help, but I need to know what “it” is first.[/ACK]

What are we paying: a utility bill, City Hall bill, rent/property item, or somet
- **right now, you are using the same codex process for each prompt instead of spawn** (others/stage3): [ACK]Chieh, I’ll verify the current stage 3 brain process behavior from the runtime code quickly.[/ACK]I found the routing switch: stage 3 uses the st
- **use the source code as your guide** (todo list/stage3): [ACK]Got it, Chieh — I’ll treat the source code as the primary reference.[/ACK]

Understood. For code/runtime questions, I’ll read the relevant files 
- **how about the one before that** (end conversation/stage3): [ACK]Chieh, I need one clarification on which previous option you mean.[/ACK]
Do you mean the previous draft wording? I don’t have enough context here
