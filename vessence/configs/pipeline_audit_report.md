# Pipeline Audit Report — 2026-05-22 01:11

- Prompts audited: **11**
- Elapsed: 707s
- Classification failures: **3**
- Response failures: **7**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 11

## Classification breakdown
- others: 9
- greeting: 1
- todo list: 1

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| yes those articles and maybe just two days | others | others |
| __debug_inspect_update_short_term_memory | others | others |
| hey Jane, can you take a look at the ~/code/waterlily project for me | todo list | others |

## Response failures (top 20) — usually need code changes
- **yes those articles and maybe just two days** (others/stage3): [ACK]Chieh, I’m missing the specific article context, so this should be quick once you point me at it.[/ACK]

Which articles/topic did you mean, and s
- **currently how does your short-term memory work** (others/stage3): [ACK]Chieh, quick explanation of my current memory model.[/ACK]

My short-term memory is the active conversation context: recent turns, tool results, 
- **how about** (greeting/stage3): Chieh, what are you proposing? Give me the option or wording you want me to evaluate. [[AWAITING:what_option
- **it seems to me that you are no longing making any sounds when speech to text is ** (others/stage3): Chieh, I found the issue and patched it.

The STT “ready” callback is firing in diagnostics, so STT is turning back on. The cue was being played on An
- **__debug_inspect_update_short_term_memory** (others/stage3): Chieh, short-term memory update is active and writing.

Evidence:
- Write path: [jane_proxy.py](/home/chieh/ambient/vessence/jane_web/jane_proxy.py:16
- **hey Jane, can you take a look at the ~/code/waterlily project for me** (todo list/stage3): Chieh, I took a first pass through `/home/chieh/code/waterlily`.

It’s a hybrid project: mirrored Squarespace site plus a FastAPI backend for auth, ad
- **can you tell me if currently you are using cold decks or Claude cold as the base** (others/stage3): Chieh, Stage 3 is currently configured for **Codex/OpenAI**, not Claude.

Evidence:
- `/home/chieh/ambient/vessence-data/.env` has `JANE_BRAIN=codex`

