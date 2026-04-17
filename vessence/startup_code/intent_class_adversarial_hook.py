#!/usr/bin/env python3
"""
PostToolUse hook: when a new intent classifier class file is written under
`intent_classifier/v2/classes/`, force Claude to generate 30 adversarial
(ambush) phrases and run them through the classifier to check for false
positives.

Fires on Write|Edit|MultiEdit. Uses a sidecar file
`<name>_adversarial.json` as a marker so it does NOT re-fire on later
edits to the same class once the adversarial suite has already been
generated.

The hook only injects context — it does not block — so Claude receives a
system reminder after the tool call completes and is compelled to act.

Registered in ~/.claude/settings.json under hooks.PostToolUse.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

CLASSES_DIR = Path("/home/chieh/ambient/vessence/intent_classifier/v2/classes")


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        sys.exit(0)

    tool_input = data.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not file_path:
        sys.exit(0)

    try:
        p = Path(file_path).resolve()
        p.relative_to(CLASSES_DIR)
    except (ValueError, OSError):
        sys.exit(0)

    if p.suffix != ".py" or p.name.startswith("_"):
        sys.exit(0)
    if p.stem.endswith("_adversarial"):
        sys.exit(0)

    sidecar = p.with_name(f"{p.stem}_adversarial.json")
    if sidecar.exists():
        # Already stress-tested — do not re-fire on subsequent edits.
        sys.exit(0)

    stem = p.stem
    CLASS = stem.upper()
    reminder = (
        f"AUTOFIX REQUIRED (new-intent-class hook): You just wrote "
        f"`intent_classifier/v2/classes/{stem}.py` and no adversarial "
        f"stress-test sidecar exists yet at "
        f"`intent_classifier/v2/classes/{stem}_adversarial.json`.\n\n"
        f"You MUST now generate 30 adversarial (ambush) phrases designed "
        f"to TRIP this class into FALSE POSITIVES — phrases that sound "
        f"superficially similar to the class's EXAMPLES but should NOT be "
        f"classified as {CLASS}. Cover: near-miss vocabulary, phrases "
        f"that mention the class topic in passing, questions about the "
        f"topic (not commands), negations, phrases sharing trigger words "
        f"but a different intent.\n\n"
        f"Steps:\n"
        f"  1. Write {stem}_adversarial.json with shape:\n"
        f"     {{\"class\": \"{CLASS}\", \"phrases\": [30 strings]}}\n"
        f"  2. Run:\n"
        f"     /home/chieh/google-adk-env/adk-venv/bin/python \\\n"
        f"       /home/chieh/ambient/vessence/intent_classifier/v2/adversarial_generator.py \\\n"
        f"       {stem}\n"
        f"  3. The script appends `results`, `false_positive_count`, and "
        f"`false_positives` to the sidecar.\n"
        f"  4. If false_positive_count > 0, tighten EXAMPLES in "
        f"{stem}.py (or add counter-examples to the conflicting sibling "
        f"class) and re-run the generator.\n\n"
        f"Do NOT report the task done until the sidecar contains "
        f"`results` and false_positive_count is 0 or explicitly "
        f"acknowledged."
    )

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": reminder,
        }
    }
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
