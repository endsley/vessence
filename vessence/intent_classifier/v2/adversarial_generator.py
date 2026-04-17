#!/usr/bin/env python3
"""
Adversarial stress-tester for a new intent-classifier v2 class.

Usage:
  python adversarial_generator.py <class_stem>

Reads (or creates a stub for) the sidecar file
`intent_classifier/v2/classes/<class_stem>_adversarial.json`:

  {
    "class": "TIMER",
    "phrases": ["...", "...", ...]   # 30 adversarial phrases
  }

Runs each phrase through `intent_classifier.v2.classifier.classify(...)`
and writes a `results` field back into the same file:

  {
    "class": "TIMER",
    "phrases": [...],
    "results": [
        {"phrase": "...", "classification": "...",
         "confidence": 0.xx, "margin": 0.xx,
         "false_positive": true/false},
        ...
    ],
    "false_positive_count": N,
    "false_positives": ["phrases that wrongly hit the new class"]
  }

Invoked by the Claude Code hook
`~/.claude/hooks/intent_class_adversarial_hook.py` whenever a new class
file is written under `intent_classifier/v2/classes/`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLASSES_DIR = HERE / "classes"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: adversarial_generator.py <class_stem>", file=sys.stderr)
        return 2

    stem = sys.argv[1]
    class_file = CLASSES_DIR / f"{stem}.py"
    if not class_file.exists():
        print(f"class file not found: {class_file}", file=sys.stderr)
        return 2

    sidecar = CLASSES_DIR / f"{stem}_adversarial.json"
    if not sidecar.exists():
        stub = {
            "class": stem.upper(),
            "phrases": [],
            "_instructions": (
                "Claude: fill `phrases` with 30 adversarial (ambush) "
                "strings designed to trip this class into false positives, "
                "then re-run this script."
            ),
        }
        sidecar.write_text(json.dumps(stub, indent=2))
        print(
            f"Wrote stub {sidecar.name}. Fill `phrases` with 30 adversarial "
            f"phrases, then re-run."
        )
        return 1

    data = json.loads(sidecar.read_text())
    phrases = data.get("phrases", [])
    if len(phrases) < 30:
        print(
            f"ERROR: {sidecar.name} has {len(phrases)} phrases — need 30 "
            f"adversarial phrases before stress-testing.",
            file=sys.stderr,
        )
        return 2

    # Import classifier lazily — it boots chromadb, slow.
    sys.path.insert(0, str(HERE.parent.parent))
    from intent_classifier.v2.classifier import classify  # noqa: E402

    target = data.get("class", stem.upper())
    results = []
    false_positives = []
    for phrase in phrases:
        try:
            r = classify(phrase)
        except Exception as e:
            r = {"classification": f"ERROR:{e}", "confidence": 0.0, "margin": 0.0}
        is_fp = r.get("classification") == target
        if is_fp:
            false_positives.append(phrase)
        results.append({
            "phrase": phrase,
            "classification": r.get("classification"),
            "confidence": round(float(r.get("confidence", 0.0)), 3),
            "margin": round(float(r.get("margin", 0.0)), 3),
            "false_positive": is_fp,
        })

    data["results"] = results
    data["false_positive_count"] = len(false_positives)
    data["false_positives"] = false_positives
    sidecar.write_text(json.dumps(data, indent=2))

    print(f"Stress-tested {len(phrases)} adversarial phrases against {target}.")
    print(f"False positives: {len(false_positives)}")
    for fp in false_positives:
        print(f"  - {fp}")
    return 0 if not false_positives else 1


if __name__ == "__main__":
    sys.exit(main())
