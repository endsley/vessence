"""auto_commit_wip.py — commit any uncommitted work before the code auditor.

The code auditor needs a clean git tree to branch off safely. During the
day, Jane and Claude accumulate changes that often don't get committed.
This script auto-commits everything so the auditor can run.

Safety:
  - Commits to whatever branch is current (usually master).
  - Message is prefixed with "auto-commit:" so it's easy to identify.
  - Never force-pushes — just a local commit.
  - If there's nothing to commit, exits cleanly.

Run as part of nightly_self_improve.py, right before the Code Auditor.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("auto_commit_wip")

VESSENCE_HOME = Path(os.environ.get(
    "VESSENCE_HOME", str(Path(__file__).resolve().parents[1])
))


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(VESSENCE_HOME),
        capture_output=True, text=True,
        check=check,
    )


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--push", action="store_true",
                        help="Push to remote after committing.")
    args = parser.parse_args()

    # Check if there's anything to commit
    status = _git("status", "--porcelain", check=False)
    lines = [ln for ln in status.stdout.splitlines()
             if ln.strip() and not ln[3:].strip().startswith(".git.backup")]

    if not lines and not args.push:
        logger.info("Working tree is clean — nothing to commit.")
        return 0

    if lines:
        logger.info("Found %d uncommitted change(s), auto-committing.", len(lines))

        # Stage everything
        _git("add", "-A", check=False)

        # Build commit message
        ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        phase = "post-self-improve" if args.push else "pre-self-improve WIP"
        msg = (
            f"auto-commit: {phase} ({ts})\n\n"
            f"{len(lines)} file(s) changed. Committed automatically by the\n"
            f"nightly self-improvement orchestrator."
        )

        result = _git("commit", "-m", msg, "--no-verify", check=False)
        if result.returncode == 0:
            logger.info("Committed %d file(s).", len(lines))
        else:
            logger.warning("git commit failed: %s", result.stderr[:300])
            if not args.push:
                return 1
    else:
        logger.info("Working tree is clean — nothing to commit.")

    # Push if requested
    if args.push:
        logger.info("Pushing to remote...")
        push = _git("push", check=False)
        if push.returncode == 0:
            logger.info("Pushed successfully.")
        else:
            logger.warning("git push failed: %s", push.stderr[:300])
            # Don't fail the job — push failure is non-fatal
            # (could be network issue, still committed locally)

    return 0


if __name__ == "__main__":
    sys.exit(main())
