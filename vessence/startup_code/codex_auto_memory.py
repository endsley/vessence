#!/usr/bin/env python3
"""Nearest-memory preflight for raw Codex CLI sessions."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(os.environ.get("VESSENCE_HOME", "/home/chieh/ambient/vessence"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ORIGINAL_STDOUT_FD = os.dup(1)


class _silence_process_output:
    def __enter__(self):
        self.stdout_fd = os.dup(1)
        self.stderr_fd = os.dup(2)
        self.null_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(self.null_fd, 1)
        os.dup2(self.null_fd, 2)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.dup2(self.stdout_fd, 1)
        os.dup2(self.stderr_fd, 2)
        os.close(self.null_fd)
        os.close(self.stdout_fd)
        os.close(self.stderr_fd)


def _emit(text: str) -> None:
    os.write(ORIGINAL_STDOUT_FD, text.encode("utf-8", errors="replace"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Query nearest Jane memories for a Codex prompt.")
    parser.add_argument("query", nargs="*", help="Prompt/query text")
    parser.add_argument("--limit", type=int, default=2, help="Maximum memories to return")
    parser.add_argument("--max-distance", type=float, default=0.50, help="Maximum Chroma distance")
    args = parser.parse_args()

    query = " ".join(args.query).strip()
    if not query:
        return 0

    with _silence_process_output():
        from memory.v1.memory_retrieval import query_nearest_memory_lines

        hits = query_nearest_memory_lines(
            query,
            limit=args.limit,
            max_distance=args.max_distance,
            assistant_name="Jane",
        )
    if not hits:
        return 0

    lines = ["[Jane Auto Memory]"]
    for hit in hits:
        lines.append(f"- {hit}")
    lines.append("[/Jane Auto Memory]")
    _emit("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
