"""Pure routing helpers for the multi-essence runtime."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence


EssenceRouteCandidate = tuple[str, Sequence[str], str, str]


def capability_words(capability: str) -> list[str]:
    return capability.lower().replace("_", " ").split()


def capability_request_overlap(capability: str, user_request: str) -> set[str]:
    cap_words = set(capability_words(capability))
    request_words = set(user_request.lower().split())
    return cap_words & request_words


def capability_route_score(
    query: str,
    capabilities: Sequence[str],
    role_title: str,
    description: str,
) -> int:
    query_lower = query.lower()
    score = 0

    for capability in capabilities:
        for word in capability_words(capability):
            if word in query_lower:
                score += 2

    role = role_title.lower()
    desc = description.lower()
    for word in query_lower.split():
        if len(word) > 2:
            if word in role:
                score += 3
            if word in desc:
                score += 1

    return score


def best_essence_route(
    query: str,
    candidates: Iterable[EssenceRouteCandidate],
) -> str | None:
    best_name: str | None = None
    best_score = 0

    for name, capabilities, role_title, description in candidates:
        score = capability_route_score(query, capabilities, role_title, description)
        if score > best_score:
            best_score = score
            best_name = name

    return best_name


def capability_plan_steps(
    capabilities_map: Mapping[str, Sequence[str]],
    user_request: str,
) -> list[dict]:
    plan: list[dict] = []

    for capability, providers in capabilities_map.items():
        if capability_request_overlap(capability, user_request):
            plan.append({
                "subtask": f"Handle '{capability}' aspect of the request",
                "target_essence": providers[0],
                "capability_needed": capability,
            })

    return plan
