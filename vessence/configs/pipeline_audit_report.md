# Pipeline Audit Report — 2026-07-13 23:45

- Prompts audited: **6**
- Elapsed: 159s
- Classification failures: **4**
- Response failures: **5**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 5
- stage2: 1

## Classification breakdown
- others: 4
- todo list: 1
- unclear: 1

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| right now, you are using the same codex process for each prompt instead of spawn | others | others |
| use the source code as your guide | todo list | others |
| # Task: Self-heal android_crash_report: === VESSENCE CRASH REPORT ===

## Object | others | others |
| currently are you using codex or Claude | unclear | others |

## Response failures (top 20) — usually need code changes
- **right now, you are using the same codex process for each prompt instead of spawn** (others/stage3): You've hit your org's monthly spend limit · run /usage-credits to ask your admin for a higher limit
- **use the source code as your guide** (todo list/stage3): You've hit your org's monthly spend limit · run /usage-credits to ask your admin for a higher limit
- **currently, the waterlily site is web only meant for browsers on laptops and comp** (others/stage3): You've hit your org's monthly spend limit · run /usage-credits to ask your admin for a higher limit
- **# Task: Self-heal android_crash_report: === VESSENCE CRASH REPORT ===

## Object** (others/stage3): You've hit your org's monthly spend limit · run /usage-credits to ask your admin for a higher limit
- **currently are you using codex or Claude** (unclear/stage2): <spoken>Sorry, I didn't understand that, can you say it again or clarify?</spoken>
