# Pipeline Audit Report — 2026-05-07 01:06

- Prompts audited: **13**
- Elapsed: 843s
- Classification failures: **8**
- Response failures: **8**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 13

## Classification breakdown
- others: 9
- timer: 1
- greeting: 1
- todo list: 1
- music play: 1

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| I want them to periodically get the lead after some time | timer | others |
| yes those articles and maybe just two days | others | others |
| it seems to me that you are no longing making any sounds when speech to text is  | others | others |
| __debug_inspect_update_short_term_memory | others | others |
| hey Jane, can you take a look at the ~/code/waterlily project for me | todo list | others |
| I'm currently are you able to see that the website Jane version is not working | others | others |
| can you mute my computer for me | music play | music play |
| ping | others | others |

## Response failures (top 20) — usually need code changes
- **I want them to periodically get the lead after some time** (timer/stage3): Hey Chieh — I'm not sure what "them" and "the lead" refer to here. Can you give me a bit more context? Are you talking about a pipeline stage, a servi
- **yes those articles and maybe just two days** (others/stage3): I don't have context for what "those articles" refers to — this might be carrying over from a conversation I don't have access to. Can you fill me in 
- **currently how does your short-term memory work** (others/stage3): Here's how short-term memory works right now:

**Write path** — after every conversation turn (Stage 3), `ConversationManager.update_short_term_memory
- **how about** (greeting/stage3): Hey Chieh, what's up? What are you thinking about?
- **it seems to me that you are no longing making any sounds when speech to text is ** (others/stage3): Based on the code, here's what's happening with STT sounds:

**On Android**, there are two sound feedback points:
1. **Wake word detection** — plays a
- **__debug_inspect_update_short_term_memory** (others/stage3): Here's the full short-term memory update architecture:

## Write Path

**Trigger:** `jane_proxy.py:1592` calls `conv_manager.update_short_term_memory(
- **hey Jane, can you take a look at the ~/code/waterlily project for me** (todo list/stage3): Here's the overview of `~/code/waterlily`:

**Waterlily** is a local-first static mirror of Kathia's Squarespace wellness site (waterlilywellness.com)
- **is the stage 3 brain working now** (others/stage3): The web server is up, but the `/api/jane/live` health check timed out again. The brain process (PID 114335) is alive at 19.7% CPU — spawned at 01:19 t
