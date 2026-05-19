# Pipeline Audit Report — 2026-05-19 01:14

- Prompts audited: **7**
- Elapsed: 1169s
- Classification failures: **1**
- Response failures: **3**
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
| hey Jane, can you take a look at the ~/code/waterlily project for me | todo list | others |

## Response failures (top 20) — usually need code changes
- **yes those articles and maybe just two days** (others/stage3): I don't have context from the previous conversation — what articles are you referring to, and what's the two-day timeframe for? Give me a quick recap 
- **currently how does your short-term memory work** (others/stage3): Here's how short-term memory works right now:

**Storage**: ChromaDB collection called `short_term_memory`, stored at `$VESSENCE_DATA_HOME/memory/v1/v
- **hey Jane, can you take a look at the ~/code/waterlily project for me** (todo list/stage3): Here's what I see:

**Waterlily** is a local-first redevelopment of Kathia's Waterlily Wellness website. It's built as a static mirror of the live Squ
