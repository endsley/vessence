#!/usr/bin/env python3
"""Runner for KathiaScheduleSequence cron job.

Phase 1: trigger AI summary generation for all patients (~1 click per patient).
Wait:    30 min for AI to generate summaries.
Phase 2: extract health_concerns, recommendations, visit_summary from each modal.
Saves all data to SQLite at VESSENCE_DATA_HOME/schedule.db.

Typical cron: run at 6:30 AM Mon-Fri. Completes ~7:05 AM.
"""
import asyncio
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from skills.web_sequences.kathia_schedule import KathiaScheduleSequence


async def main() -> None:
    seq = KathiaScheduleSequence()
    result = await seq.run()
    if result.get("ok"):
        data = result.get("data", {})
        print(f"OK — {data.get('rows_saved', 0)} appointments saved, "
              f"AI triggered: {data.get('ai_triggered', 0)}, "
              f"days: {data.get('days', [])}")
    else:
        print(f"FAILED — {result.get('error', 'unknown error')}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
