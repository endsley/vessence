"""Shared footer helpers for Stage 2 escalation context blocks."""

from __future__ import annotations

import datetime
from collections.abc import Callable


def utcnow_naive() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def fetched_at_footer(instructions: str, *, now_fn: Callable[[], datetime.datetime] = utcnow_naive) -> str:
    return f"(Fetched at {now_fn().isoformat()}Z. {instructions})"
