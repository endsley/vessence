# Pipeline Audit Report — 2026-06-05 01:12

- Prompts audited: **19**
- Elapsed: 522s
- Classification failures: **5**
- Response failures: **15**
- Auto-fixes applied (exemplars added): **0**

## Stage breakdown
- stage3: 17
- stage2: 2

## Classification breakdown
- others: 13
- unclear: 2
- web_automation: 2
- shopping list: 1
- greeting: 1

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| well can you just give yourself these access you have root access anyways | others | others |
| I want to know if you have right access for the education project right now | unclear | others |
| please set up this payment for me on the local browser | web_automation | others |
| I just uploaded an image you can't see that? | unclear | others |
| help pay it | web_automation | others |

## Response failures (top 20) — usually need code changes
- **you have access to my education software and I would like you to make some chang** (others/stage3): [ACK]Chieh, I can update the mobile student view; I need the target screens and changes first.[/ACK]

Yes, I have writable access to `/home/chieh/code
- **so I was thinking if you could add another item for the search for Facebook Mark** (others/stage3): [ACK]Got it, Chieh — I can add another Facebook Marketplace search item once I know what to track.[/ACK]

What item should I add? Send the search keyw
- **I would like you to add electric skateboard** (shopping list/stage3): [ACK]Chieh, quick clarification before I add electric skateboard.[/ACK]
Do you want it added as a Daily Briefing topic, or somewhere else? [[AWAITING:
- **I don't understand why you have this sandbox issue where everything is only read** (others/stage3): [ACK]Chieh, I can clarify the sandbox behavior quickly.[/ACK]

It is not globally read-only. This Codex session can read broadly, but it can only writ
- **well can you just give yourself these access you have root access anyways** (others/stage3): [ACK]Chieh, quick answer: no, root doesn’t safely grant me those permissions.[/ACK]

I can’t just give myself external access. Local admin/root access
- **right now as a pofessor, look into a section and under the student tab, each stu** (others/stage3): [ACK]Chieh, I’ll remove that redundant student-row Detail link in the professor section view; this should be a quick code change.[/ACK]I found this is
- **should you restart yourself and maybe then you will have the right access** (others/stage3): [ACK]Chieh, quick answer: restarting probably won’t create new access by itself.[/ACK]

Not yet. A restart only helps if you just changed my environme
- **well if you were to restart yourself would you have right access then** (others/stage3): [ACK]Chieh, quick answer: restarting only helps if the runtime permissions were changed.[/ACK]

If you mean **write access**: I already have it for th
- **you do have right access for the Investments project** (others/stage3): Noted, Chieh. I’ll treat the Investments project as writable when you explicitly ask me to work there, while still avoiding secrets, local credentials
- **Do you have access to** (others/stage3): Chieh, I have access to the Vessence workspace, the approved project roots, and the tools listed in this session. What specific access are you asking 
- **I want to know if you have right access for the education project right now** (unclear/stage2): <spoken>Sorry, I didn't understand that, can you say it again or clarify?</spoken>
- **what was your result** (greeting/stage3): Chieh, I’m missing the prior result you’re referring to in this context. Which task or command do you mean? [[AWAITING:which_result_reference
- **please set up this payment for me on the local browser** (web_automation/stage3): [ACK]Chieh, I can help get the payment page ready, but I need the payment target first.[/ACK]

Send me the biller/site, amount, due date, and whether 
- **I just uploaded an image you can't see that?** (unclear/stage2): <spoken>Sorry, I didn't understand that, can you say it again or clarify?</spoken>
- **help pay it** (web_automation/stage3): [ACK]Chieh, I can help with the payment, but I need to know what “it” is first.[/ACK]

What are you trying to pay: a bill, invoice, toll, subscription
