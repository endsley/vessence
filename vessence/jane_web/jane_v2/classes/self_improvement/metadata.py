"""self_improvement class — classifier metadata."""


METADATA = {
    "name": "self improvement",
    "priority": 15,
    "description": (
        "[self improvement]\n"
        "Questions about Jane's own nightly self-improvement work: "
        "what she audited, what she fixed, what the dead-code / doc-drift / "
        "transcript-review / pipeline-audit jobs found overnight. Also "
        "questions about recent code changes Jane made to herself. "
        "- Vocal summary log: $VESSENCE_DATA_HOME/self_improve_vocal_log.jsonl "
        "(JSONL; each line has timestamp, job, severity, summary)\n"
        "- Orchestrator + per-job technical logs: "
        "$VESSENCE_DATA_HOME/logs/self_improve_*.log\n"
        "- Stage 3 (Opus) gets the recent summaries auto-injected as context; "
        "for older or specific runs, read the JSONL file directly.\n"
        "- Always escalates to Stage 3 so Opus can answer conversationally\n"
        "- DOES NOT handle: general coding help, user's own projects, "
        "or questions about Jane's architecture (those go to 'others')."
    ),
    "few_shot": [
        ("What did you fix last night?", "self improvement:High"),
        ("Any self-improvements today?", "self improvement:High"),
        ("What did the nightly audit find?", "self improvement:High"),
        ("Did the transcript review catch anything?", "self improvement:High"),
        ("What bugs did you catch this week?", "self improvement:High"),
        ("What's in the self-improve log?", "self improvement:High"),
        ("Did dead code auditor remove anything?", "self improvement:High"),
        ("What did you improve recently?", "self improvement:High"),
        ("How are you improving yourself?", "self improvement:Medium"),
        ("How was your night?", "self improvement:Medium"),
        # Contrast cases — NOT self improvement
        ("How do I improve my Python code?", "others:Low"),
        ("Fix this bug in my app", "others:Low"),
    ],
    "ack": "Checking what I worked on overnight…",
    "escalate_ack": "Let me pull up what I've been fixing…",
}
