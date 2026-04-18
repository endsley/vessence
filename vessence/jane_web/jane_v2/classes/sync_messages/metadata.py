"""Sync messages class — force SMS re-sync from device."""

METADATA = {
    "name": "sync messages",
    "priority": 10,
    "description": (
        "[sync messages]\n"
        "User explicitly wants to force-refresh the server's SMS cache "
        "from the phone. Operational request, rarely conversational. "
        "Jane emits a sync.force_sms CLIENT_TOOL and the Android "
        "SmsSyncManager pulls the last ~14 days of SMS into the server's "
        "synced_messages table.\n\n"
        "Example phrasings the user might say:\n"
        "  - \"sync my messages\"\n"
        "  - \"refresh my texts\"\n"
        "  - \"force an SMS sync\"\n"
        "  - \"pull the latest SMS from my phone\"\n"
        "  - \"resync messages\"\n"
        "  - \"re-pull my texts\"\n\n"
        "Adversarial phrasings that LOOK LIKE 'sync messages' but ARE NOT:\n"
        "  - \"read my messages\" → 'read messages' (readback, not sync)\n"
        "  - \"any new texts\" → 'read messages'\n"
        "  - \"sync my calendar\" → 'others' (different sync domain)\n"
        "  - \"sync my contacts\" → 'others'\n"
        "  - \"send a message\" → 'send message' (outgoing, not sync)"
    ),
    "few_shot": [],
    "ack": None,  # Stage 2 fast-path is instant — no interim ack needed
    "escalate_ack": None,
}
