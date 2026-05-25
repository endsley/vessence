# Pipeline Audit Report — 2026-05-25 01:14

- Prompts audited: **5**
- Elapsed: 405s
- Classification failures: **1**
- Response failures: **1**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 5

## Classification breakdown
- others: 4
- todo list: 1

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| hey Jane, can you take a look at the ~/code/waterlily project for me | todo list | others |

## Response failures (top 20) — usually need code changes
- **hey Jane, can you take a look at the ~/code/waterlily project for me** (todo list/stage3): Chieh, I did a read-only pass over `~/code/waterlily`.

It’s a hybrid Squarespace mirror plus FastAPI backend. Current dirty state is substantial: `ba
