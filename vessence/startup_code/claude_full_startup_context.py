#!/usr/bin/env python3
"""Inject the full Jane startup document set into Claude sessions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.config import VAULT_DIR, VESSENCE_DATA_HOME, VESSENCE_HOME

DATA_ROOT = Path(VESSENCE_DATA_HOME)
VESSENCE_ROOT = Path(VESSENCE_HOME)
VAULT_ROOT = Path(VAULT_DIR)

DOCS = [
    ("User Profile", DATA_ROOT / "user_profile.md"),
    ("User Identity Essay", VAULT_ROOT / "documents" / "chieh_identity_essay.txt"),
    ("Jane Identity Essay", VAULT_ROOT / "documents" / "jane_identity_essay.txt"),
    ("Amber Identity Essay", VAULT_ROOT / "documents" / "amber_identity_essay.txt"),
    ("Jane Architecture", VESSENCE_ROOT / "configs" / "Jane_architecture.md"),
    ("Amber Architecture", VESSENCE_ROOT / "configs" / "Amber_architecture.md"),
    ("Memory Architecture", VESSENCE_ROOT / "configs" / "memory_manage_architecture.md"),
    ("Skills Registry", VESSENCE_ROOT / "configs" / "SKILLS_REGISTRY.md"),
    ("TODO Projects", VESSENCE_ROOT / "configs" / "TODO_PROJECTS.md"),
    ("Project Accomplishments", VESSENCE_ROOT / "configs" / "PROJECT_ACCOMPLISHMENTS.md"),
    ("Cron Jobs", VESSENCE_ROOT / "configs" / "CRON_JOBS.md"),
]


def read_doc(title: str, path: Path) -> str:
    if not path.exists() or not path.is_file():
        return f"=== {title} ===\n[missing: {path}]"
    try:
        content = path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception as exc:
        return f"=== {title} ===\n[error reading {path}: {exc}]"
    return f"=== {title} ===\n{content}"


def main() -> int:
    parts = [
        "[Jane Full Startup Context — Read At New Session Start]",
        "This block contains the authoritative startup documents Jane should read to recover identity, architecture, priorities, accomplishments, and current operating rules.",
    ]
    for title, path in DOCS:
        parts.append(read_doc(title, path))

    print(json.dumps({"additionalContext": "\n\n".join(parts)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
