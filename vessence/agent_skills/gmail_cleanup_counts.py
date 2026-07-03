"""Outcome-count helpers for Gmail cleanup scans."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, MutableMapping


def add_outcome_count(counts: MutableMapping[str, int], outcome: str, amount: int = 1) -> None:
    counts[outcome] = counts.get(outcome, 0) + amount


def merge_outcome_counts(counts: MutableMapping[str, int], updates: Mapping[str, int]) -> None:
    for outcome, amount in updates.items():
        add_outcome_count(counts, outcome, amount)


def count_message_outcomes(
    message_ids: Iterable[str],
    process_one: Callable[[str], str],
    *,
    failure_outcome: str,
    log_failure: Callable[[str, Exception], None] | None = None,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for message_id in message_ids:
        try:
            outcome = process_one(message_id)
        except Exception as exc:
            if log_failure:
                log_failure(message_id, exc)
            outcome = failure_outcome
        add_outcome_count(counts, outcome)
    return counts
