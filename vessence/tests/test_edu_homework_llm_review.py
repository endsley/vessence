from agent_skills import edu_homework_audit
from agent_skills.edu_homework_audit import QuestionFinding
from agent_skills.edu_homework_llm_review import (
    build_llm_review_prompt,
    normalize_llm_review_response,
    run_batched_llm_review,
)


def finding(n: int, *, prompt_text: str = "Prompt", answer_type: str = "") -> QuestionFinding:
    return QuestionFinding(
        n=n,
        key=f"k{n}",
        answer_type=answer_type,
        solution=None,
        submitted_response=None,
        verdict=None,
        feedback_text=None,
        prompt_text=prompt_text,
        prompt_html="",
        issues=[],
    )


def test_homework_audit_uses_llm_review_helpers():
    assert edu_homework_audit._build_llm_review_prompt is build_llm_review_prompt
    assert edu_homework_audit._normalize_llm_review_response is normalize_llm_review_response
    assert edu_homework_audit._run_batched_llm_review is run_batched_llm_review


def test_build_llm_review_prompt_preserves_chunk_shape_and_empty_prompt_fallback():
    assert build_llm_review_prompt(
        [finding(1, prompt_text="  What is x?  ", answer_type="numeric"), finding(2, prompt_text="")],
        "INSTRUCTIONS\n",
    ) == (
        "INSTRUCTIONS\n"
        "\n[Q1] (key=k1, type=numeric)\nWhat is x?\n"
        "\n[Q2] (key=k2, type=default)\n<EMPTY PROMPT>\n"
    )


def test_normalize_llm_review_response_preserves_issue_defaults_and_prefixes():
    assert normalize_llm_review_response(
        {
            "reviews": [
                {
                    "n": 3,
                    "issues": [
                        {"severity": "high", "kind": "math", "message": "Wrong."},
                        {"kind": "style", "message": ""},
                        {"message": "Defaulted."},
                    ],
                },
                {"issues": [{"message": "Missing n"}]},
                {"n": 4, "issues": []},
            ]
        }
    ) == {
        3: [
            {"severity": "high", "kind": "llm_math", "message": "Wrong."},
            {"severity": "low", "kind": "llm_llm_review", "message": "Defaulted."},
        ],
        4: [],
    }


def test_run_batched_llm_review_merges_batches_and_records_partial_failures():
    calls = []

    def completion(prompt: str, *, tier: str, timeout: int) -> dict:
        calls.append((prompt, tier, timeout))
        if "[Q3]" in prompt:
            raise RuntimeError("boom")
        return {
            "reviews": [
                {"n": 1, "issues": [{"kind": "clarity", "message": "Clarify Q1."}]},
                {"n": 2, "issues": []},
            ]
        }

    result = run_batched_llm_review(
        [finding(1), finding(2), finding(3)],
        instructions="INSTRUCTIONS\n",
        completion_json=completion,
        model_tier="utility",
        timeout=12,
        batch_size=2,
    )

    assert result[1] == [
        {"severity": "low", "kind": "llm_clarity", "message": "Clarify Q1."}
    ]
    assert result[2] == []
    assert result[-1] == [
        {
            "severity": "low",
            "kind": "llm_partial_failure",
            "message": "batch [3] failed: boom",
        }
    ]
    assert len(calls) == 2
    assert calls[0][1:] == ("utility", 12)


def test_run_batched_llm_review_raises_when_every_batch_fails_and_validates_size():
    def completion(_prompt: str, *, tier: str, timeout: int) -> dict:
        raise RuntimeError("offline")

    try:
        run_batched_llm_review(
            [finding(1), finding(2)],
            instructions="INSTRUCTIONS\n",
            completion_json=completion,
            batch_size=1,
        )
    except RuntimeError as exc:
        assert str(exc) == "batch [1] failed: offline; batch [2] failed: offline"
    else:
        raise AssertionError("expected RuntimeError")

    try:
        run_batched_llm_review(
            [finding(1)],
            instructions="INSTRUCTIONS\n",
            completion_json=completion,
            batch_size=0,
        )
    except ValueError as exc:
        assert str(exc) == "batch_size must be >= 1, got 0"
    else:
        raise AssertionError("expected ValueError")
