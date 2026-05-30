# Pipeline Audit Report — 2026-05-30 01:14

- Prompts audited: **8**
- Elapsed: 285s
- Classification failures: **4**
- Response failures: **6**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 6
- stage2: 2

## Classification breakdown
- others: 3
- unclear: 2
- read messages: 1
- greeting: 1
- todo list: 1

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| I'm currently you are using cold text as the third brain right | read messages | read messages |
| also, for each question please write a hint section that's helpful fo the studen | todo list | others |
| I feel like the header is still based on web browser | unclear | others |
| I feel like the header for the red not the web view but the and | unclear | others |

## Response failures (top 20) — usually need code changes
- **I'm currently you are using cold text as the third brain right** (read messages/stage3): Yes, Chieh. This session is Jane running through the text standing-brain path with memory injected. If you meant “Claude Text” specifically, I’d check
- **codex timing** (others/stage3): [ACK]Chieh, I need one quick clarification on what “codex timing” refers to.[/ACK]
Do you mean Codex latency/runtime timing, timeout settings, or timi
- **also, for each question please write a hint section that's helpful fo the studen** (todo list/stage3): [ACK]Got it, Chieh — I’ll add helpful student-facing hints for each question; quick change.[/ACK]
I’ll keep the hints scaffolded: enough to guide the 
- **you have access to my education software and I would like you to make some chang** (others/stage3): [ACK]Chieh, I can make the mobile student-view UI changes; I just need the target changes before editing.[/ACK]

What exactly do you want changed in t
- **I feel like the header is still based on web browser** (unclear/stage2): <spoken>Sorry, I didn't understand that, can you say it again or clarify?</spoken>
- **I feel like the header for the red not the web view but the and** (unclear/stage2): <spoken>Sorry, I didn't understand that, can you say it again or clarify?</spoken>
