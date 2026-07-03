import json

from agent_skills.edu_homework_answers import format_response


def test_format_response_preserves_simple_answer_types():
    assert format_response("number", 3) == "3"
    assert format_response("multiple_choice", "B") == "B"
    assert format_response("vector", [1, "2/3", -4]) == "[1; 2/3; -4]"


def test_format_response_handles_linear_system_variants():
    assert json.loads(format_response(
        "linear_system_solve",
        {"classification": "unique", "v": [1, 2]},
    )) == {"class": "unique", "v": "[1; 2]"}
    assert json.loads(format_response(
        "linear_system_solve",
        {"classification": "none", "A": [[1, 0]], "b": [1]},
    )) == {"class": "none", "v": ""}
    assert json.loads(format_response(
        "linear_system_solve",
        {"classification": "infinite", "A": [[1, 1]], "b": [2]},
    )) == {"class": "infinite", "v": "[2; 0]"}


def test_format_response_handles_basis_and_reach_json_shapes():
    assert format_response(
        "subspace_basis",
        {"kind": "null_space", "A": [[1, 1]]},
    ) == "[-1; 1]"
    assert json.loads(format_response(
        "classify_and_reach",
        {"classification": "reachable", "reachable": True},
    )) == {"class": "reachable", "reach": "yes"}
    assert json.loads(format_response(
        "invertibility_with_blank",
        {"invertible": True, "blank": "2"},
    )) == {"class": "invertible", "blank": "2"}


def test_format_response_handles_solve_system_with_basis():
    assert json.loads(format_response(
        "solve_system_with_basis",
        {"classification": "unique", "A": [[1, 0], [0, 1]], "b": [2, 3]},
    )) == {"class": "unique", "v": "[2; 3]", "M": ""}
    assert json.loads(format_response(
        "solve_system_with_basis",
        {"classification": "infinite", "A": [[1, 1]], "b": [2]},
    )) == {"class": "infinite", "v": "", "M": "[2 -1; 0 1]"}
