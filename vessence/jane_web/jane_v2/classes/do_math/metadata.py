"""Do math class — user wants Jane to compute a numeric expression."""

METADATA = {
    "name": "do math",
    "priority": 12,
    "description": (
        "[do math]\n"
        "User wants a quick arithmetic answer (multiplication, division, "
        "addition, subtraction, percent, square/root, or a small mixed "
        "expression). The handler asks the local LLM to translate the "
        "spoken phrase into a Python expression, evaluates it with a "
        "restricted ast walker (no names, no calls outside a tiny safe "
        "set), and reports the number naturally.\n\n"
        "Example phrasings the user might say:\n"
        "  - \"what's 17 times 23\"\n"
        "  - \"25 divided by 5\"\n"
        "  - \"what's 15 percent of 80\"\n"
        "  - \"square root of 144\"\n"
        "  - \"7 times 8 plus 3\"\n\n"
        "Adversarial phrasings that LOOK LIKE 'do math' but ARE NOT:\n"
        "  - \"how many minutes until 5pm\" → 'others' (time arithmetic)\n"
        "  - \"how many emails do I have\" → 'read email' (count, not math)\n"
        "  - \"how do I do long division\" → 'others' (teaching question)\n"
        "  - \"I'm bad at math\" / \"math is hard\" → 'others' (venting)\n"
        "  - \"calculate my taxes for me\" → 'others' (multi-step task)\n"
        "  - \"the meeting times are 3 and 5\" → 'others' (\"times\" is a noun)"
    ),
    "few_shot": [
        ("what's 17 times 23", "do math:High"),
        ("25 divided by 5", "do math:High"),
        ("what's 15 percent of 80", "do math:High"),
    ],
    "ack": None,
    "escalate_ack": None,
}
