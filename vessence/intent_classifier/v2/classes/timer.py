"""TIMER — set/cancel/list client-side Android timers (works offline)."""

CLASS_NAME = "TIMER"
NEEDS_LLM = True

EXAMPLES = [
    # SET — minutes
    "set a timer for 10 minutes",
    "set a 5 minute timer",
    "start a 15 minute timer",
    "timer for 20 minutes",
    "remind me in 10 minutes",
    "wake me up in 25 minutes",
    "give me a 30 minute timer",
    "can you set a 2 minute timer",
    "start a one minute timer",
    "set a timer for 45 minutes please",
    "let me know in 10 minutes",
    "ping me in 15 minutes",
    "alarm in 10 minutes",
    # SET — hours
    "remind me in an hour",
    "set a timer for 1 hour",
    "two hour timer",
    "wake me in 2 hours",
    "timer for an hour and a half",
    "set a 90 minute timer",
    "three hour timer",
    "remind me in half an hour",
    # SET — seconds
    "set a 30 second timer",
    "start a 10 second timer",
    "countdown 60 seconds",
    "timer for 45 seconds",
    # SET — labeled
    "set a 20 minute timer for the pasta",
    "timer for the oven 25 minutes",
    "remind me in 10 minutes to take the laundry out",
    "5 minute timer for eggs",
    "set a 15 minute pizza timer",
    "30 minute timer for the roast",
    # SET — colloquial / bare duration
    "time me for 5 minutes",
    "gimme 5 minutes",
    "give me 10 min",
    "countdown from 60",
    "countdown from 30 seconds",
    "tell me when 15 minutes is up",
    "tell me when 5 minutes is up",
    "buzz me in 10",
    "let me know when 20 minutes is up",
    "hit me back in 10 minutes",
    # CANCEL
    "cancel my timer",
    "stop the timer",
    "cancel the timer",
    "kill the timer",
    "stop my timer",
    "turn off the timer",
    "cancel all timers",
    "stop all timers",
    "never mind the timer",
    "forget the timer",
    "clear the timer",
    # LIST
    "what timers do I have",
    "show my timers",
    "list my timers",
    "any timers running",
    "do I have any timers",
    "how much time left on my timer",
    "how long on my timer",
    "check my timers",
    "what's on my timer",
    "how much time is left",
    "time remaining on timer",
    "what's the countdown at",
    "got anything ticking",
    "any countdown running",
    "whats my timer at",
]

CONTEXT = """\
The user wants to SET, CANCEL, or LIST a client-side timer on their phone.
Output exactly:
CLASSIFICATION: TIMER
ACTION: <set|cancel|list>
DURATION_MS: <integer milliseconds, only if ACTION=set, else 0>
LABEL: <short label if mentioned (e.g. "pasta", "oven"), else empty>"""
