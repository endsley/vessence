"""Persistence policy helpers for Jane proxy turn writeback."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Stage3WritebackDecision:
    run_stage3_writeback: bool
    skip_log_stage: str | None = None
    reason: str | None = None


def privacy_local_only_for_class(
    cls: str | None,
    privacy_for_fn: Callable[[str], str],
) -> bool:
    if not cls:
        return False
    try:
        return privacy_for_fn(cls) == "local_only"
    except Exception:
        return False


def stage3_writeback_decision(
    stage: str | None,
    *,
    privacy_local_only: bool,
) -> Stage3WritebackDecision:
    if privacy_local_only:
        return Stage3WritebackDecision(
            run_stage3_writeback=False,
            skip_log_stage="persistence_privacy_skip_haiku_summary",
            reason="privacy_local_only",
        )
    if (stage or "stage3").lower() != "stage3":
        return Stage3WritebackDecision(
            run_stage3_writeback=False,
            skip_log_stage="persistence_stage2_skip_theme_summary",
            reason="non_stage3",
        )
    return Stage3WritebackDecision(run_stage3_writeback=True)
