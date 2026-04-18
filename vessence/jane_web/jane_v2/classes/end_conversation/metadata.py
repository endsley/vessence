"""End conversation class — goodbyes, dismissals, cancel."""

METADATA = {
    "name": "end conversation",
    "priority": 90,
    "description": (
        "[end conversation]\n"
        "User wants to terminate the current conversation cleanly — sign off, "
        "dismiss, or cancel an in-progress flow. The handler closes the voice "
        "loop (no STT relaunch; wake-word resumes if enabled) and Jane goes "
        "quiet.\n\n"
        "Example phrasings the user might say:\n"
        "  - \"bye\"\n"
        "  - \"goodbye jane\"\n"
        "  - \"stop\"\n"
        "  - \"cancel\"\n"
        "  - \"never mind\"\n"
        "  - \"that's all\"\n"
        "  - \"I'm done\"\n"
        "  - \"thanks that's it\"\n"
        "  - \"okay thank\"\n"
        "  - \"ok thanks\"\n"
        "  - \"ok thank you\"\n"
        "  - \"forget it\"\n"
        "  - \"nothing else\"\n\n"
        "Also YES to abandon an active pending_action: \"cancel\" during an "
        "open SMS draft or todo follow-up signals end-of-flow.\n\n"
        "Adversarial phrasings that LOOK LIKE 'end conversation' but ARE NOT:\n"
        "  - \"stop the music\" → 'music play' (media control, not sign-off)\n"
        "  - \"cancel my timer\" → 'timer' (cancel a specific timer)\n"
        "  - \"ok\" (alone, mid-flow) → stay in current flow or 'others'\n"
        "  - \"thanks\" (standalone, after a useful answer) → 'others' (acknowledgment, not sign-off)\n"
        "  - \"never mind\" after Jane misheard earlier → could be correction, not necessarily sign-off"
    ),
    "few_shot": [],
    "ack": None,
    "escalate_ack": None,
}
