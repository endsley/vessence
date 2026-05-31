# Pipeline Audit Report — 2026-05-31 01:15

- Prompts audited: **8**
- Elapsed: 271s
- Classification failures: **4**
- Response failures: **5**
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
| I'm currently you are using cold text as the third brain right | read messages | others |
| also, for each question please write a hint section that's helpful fo the studen | todo list | others |
| I feel like the header is still based on web browser | unclear | others |
| I feel like the header for the red not the web view but the and | unclear | others |

## Response failures (top 20) — usually need code changes
- **codex timing** (others/stage3): [ACK]Chieh, I need one quick clarification on what “codex timing” means.[/ACK]

Do you mean timing a Codex task, checking Codex latency/performance, o
- **also, for each question please write a hint section that's helpful fo the studen** (todo list/stage3): [ACK]Chieh, yes — I’ll add student-facing hint sections once I know which question set.[/ACK]

Send me the questions or the file path, and I’ll add a 
- **you have access to my education software and I would like you to make some chang** (others/stage3): [ACK]Chieh, I can work on the mobile student view; I need the specific UI changes before editing.[/ACK]

What should change in the mobile student UI? 
- **I feel like the header is still based on web browser** (unclear/stage2): <spoken>Sorry, I didn't understand that, can you say it again or clarify?</spoken>
- **I feel like the header for the red not the web view but the and** (unclear/stage2): <spoken>Sorry, I didn't understand that, can you say it again or clarify?</spoken>
