# Pipeline Audit Report — 2026-06-19 01:11

- Prompts audited: **7**
- Elapsed: 884s
- Classification failures: **4**
- Response failures: **5**
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

What bill or invoice are you trying to pay? Tell me the site/service and amount 
- **right now, you are using the same codex process for each prompt instead of spawn** (others/stage3): [ACK]Chieh, quick answer: yes, you’re asking about the Stage 3 brain process model.[/ACK]

Yes. Right now this is the standing-brain mode: the web/And
- **use the source code as your guide** (todo list/stage3): Understood, Chieh. I’ll treat the source code as authoritative and verify against it before making claims or changes.
- **currently, the waterlily site is web only meant for browsers on laptops and comp** (others/stage3): [ACK]Chieh, I’ll audit both projects’ mobile patterns and patch Waterlily’s responsive UI end to end; this will take a while.[/ACK]I’m going to locate
- **how about the one before that** (end conversation/stage3): Chieh, I don’t have enough context for “the one before that.” Which message do you want me to use? [[AWAITING:which_message
