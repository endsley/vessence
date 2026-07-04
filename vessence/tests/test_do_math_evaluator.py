import pytest

from jane_web.jane_v2.classes.do_math import handler
from jane_web.jane_v2.classes.do_math.evaluator import (
    BIN_OPS,
    EXPR_LINE_RE,
    MAX_EXPONENT,
    PROMPT_TEMPLATE,
    SAFE_CALLS,
    UNARY_OPS,
    UnsafeExpression,
    build_math_prompt,
    eval_node,
    extract_expression,
    format_number,
    math_llm_payload,
    safe_eval,
)
from jane_web.jane_v2.ollama_client import post_local_llm_response


def test_handler_uses_extracted_math_helpers() -> None:
    assert handler._BIN_OPS is BIN_OPS
    assert handler._UNARY_OPS is UNARY_OPS
    assert handler._SAFE_CALLS is SAFE_CALLS
    assert handler._MAX_EXPONENT is MAX_EXPONENT
    assert handler._EXPR_LINE_RE is EXPR_LINE_RE
    assert handler._PROMPT_TEMPLATE is PROMPT_TEMPLATE
    assert handler._build_math_prompt is build_math_prompt
    assert handler._UnsafeExpression is UnsafeExpression
    assert handler._eval_node is eval_node
    assert handler._extract_expression is extract_expression
    assert handler._format_number is format_number
    assert handler._math_llm_payload is math_llm_payload
    assert handler._post_local_llm_response is post_local_llm_response
    assert handler.safe_eval is safe_eval


def test_math_success_response_preserves_text_and_thought_shape() -> None:
    assert handler.math_success_response("7 * 8", "56") == {
        "text": "56.",
        "thought": "computed 7 * 8 = 56",
    }


def test_safe_eval_handles_arithmetic_and_allowed_functions() -> None:
    assert safe_eval("2 + 3 * 4") == 14
    assert safe_eval("(2 + 3) * 4") == 20
    assert safe_eval("2 ** 10") == 1024
    assert safe_eval("sqrt(144)") == 12
    assert safe_eval("floor(2.9) + ceil(2.1)") == 5
    assert safe_eval("abs(-7)") == 7


@pytest.mark.parametrize(
    "expr",
    [
        "__import__('os')",
        "(1).__class__",
        "[1, 2, 3]",
        "{'x': 1}",
        "sqrt(x)",
        "round(number=2.5)",
        "True",
        "9 ** 1001",
    ],
)
def test_safe_eval_rejects_unsafe_or_non_numeric_expressions(expr: str) -> None:
    with pytest.raises(UnsafeExpression):
        safe_eval(expr)


def test_extract_expression_handles_prefixed_raw_and_none_replies() -> None:
    assert extract_expression("EXPRESSION: 17 * 23") == "17 * 23"
    assert extract_expression("thoughts\nEXPRESSION: 2 + 2 # simple") == "2 + 2"
    assert extract_expression("```sqrt(144)```") == "sqrt(144)"
    assert extract_expression("NONE") is None
    assert extract_expression("EXPRESSION: NONE") is None
    assert extract_expression("") is None


def test_build_math_prompt_preserves_expression_contract() -> None:
    prompt = build_math_prompt(" what's 17 times 23 ")

    assert "Allowed operators: + - * / ** %" in prompt
    assert "Allowed functions: sqrt(x), pow(x, y), abs(x), round(x), floor(x), ceil(x)" in prompt
    assert 'User: "what\'s 17 times 23"' in prompt
    assert prompt.endswith("EXPRESSION:")


def test_math_llm_payload_preserves_local_ollama_options() -> None:
    payload = math_llm_payload(
        "EXPRESSION:",
        model="qwen",
        num_ctx=2048,
        keep_alive="10m",
    )

    assert payload == {
        "model": "qwen",
        "prompt": "EXPRESSION:",
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 40, "num_ctx": 2048},
        "keep_alive": "10m",
    }


def test_format_number_keeps_ints_readable_and_floats_concise() -> None:
    assert format_number(1000) == "1,000"
    assert format_number(2.0) == "2"
    assert format_number(1 / 3) == "0.3333"
    assert format_number(1234.56789) == "1,234.5679"
    assert format_number(0.0000005) == "5e-07"
