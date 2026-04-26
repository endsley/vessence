"""Unclear class — STT noise / fragmentary transcription.

No handler — the v3 pipeline short-circuits with a canned "say that again?"
reply. Folded into the classifier's possible outputs so a single qwen call
decides routing AND unclear-detection at once, instead of paying for a
separate is_unclear pass after the classifier has already decided.
"""

METADATA = {
    "name": "unclear",
    "priority": 95,
    "description": (
        "[unclear]\n"
        "Pick UNCLEAR only when the user's message AS A WHOLE has no "
        "recoverable intent. Specifically:\n"
        "  - Cut off mid-phrase or ends with a preposition that clearly "
        "has more to come (\"what's the weather in\", \"turn on the\", "
        "\"can you please\")\n"
        "  - Word-soup with no verb or coherent subject "
        "(\"apple meeting tomorrow blue\", \"I got to seaweed\", "
        "\"origin\")\n"
        "  - Stitches contradictory fragments with no coherent intent "
        "(\"play uh no wait the other thing um actually\")\n"
        "  - Background speech bleeding into the transcript\n\n"
        "Do NOT pick unclear just because one word looks mistranscribed "
        "— if the rest of the sentence has a clear verb + object "
        "(\"who is the next patient\", \"what's the clinic schedule like X\"), "
        "pick the matching content class even if a name or noun looks "
        "wrong. Do NOT return 'unclear' for natural short sentences "
        "(\"hi\", \"yes\", \"stop\"), opinions (\"that was wrong\"), or "
        "slightly awkward grammar. Test: would a human listener say \"I "
        "genuinely couldn't tell what they want\" (unclear) or \"they want "
        "X but mangled a word\" (pick the content class)?"
    ),
    "few_shot": [],
    "ack": None,
    "escalate_ack": None,
}
