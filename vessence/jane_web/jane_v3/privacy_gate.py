"""Deterministic privacy-gate helpers for Jane v3 Stage 3 escalation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

PrivacyNeighbor = tuple[float, str | None, str | None]


@dataclass(frozen=True)
class PrivacyGateDecision:
    refuse: bool
    reason: str = ""
    closest_cls: str | None = None
    closest_dist: float | None = None
    private_count: int = 0
    in_range_count: int = 0


def privacy_neighbors_in_range(
    metadatas: list[dict[str, Any] | None],
    distances: list[float | None],
    *,
    max_distance: float,
    privacy_for: Callable[[str | None], str | None],
) -> list[PrivacyNeighbor]:
    in_range: list[PrivacyNeighbor] = []
    for meta, distance in zip(metadatas, distances):
        if distance is None or distance > max_distance:
            continue
        class_name = (meta or {}).get("class")
        in_range.append((float(distance), class_name, privacy_for(class_name)))
    return in_range


def privacy_gate_decision(in_range: list[PrivacyNeighbor]) -> PrivacyGateDecision:
    if not in_range:
        return PrivacyGateDecision(refuse=False)

    closest_dist, closest_cls, closest_privacy = in_range[0]
    if closest_privacy == "local_only":
        return PrivacyGateDecision(
            refuse=True,
            reason="closest",
            closest_cls=closest_cls,
            closest_dist=closest_dist,
            private_count=sum(1 for _, _, privacy in in_range if privacy == "local_only"),
            in_range_count=len(in_range),
        )

    private_count = sum(1 for _, _, privacy in in_range if privacy == "local_only")
    if private_count >= 3 and private_count > len(in_range) - private_count:
        return PrivacyGateDecision(
            refuse=True,
            reason="majority",
            closest_cls=closest_cls,
            closest_dist=closest_dist,
            private_count=private_count,
            in_range_count=len(in_range),
        )
    return PrivacyGateDecision(
        refuse=False,
        closest_cls=closest_cls,
        closest_dist=closest_dist,
        private_count=private_count,
        in_range_count=len(in_range),
    )
