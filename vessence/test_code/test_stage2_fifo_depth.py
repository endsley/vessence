"""Tests for Stage 2 FIFO depth selection."""

from __future__ import annotations

from jane_web.jane_v2.pipeline import _stage2_fifo_turns


def test_private_stage2_handlers_get_deeper_fifo():
    assert _stage2_fifo_turns("clinic schedules info") == 7
    assert _stage2_fifo_turns("clinic_schedules_info") == 7


def test_non_private_stage2_handlers_keep_caller_default():
    assert _stage2_fifo_turns("weather") == 3
    assert _stage2_fifo_turns("weather", default=4) == 4
