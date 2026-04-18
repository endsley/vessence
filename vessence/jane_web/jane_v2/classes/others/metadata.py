"""Others class — catch-all fallback. No handler → always escalates to Stage 3.

This class is special: it doesn't have a schema description block
injected into the classifier prompt (the prompt always offers
'others' as the catch-all value). Its few-shot examples teach the
classifier when to pick 'others' instead of a specific class.
"""

METADATA = {
    "name": "others",
    "priority": 100,           # run last when iterating; low in classifier prompt
    "description": (
        "[others]\n"
        "The \"else\" possibility — catch-all fallback when neither the "
        "primary nor alternative class fits. Choose 'others' (with Low "
        "confidence) when the message: (a) needs general reasoning "
        "(coding, creative, math, explanations); (b) asks a meta question "
        "about Jane's own architecture or code; (c) depends on memory of "
        "past conversations; (d) pivots to a topic with no registered "
        "handler; or (e) is too ambiguous to route confidently.\n\n"
        "A weak-but-real match to a specific class still beats 'others'. "
        "Reserve 'others' for cases where no specific handler is a "
        "defensible fit at all."
    ),
    "few_shot": [
        ("What playlists do I have?", "others:Low"),
        ("How many songs are in my workout playlist?", "others:Low"),
        ("Who is on the Billboard Hot 100?", "others:Low"),
        ("When was Bohemian Rhapsody released?", "others:Low"),
        ("Nice weather we're having, huh.", "others:Low"),
        ("Ugh, I hate this cold.", "others:Low"),
        ("The weather's been crazy lately.", "others:Low"),
        ("My grandpa used to predict weather by his knee.", "others:Low"),
        ("I'm going for a walk.", "others:Low"),
        ("Good morning!", "others:Low"),
        ("How does the weather fetch script work?", "others:Low"),
        ("how is our current weather report coded up?", "others:Low"),
    ],
    "ack": None,
    "escalate_ack": "Let me think about that…",
}
