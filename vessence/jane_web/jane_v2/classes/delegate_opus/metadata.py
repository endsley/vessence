"""Delegate-to-Opus class — explicit escalation signal.

A chroma-trained label (249 exemplars) used to route general-reasoning / multi-
step / topic-switch / contact-related asks to the full brain. NO handler on
purpose — the pipeline treats it the same as 'others' and escalates to Stage 3.

Registered so the v3 classifier can show qwen a proper description on the
primary-option slot when the chroma winner is DELEGATE_OPUS. Without this,
qwen saw an empty `[delegate opus]` line and had no signal to work with.
"""

METADATA = {
    "name": "delegate opus",
    "priority": 98,
    "description": (
        "[delegate opus]\n"
        "Request needs the full reasoning brain — no narrow handler fits. "
        "Escalate to Stage 3 so Opus can handle it with full memory + tools.\n\n"
        "Typical triggers:\n"
        "  - Contact actions that aren't SMS/call templates (\"call Dr. Wu's office\")\n"
        "  - Calendar write/update (\"add a meeting tomorrow at 10\")\n"
        "  - Multi-step or multi-topic asks (\"switch topics\", \"let's work on the next thing\")\n"
        "  - Sync / state-of-system questions (\"are we out of sync again\")\n"
        "  - Anything open-ended that a templated stage-2 handler would mangle.\n\n"
        "When in doubt between a specific class and this one, prefer the specific "
        "class only if the phrasing matches its exemplars cleanly; otherwise pick "
        "'delegate opus' so Opus can take the full read."
    ),
    "few_shot": [
        ("call Sarah", "delegate opus:High"),
        ("let's switch topics", "delegate opus:High"),
        ("add a meeting tomorrow", "delegate opus:High"),
        ("for now let's focus on something else", "delegate opus:High"),
    ],
    "ack": None,
    "escalate_ack": "Let me dig into that…",
}
