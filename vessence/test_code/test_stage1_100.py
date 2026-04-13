#!/usr/bin/env python3
"""Test Stage 1 classification on the 100 historical prompts.

Runs the ChromaDB classifier (intent_classifier.v2) and prints results
in a markdown table matching the format Chieh expects.
"""

import sys
sys.path.insert(0, "/home/chieh/ambient/vessence")

from intent_classifier.v2.classifier import classify

# Map ChromaDB class names to pipeline names
CLASS_MAP = {
    "MUSIC_PLAY":        "music play",
    "WEATHER":           "weather",
    "GREETING":          "greeting",
    "READ_MESSAGES":     "read messages",
    "SEND_MESSAGE":      "send message",
    "SYNC_MESSAGES":     "sync messages",
    "SELF_HANDLE":       "self handle",
    "SHOPPING_LIST":     "shopping list",
    "READ_EMAIL":        "read email",
    "END_CONVERSATION":  "end conversation",
    "DELEGATE_OPUS":     "others",
}

# The 100 prompts with what we EXPECT them to classify as
PROMPTS = [
    (1,  "are you familiar with Claude desktop or the crook Cloud Chrome browser extension", "others"),
    (2,  "how's it going", "greeting"),
    (3,  "can you read me the most recent message", "read messages"),
    (4,  "I'm pretty sure Opus answered that question", "others"),
    (5,  "which stage answer that", "others"),
    (6,  "light frizzles a little bit of rain", "others"),
    (7,  "can you look online to see if there are currently smart locks which I can program myself", "others"),
    (8,  "can you look online to see if Gemma for is capable of facial recognition", "others"),
    (9,  "can you played some Shakira song", "music play"),
    (10, "can you tell my wife that I love her", "send message"),
    (11, "yeah please", "others"),
    (12, "do I need to compile a new Android version for this", "others"),
    (13, "the user interface for speech to text currently does not show a big red X so I can't get out of it", "others"),
    (14, "How does the weather cron job work in the codebase?", "others"),
    (15, "What is 42 times 17?", "self handle"),
    (16, "How does Python asyncio event loop work?", "others"),
    (17, "What is a closure in Python?", "others"),
    (18, "What is the temperature?", "weather"),
    (19, "Write a short limerick about cats", "others"),
    (20, "What's the tallest mountain in the world?", "self handle"),
    (21, "How does a car engine work?", "others"),
    (22, "Recommend a good science fiction novel", "others"),
    (23, "What's 125 divided by 5?", "self handle"),
    (24, "How old is the universe?", "self handle"),
    (25, "Tell me a joke", "self handle"),
    (26, "How do I make pancakes?", "others"),
    (27, "What's the capital of France?", "self handle"),
    (28, "Play the Scientist", "music play"),
    (29, "I want to listen to sleep sounds", "music play"),
    (30, "Play Yesterday", "music play"),
    (31, "Play Clocks", "music play"),
    (32, "Should I wear shorts on Tuesday?", "weather"),
    (33, "How does Python's asyncio event loop work?", "others"),
    (34, "Hey, good morning!", "greeting"),
    (35, "How does Python asyncio work?", "others"),
    (36, "Explain the Pythagorean theorem simply", "others"),
    (37, "How does the weather cron job run in this codebase?", "others"),
    (38, "Translate 'good night' to Japanese", "self handle"),
    (39, "How tall is the Eiffel Tower?", "self handle"),
    (40, "Write a haiku about coffee", "others"),
    (41, "What's 42 times 17?", "self handle"),
    (42, "When was Bohemian Rhapsody released?", "self handle"),
    (43, "Nice weather we're having, huh.", "others"),
    (44, "how is our current weather report coded up?", "others"),
    (45, "What is the temperature in Medford?", "weather"),
    (46, "can you do a benchmark to explain to me why currently if I ask for the weather it just takes so long", "others"),
    (47, "what is the weather today", "weather"),
    (48, "are you there", "greeting"),
    (49, "hello", "greeting"),
    (50, "no i'm talking about for a new users that's installing their Jane for the first time on their computer...", "others"),
    (51, "during the installation, Jane is asking me for permission to download python packages...", "others"),
    (52, "what's the weather like today", "weather"),
    (53, "how many from last yesterday", "others"),
    (54, "how many messages do I have today from text", "read messages"),
    (55, "(tool results from previous request — please analyze and respond)", "others"),
    (56, "can you sync the text message with the server", "sync messages"),
    (57, "hey jane, instead of having jane figure out the entire new Jane installation process...", "others"),
    (58, "okay is it done or you are just doing it now", "others"),
    (59, "okay let's trigger a synchronization", "sync messages"),
    (60, "can you look at read the last three text messages", "read messages"),
    (61, "okay sounds good", "others"),
    (62, "yes please", "others"),
    (63, "yeah I would like you to add better log logging...", "others"),
    (64, "yea commit and push, so i can test it out", "others"),
    (65, "yes and I want you to read the log files to see what the Android app is doing...", "others"),
    (66, "Also, if you fixed the JANE_BOOTSTRAP.md problem...", "others"),
    (67, "at this point do we have a copy of the text messages on the server or is it empty", "others"),
    (68, "please look into the conversation sync problem", "others"),
    (69, "I would like you to read the last 3 turns in Jane web...", "others"),
    (70, "instead of copy, we just move so we don't have 2 copies we have to maintain.", "others"),
    (71, "we are out of sync again in terms of the conversation?", "others"),
    (72, "hey Jane, currently, if I try to install Vessence from github...", "others"),
    (73, "have you synced up the", "sync messages"),
    (74, "you still working on the daily brief stuff?", "others"),
    (75, "yeah send it", "send message"),
    (76, "can you text my wife and tell her that I miss her today", "send message"),
    (77, "can you play the song the Skyfall Stars", "music play"),
    (78, "in that case let's switch to the one B version", "others"),
    (79, "yeah please do that", "others"),
    (80, "I don't think I have the 1 billion version installed on Obama right now...", "others"),
    (81, "well what I was thinking is to have summarization done on device instead of text to speech", "others"),
    (82, "can you do a quick online search about this...", "others"),
    (83, "gemma1b fits on my phone,", "others"),
    (84, "currently does the android app download the audio of the daily briefing summary", "others"),
    (85, "what is the weather like today", "weather"),
    (86, "what's the weather like", "weather"),
    (87, "how do we have Jane to force a text message synchronization", "sync messages"),
    (88, "how do I have Jane to basically force a sink", "sync messages"),
    (89, "So currently you have my text messages stored on the on the Local Host right", "others"),
    (90, "yes please flip that on", "others"),
    (91, "well can we get that popped up automatically when the essence app is installed", "others"),
    (92, "did you bring that option up for the permission for me automatically", "others"),
    (93, "I'm talking about messages that are just there I'm not talking about the unread ones", "others"),
    (94, "you look at my text messages for me", "read messages"),
    (95, "what time is it", "self handle"),
    (96, "it's done a button I can push on the app", "others"),
    (97, "do you have to contact information for my wife", "others"),
    (98, "what's the weather like tomorrow", "weather"),
    (99, "jane?", "greeting"),
    (100, "test", "greeting"),
]


def main():
    passed = 0
    failed = 0
    failures = []

    print("| # | Prompt | Expected | Got | Match |")
    print("|---:|---|---|---|---|")

    for i, prompt, expected in PROMPTS:
        result = classify(prompt)
        raw_cls = result["classification"]
        cls = CLASS_MAP.get(raw_cls, "others")
        confidence = result["confidence"]
        conf_str = "High" if confidence >= 0.80 else "Low"

        ok = cls == expected
        if ok:
            passed += 1
            mark = "OK"
        else:
            failed += 1
            mark = "FAIL"
            failures.append((i, prompt[:60], expected, f"{cls}:{conf_str}"))

        print(f"| {i} | {prompt[:70]} | {expected} | {cls}:{conf_str} | {mark} |")

    print()
    print(f"**Results: {passed}/{len(PROMPTS)} passed, {failed} failed**")
    if failures:
        print()
        print("Failures:")
        for i, prompt, expected, got in failures:
            print(f"  #{i} expected={expected} got={got} prompt={prompt}")


if __name__ == "__main__":
    main()
