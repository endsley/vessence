#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


AMBIENT_HOME = Path(__file__).resolve().parents[2]
ANNOUNCEMENTS_PATH = AMBIENT_HOME / "vessence-data" / "data" / "jane_announcements.jsonl"


def main() -> None:
    message = " ".join(sys.argv[1:]).strip()
    if not message:
        raise SystemExit("Usage: send_jane_announcement.py <message>")
    ANNOUNCEMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "message": message,
    }
    with ANNOUNCEMENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


if __name__ == "__main__":
    main()
