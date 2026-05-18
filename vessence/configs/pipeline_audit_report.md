# Pipeline Audit Report — 2026-05-18 01:11

- Prompts audited: **7**
- Elapsed: 907s
- Classification failures: **3**
- Response failures: **5**
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
| can you look at the short-term memory to see if this whole thing is actually bei | others | others |
| __debug_inspect_update_short_term_memory | others | others |
| hey Jane, can you take a look at the ~/code/waterlily project for me | todo list | others |

## Response failures (top 20) — usually need code changes
- **yes those articles and maybe just two days** (others/stage3): I don't have context from what came before — looks like this is continuing a prior conversation that I can't see. What articles are you referring to, 
- **currently how does your short-term memory work** (others/stage3): Here's how short-term memory works right now:

**Storage:** ChromaDB collection `short_term_memory` at `vessence-data/vector_db/short_term_memory/`. D
- **it seems to me that you are no longing making any sounds when speech to text is ** (others/stage3): Based on the code, there are two different situations depending on whether you're talking about **Android** or **web**:

**Android** — has beep sounds
- **can you look at the short-term memory to see if this whole thing is actually bei** (others/stage3): Here's the full diagnosis:

**The hook is wired and firing** — `context_summary_hook.sh` pipes stdin to `claude_stop_short_term.py` on every session s
- **__debug_inspect_update_short_term_memory** (others/stage3): Here's the full picture of the short-term memory update pipeline:

### Flow

1. **Trigger**: After every Stage 3 response in `jane_proxy.py:1628`, a d
