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
        "It is possible for STT to get cut off or background speech mixed "
        "into the prompt as noise. For those cases, declare the prompt "
        "unclear and ask the user to repeat again.\n\n"
        "Return 'unclear' when the message:\n"
        "  - Is cut off mid-word or ends with a preposition that clearly "
        "has more to come (\"what's the weather in\", \"turn on the\", "
        "\"can you please\")\n"
        "  - Stitches contradictory fragments with no coherent intent "
        "(\"play uh no wait the other thing um actually\")\n"
        "  - Is a short disconnected phrase with no verb or subject "
        "(\"apple meeting tomorrow blue\")\n\n"
        "Do NOT return 'unclear' for natural short sentences (\"hi\", "
        "\"yes\", \"stop\"), opinions/complaints (\"that was wrong\"), "
        "slightly awkward grammar, or topical statements with recoverable "
        "intent. When in doubt, prefer a specific class or 'others' — only "
        "return 'unclear' when a reasonable human would say \"I genuinely "
        "couldn't tell what you meant.\""
    ),
    "few_shot": [],
    "ack": None,
    "escalate_ack": None,
}
