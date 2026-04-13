"""Others class — catch-all fallback. No handler → always escalates to Stage 3.

This class is special: it doesn't have a schema description block
injected into the classifier prompt (the prompt always offers
'others' as the catch-all value). Its few-shot examples teach the
classifier when to pick 'others' instead of a specific class.
"""

METADATA = {
    "name": "others",
    "priority": 100,           # run last when iterating; low in classifier prompt
    "description": "",          # no schema block — 'others' is the fallback
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
