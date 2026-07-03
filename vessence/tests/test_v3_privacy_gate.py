from jane_web.jane_v3.privacy_gate import (
    privacy_gate_decision,
    privacy_neighbors_in_range,
)


def test_privacy_neighbors_in_range_filters_distance_and_maps_privacy():
    privacy = {"clinic": "local_only", "weather": "public"}

    assert privacy_neighbors_in_range(
        [{"class": "clinic"}, {"class": "weather"}, {"class": "timer"}],
        [0.2, 0.5, None],
        max_distance=0.4,
        privacy_for=lambda cls: privacy.get(cls or ""),
    ) == [(0.2, "clinic", "local_only")]


def test_privacy_gate_decision_refuses_when_closest_neighbor_is_private():
    decision = privacy_gate_decision(
        [
            (0.1, "clinic", "local_only"),
            (0.2, "weather", "public"),
        ]
    )

    assert decision.refuse
    assert decision.reason == "closest"
    assert decision.closest_cls == "clinic"
    assert decision.closest_dist == 0.1
    assert decision.private_count == 1
    assert decision.in_range_count == 2


def test_privacy_gate_decision_refuses_private_majority():
    decision = privacy_gate_decision(
        [
            (0.1, "weather", "public"),
            (0.2, "clinic", "local_only"),
            (0.3, "patient", "local_only"),
            (0.4, "schedule", "local_only"),
            (0.5, "timer", "public"),
        ]
    )

    assert decision.refuse
    assert decision.reason == "majority"
    assert decision.private_count == 3
    assert decision.in_range_count == 5


def test_privacy_gate_decision_allows_empty_and_non_majority_neighbors():
    assert not privacy_gate_decision([]).refuse

    decision = privacy_gate_decision(
        [
            (0.1, "weather", "public"),
            (0.2, "clinic", "local_only"),
            (0.3, "timer", "public"),
        ]
    )

    assert not decision.refuse
    assert decision.reason == ""
    assert decision.private_count == 1
    assert decision.in_range_count == 3
