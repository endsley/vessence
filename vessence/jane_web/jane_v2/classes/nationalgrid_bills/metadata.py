"""National Grid bill questions for known Waterlily property accounts."""

METADATA = {
    "name": "nationalgrid bills",
    "priority": 9,
    "description": (
        "[nationalgrid bills]\n"
        "User asks for National Grid utility bill amounts, monthly bill history, "
        "gas/electric charges, or yearly totals for known property accounts. "
        "Known aliases include Air Temple electric/gas and Earth Kingdom gas. "
        "Use for questions like 'what's Air Temple's electric bill for each "
        "month of 2026' or 'how much did Air Temple spend on gas for 2026 so far'."
    ),
    "few_shot": [
        ("what's Air Temple's electric bill for each month of 2026", "nationalgrid bills:High"),
        ("how much did Air Temple spend on gas for 2026 so far", "nationalgrid bills:High"),
        ("download all Air Temple gas bills for 2026", "nationalgrid bills:High"),
        ("what are the National Grid gas charges for Air Temple this year", "nationalgrid bills:High"),
    ],
    "ack": "Checking National Grid bills...",
    "escalate_ack": "Let me dig into the National Grid bill records...",
}
