# Pipeline Audit Report — 2026-05-05 01:05

- Prompts audited: **12**
- Elapsed: 990s
- Classification failures: **4**
- Response failures: **7**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 12

## Classification breakdown
- others: 8
- timer: 1
- greeting: 1
- todo list: 1
- music play: 1

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| I want them to periodically get the lead after some time | timer | others |
| yes those articles and maybe just two days | others | others |
| hey Jane, can you take a look at the ~/code/waterlily project for me | todo list | others |
| can you mute my computer for me | music play | music play |

## Response failures (top 20) — usually need code changes
- **I want them to periodically get the lead after some time** (timer/stage3): Can you clarify what you mean? Who is "them" and what does "getting the lead" look like in this context — are you talking about the Stage 2/3 pipeline
- **yes those articles and maybe just two days** (others/stage3): I'm picking up from where we left off, but I've lost the earlier context. I know there was an open loop about clarifying "them" and "get the lead" — y
- **it seems to me that you are no longing making any sounds when speech to text is ** (others/stage3): Based on my research, here's what I found about sounds in the STT flow:

**Android:** The wake word detection plays a beep via `ToneGenerator` in `Voi
- **__debug_inspect_update_short_term_memory** (others/stage3): Here's the full picture of the short-term memory update system:

## Short-Term Memory Architecture

### Write Path
1. **Trigger**: `jane_proxy.py:1589
- **hey Jane, can you take a look at the ~/code/waterlily project for me** (todo list/stage3): Got it. Here's the overview:

**Waterlily** is a local-first redevelopment of Kathia's Waterlily Wellness site. It's a hybrid setup:

1. **Static mirr
- **I'm currently are you able to see that the website Jane version is not working** (others/stage3): The server is up, the frontend loads, and the chat API works. Can you tell me more about what you're seeing? Specifically:

1. **What happens when you
- **is stage 3 brain back up by now** (others/stage3): The web service is up and running (active since yesterday, serving HTML fine), but the Stage 3 brain (Claude subprocess) appears to be busy — the chat
