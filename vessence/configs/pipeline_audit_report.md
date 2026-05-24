# Pipeline Audit Report — 2026-05-24 01:13

- Prompts audited: **5**
- Elapsed: 488s
- Classification failures: **1**
- Response failures: **2**
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
- **hey Jane, can you take a look at the ~/code/waterlily project for me** (todo list/stage3): Chieh, I looked through `~/code/waterlily`. No edits made.

Top-level read: it’s a Squarespace static mirror plus a FastAPI backend for auth, admin/st
- **can you tell me if currently you are using cold decks or Claude cold as the base** (others/stage3): Chieh, it’s Codex, not Claude Code.

Evidence I checked:
- Runtime config: `/home/chieh/ambient/vessence-data/.env` has `JANE_BRAIN=codex`.
- Model se
