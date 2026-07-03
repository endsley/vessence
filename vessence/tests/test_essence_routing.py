from agent_skills.essence_routing import (
    best_essence_route,
    capability_plan_steps,
    capability_request_overlap,
    capability_route_score,
    capability_words,
)


def test_capability_words_and_overlap_preserve_matching_shape():
    assert capability_words("calendar_read") == ["calendar", "read"]
    assert capability_request_overlap("calendar_read", "please read my calendar") == {
        "calendar",
        "read",
    }


def test_capability_route_score_uses_capability_role_and_description_matches():
    assert capability_route_score(
        "calendar specialist sync",
        ["calendar_read"],
        "Calendar Specialist",
        "Can sync schedules",
    ) == 9


def test_capability_route_score_preserves_substring_matching():
    assert capability_route_score(
        "cartography",
        ["art"],
        "",
        "",
    ) == 2


def test_best_essence_route_preserves_first_positive_tie_and_zero_no_match():
    candidates = [
        ("first", ["calendar"], "", ""),
        ("second", ["calendar"], "", ""),
    ]

    assert best_essence_route("calendar", candidates) == "first"
    assert best_essence_route("unmatched", [("none", ["calendar"], "", "")]) is None


def test_capability_plan_steps_uses_first_provider_and_existing_subtask_text():
    assert capability_plan_steps(
        {
            "calendar_read": ["calendar-a", "calendar-b"],
            "weather": ["weather-a"],
        },
        "please read calendar",
    ) == [
        {
            "subtask": "Handle 'calendar_read' aspect of the request",
            "target_essence": "calendar-a",
            "capability_needed": "calendar_read",
        }
    ]
