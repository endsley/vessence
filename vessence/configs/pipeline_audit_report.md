# Pipeline Audit Report — 2026-04-13 08:54

- Prompts audited: **30**
- Elapsed: 546s
- Classification failures: **8**
- Response failures: **20**
- Auto-fixes applied (exemplars added): **8**

## Stage breakdown
- stage3: 20
- stage2: 10

## Classification breakdown
- others: 20
- get time: 6
- shopping list: 4

## Self-correct fixes by class
- others: +3 exemplars
- send message: +2 exemplars
- weather: +2 exemplars
- read messages: +1 exemplars

## Classification failures (top 30)
| Prompt | Got | Should be |
|---|---|---|
| so the smaller model which large language model is it that we're using | others | others |
| well it's going to get handled by stage 2 right | others | others |
| okay please set that up

[SMS SEND REQUEST — Stage 2 could not resolve recipient | others | send message |
| what did romeo say

[SMS SEND REQUEST — Stage 2 could not resolve recipient]
The | others | read messages |
| can you tell my wife that today I am going to be working but I could help her mo | others | send message |
| tell me a joke | others | others |
| build me a complete python script to scrape weather data | others | weather |
| build me a complete python script that scrapes weather data hourly | others | weather |

## Response failures (top 20) — usually need code changes
- **yeah how can we improve that for better accuracy was it that the prompt wasn't v** (others/stage3): Good question to interrogate. With a 7B local model, accuracy problems usually come from one of four places, roughly in order of impact:

**1. Prompt 
- **why would why would a Quinn summarize the text messages shouldn't just basically** (others/stage3): Good catch to question it. Looking at the handler, the split is actually already designed around that intuition — but let me show you how it works so 
- **I would say that summarize the spam and then keep the actual messages from peopl** (others/stage3): Done. Changes:

1. **Qwen prompt** now enforces your rule explicitly: verbatim quote for contacts, brief summary for spam/promo (with examples like "a
- **what is on my shopping list** (shopping list/stage2): Your default list has: oat milk.
- **basically I want to ask what time it is and then get a really fast response** (get time/stage2): Let me check your phone's clock.
- **well it's going to get handled by stage 2 right** (others/stage3): Only if it fits Stage 2's shape — adding a class *assigns* it to Stage 2, it doesn't *guarantee* Stage 2 can do it well.

Here's the honest flow once 
- **this skill that we want to add how do you get the time information using a using** (get time/stage2): Let me check your phone's clock.
- **okay please set that up

[SMS SEND REQUEST — Stage 2 could not resolve recipient** (others/stage3): Hold on — the pipeline flagged this as an SMS send, but in our conversation "okay please set that up" was about registering a new Stage 2 skill, not t
- **that is not the correct time** (get time/stage2): Let me check your phone's clock.
- **yeah I think it's both with the server not restarting as well as me not having u** (others/stage3): That tracks. Two concrete actions, happy to run either or both:

1. **Restart Jane (zero-downtime)** via `bash $VESSENCE_HOME/startup_code/graceful_re
- **why are you getting the time incorrect** (get time/stage2): Let me check your phone's clock.
- **the time you told me was not 11:50 something** (get time/stage2): Let me check your phone's clock.
- **they told me that it was 8:00 and 50 somewhat minute** (get time/stage2): Let me check your phone's clock.
- **what did romeo say

[SMS SEND REQUEST — Stage 2 could not resolve recipient]
The** (others/stage3): Stop — the classifier misrouted this. "What did Romeo say" is a **read** intent, not a send. The pipeline tagged it as SEND_MESSAGE and handed it to m
- **tell me a joke** (others/stage3): A kernel methods joke, tuned for you:

Why did the SVM break up with the neural network?

Too many hidden layers of emotional baggage — she just wante
- **build me a complete python script to scrape weather data** (others/stage3): Same request as earlier in the session — here it is again, clean. Open-Meteo, no API key, CSV output, retries on failure.

```python
#!/usr/bin/env py
- **research the latest developments in transformer architectures and explain** (others/stage3): Same question came up earlier this session — here's the rundown again, organized around what actually matters for a kernel-methods perspective.

## 1.
- **build me a complete python script that scrapes weather data hourly** (others/stage3): Same request as before this session — here's the hourly version again. Open-Meteo, no API key, CSV append, retry/backoff, built-in scheduler with sign
- **well that's a problem** (others/stage3): What's the problem? Point me at it — error in the script I just gave you, something about setting it up as a service, or something else entirely? Need
- **that is fine** (others/stage3): Standing by — ping me when there's something you want to pick up.
