"""END_CONVERSATION — cancel/stop/dismiss after a prior proposal."""

CLASS_NAME = "END_CONVERSATION"
NEEDS_LLM = False

EXAMPLES = [
    "cancel", "stop", "never mind", "forget it", "don't send it",
    "nope", "no thanks", "not now", "skip it",
    "be quiet", "silence", "shush", "enough",
    "leave me alone", "that's all", "that's it",
    "we're done", "i'm done", "drop it",
    "bye", "goodbye", "see you later", "talk later",
    "ok thanks", "thanks", "thank you", "dismissed",
    "go to sleep", "nevermind", "abort",
    "don't bother", "forget about it", "let it go",
    "stop that", "cancel that", "don't do it",
    "no don't", "actually no", "actually never mind",
    "hold on cancel that", "wait no",
    "thanks that's all", "that will do", "all good",
    "that's everything", "i'm good", "we're good",
    "cool thanks", "perfect thanks", "great thanks",
    "no need", "don't worry about it",
    "stop right there", "pause", "hold on",
    "later", "talk to you later", "catch you later",
    # Night farewells — these are goodbyes not greetings
    "good night", "good night jane", "goodnight", "goodnight jane",
    "have a good night", "sleep well", "good night everyone",
    "night night", "nighty night", "sweet dreams",
    # End of session
    "i am done for the night", "done for tonight", "done for the day",
    "finishing up for the night", "wrapping up for the day",
    "calling it a night", "calling it a day", "heading to bed",
    "going to sleep now", "off to bed", "time to sleep",
    "i am heading out", "signing off", "logging off",
]

CONTEXT = None
