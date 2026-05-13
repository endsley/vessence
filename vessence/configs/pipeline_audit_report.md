# Pipeline Audit Report — 2026-05-13 01:06

- Prompts audited: **12**
- Elapsed: 97s
- Classification failures: **7**
- Response failures: **12**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 12

## Classification breakdown
- others: 9
- greeting: 1
- todo list: 1
- music play: 1

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| yes those articles and maybe just two days | others | others |
| it seems to me that you are no longing making any sounds when speech to text is  | others | others |
| can you look at the short-term memory to see if this whole thing is actually bei | others | others |
| __debug_inspect_update_short_term_memory | others | others |
| hey Jane, can you take a look at the ~/code/waterlily project for me | todo list | others |
| I'm currently are you able to see that the website Jane version is not working | others | others |
| can you mute my computer for me | music play | music play |

## Response failures (top 20) — usually need code changes
- **yes those articles and maybe just two days** (others/stage3): You've hit your limit · resets 10pm (America/New_York)
- **currently how does your short-term memory work** (others/stage3): You've hit your limit · resets 10pm (America/New_York)
- **how about** (greeting/stage3): You've hit your limit · resets 10pm (America/New_York)
- **it seems to me that you are no longing making any sounds when speech to text is ** (others/stage3): You've hit your limit · resets 10pm (America/New_York)
- **can you look at the short-term memory to see if this whole thing is actually bei** (others/stage3): You've hit your limit · resets 10pm (America/New_York)
- **__debug_inspect_update_short_term_memory** (others/stage3): You've hit your limit · resets 10pm (America/New_York)
- **hey Jane, can you take a look at the ~/code/waterlily project for me** (todo list/stage3): You've hit your limit · resets 10pm (America/New_York)
- **I'm currently are you able to see that the website Jane version is not working** (others/stage3): You've hit your limit · resets 10pm (America/New_York)
- **is stage 3 brain back up by now** (others/stage3): You've hit your limit · resets 10pm (America/New_York)
- **is the stage 3 brain working now** (others/stage3): You've hit your limit · resets 10pm (America/New_York)
- **can you mute my computer for me** (music play/stage3): You've hit your limit · resets 10pm (America/New_York)
- **ping** (others/stage3): You've hit your limit · resets 10pm (America/New_York)
