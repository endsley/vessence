# Pipeline Audit Report — 2026-04-19 01:15

- Prompts audited: **30**
- Elapsed: 620s
- Classification failures: **21**
- Response failures: **26**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage2: 21
- stage3: 9

## Classification breakdown
- error: 30

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| well that is a problem can you fix that | error | others |
| I don't understand why there's a short circuit there should not be short circuit | error | others |
| no we designed a three-stage specifically for this reason so we can capture erro | error | others |
| <memory_verify priority="critical">
This turn's question depends on prior conver | error | others |
| and then at stage 2 describe to me what it's supposed to do | error | others |
| for stage 2 I wanted to say that I forgot what I wanted to say | error | others |
| so unstage 2 We Run The Quinn twice | error | others |
| what is the currently the latest Android version | error | others |
| can you tell my wife that I am texting Mary but she is not responding but I gues | error | send message |
| I will also make sure we put some money inside the stocks | error | others |
| I want you to delete phase one and phase two because I think they're finished | error | others |
| what about the third one | error | others |
| please read the last 3 turns from Android Jane, the "how are you" question took  | error | others |
| think deeply, I am having a lot of trouble with stage 3 right now, can you inves | error | others |
| <memory_verify priority="critical">
This turn's question depends on prior conver | error | others |
| <jane_architecture>
Authoritative snapshot of Jane's system. Use this before gue | error | others |
| <class_protocol name="todo_list">
These are runtime instructions for handling a  | error | others |
| <class_protocol name="end_conversation">
These are runtime instructions for hand | error | end conversation |
| <class_protocol name="music_play">
These are runtime instructions for handling a | error | end conversation |
| <class_protocol name="todo_list">
These are runtime instructions for handling a  | error | others |
| <class_protocol name="todo_list">
These are runtime instructions for handling a  | error | others |

## Response failures (top 20) — usually need code changes
- **well that is a problem can you fix that** (error/stage2): Sorry, could you say that again?
- **I don't understand why there's a short circuit there should not be short circuit** (error/stage2): Sorry, could you say that again?
- **no we designed a three-stage specifically for this reason so we can capture erro** (error/stage2): Sorry, could you say that again?
- **<memory_verify priority="critical">
This turn's question depends on prior conver** (error/stage2): Sorry, could you say that again?
- **and then at stage 2 describe to me what it's supposed to do** (error/stage2): Sorry, could you say that again?
- **<memory_verify priority="critical">
This turn's question depends on prior conver** (error/stage2): Sorry, could you say that again?
- **for stage 2 I wanted to say that I forgot what I wanted to say** (error/stage2): Sorry, could you say that again?
- **so unstage 2 We Run The Quinn twice** (error/stage2): Sorry, could you say that again?
- **what is the currently the latest Android version** (error/stage2): Sorry, could you say that again?
- **can you tell my wife that I am texting Mary but she is not responding but I gues** (error/stage2): Sorry, could you say that again?
- **I will also make sure we put some money inside the stocks** (error/stage2): Sorry, could you say that again?
- **I want you to delete phase one and phase two because I think they're finished** (error/stage3): There are "phases" in many different documents across the project — web automation, phone tools, tax accountant, vessence TODO, etc. Which "phase one 
- **what about the third one** (error/stage2): Sorry, could you say that again?
- **<class_protocol name="send_message">
These are runtime instructions for handling** (error/stage2): Sorry, could you say that again?
- **please read the last 3 turns from Android Jane, the "how are you" question took ** (error/stage2): Sorry, could you say that again?
- **<class_protocol name="end_conversation">
These are runtime instructions for hand** (error/stage2): Sorry, could you say that again?
- **<class_protocol name="greeting">
These are runtime instructions for handling a g** (error/stage2): Sorry, could you say that again?
- **think deeply, I am having a lot of trouble with stage 3 right now, can you inves** (error/stage3): 

[ACK]On it — let me dig into the Stage 3 pipeline and see what's broken.[/ACK]

Let me investigate the current state of Stage 3.ctor re-instantiated
- **<class_protocol name="weather">
These are runtime instructions for handling a we** (error/stage2): Sorry, could you say that again?
- **<memory_verify priority="critical">
This turn's question depends on prior conver** (error/stage2): Sorry, could you say that again?
