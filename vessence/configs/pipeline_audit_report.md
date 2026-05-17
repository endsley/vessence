# Pipeline Audit Report — 2026-05-17 01:06

- Prompts audited: **7**
- Elapsed: 81s
- Classification failures: **4**
- Response failures: **7**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 7

## Classification breakdown
- others: 5
- greeting: 1
- todo list: 1

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| yes those articles and maybe just two days | others | others |
| can you look at the short-term memory to see if this whole thing is actually bei | others | others |
| __debug_inspect_update_short_term_memory | others | others |
| hey Jane, can you take a look at the ~/code/waterlily project for me | todo list | others |

## Response failures (top 20) — usually need code changes
- **yes those articles and maybe just two days** (others/stage3): You've hit your limit · resets 2am (America/New_York)
- **currently how does your short-term memory work** (others/stage3): You've hit your limit · resets 2am (America/New_York)
- **how about** (greeting/stage3): You've hit your limit · resets 2am (America/New_York)
- **it seems to me that you are no longing making any sounds when speech to text is ** (others/stage3): You've hit your limit · resets 2am (America/New_York)
- **can you look at the short-term memory to see if this whole thing is actually bei** (others/stage3): You've hit your limit · resets 2am (America/New_York)
- **__debug_inspect_update_short_term_memory** (others/stage3): You've hit your limit · resets 2am (America/New_York)
- **hey Jane, can you take a look at the ~/code/waterlily project for me** (todo list/stage3): You've hit your limit · resets 2am (America/New_York)
