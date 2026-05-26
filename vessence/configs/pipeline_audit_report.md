# Pipeline Audit Report — 2026-05-26 01:22

- Prompts audited: **5**
- Elapsed: 438s
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
- **can you tell me if currently you are using cold decks or Claude cold as the base** (others/stage3): Chieh, current base Stage 3 brain is **Codex/OpenAI**, not Claude Code.

Evidence:
- `/home/chieh/ambient/vessence-data/.env` has `JANE_BRAIN=codex`
-
