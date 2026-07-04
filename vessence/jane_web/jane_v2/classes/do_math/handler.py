"""Stage 2 handler for DO_MATH — Qwen parses the spoken expression, Python
computes the answer.

Flow:
  1. Ask the local LLM to translate the spoken prompt into a single Python
     arithmetic expression. The LLM only emits the expression (or NONE if
     the phrase isn't actually a computation).
  2. Walk the resulting expression with `ast` and only allow numeric
     literals, the basic binary ops, unary +/-, and a tiny set of safe
     calls (sqrt, pow, abs, round). No names, no attribute access.
  3. Evaluate, format, and reply with the number.

Qwen alone is unreliable on multi-digit multiplication (audit 2026-04-24:
234*567 → 132066 vs actual 132678). This handler keeps Qwen for what it's
good at (parsing the spoken form) and lets Python do the arithmetic.
"""

from __future__ import annotations

import logging
import time
from jane_web.jane_v2.ollama_client import post_local_llm_response as _post_local_llm_response

from .evaluator import (
    BIN_OPS as _BIN_OPS,
    EXPR_LINE_RE as _EXPR_LINE_RE,
    MAX_EXPONENT as _MAX_EXPONENT,
    PROMPT_TEMPLATE as _PROMPT_TEMPLATE,
    SAFE_CALLS as _SAFE_CALLS,
    UNARY_OPS as _UNARY_OPS,
    UnsafeExpression as _UnsafeExpression,
    build_math_prompt as _build_math_prompt,
    eval_node as _eval_node,
    extract_expression as _extract_expression,
    format_number as _format_number,
    math_llm_payload as _math_llm_payload,
    safe_eval,
)

logger = logging.getLogger(__name__)

async def _call_local_llm(prompt_text: str) -> str:
    return await _post_local_llm_response(prompt_text, _math_llm_payload)


def math_success_response(expr: str, answer: str) -> dict:
    return {"text": f"{answer}.", "thought": f"computed {expr} = {answer}"}


# ── Entry point ─────────────────────────────────────────────────────────────

async def handle(prompt: str, context: str = "") -> dict | None:
    full_prompt = _build_math_prompt(prompt)

    t0 = time.perf_counter()
    try:
        raw = await _call_local_llm(full_prompt)
    except Exception as e:
        logger.warning("do_math: LLM call failed (%s) — escalating", e)
        return None
    parse_ms = int((time.perf_counter() - t0) * 1000)

    expr = _extract_expression(raw)
    if expr is None:
        logger.info("do_math: LLM returned NONE for %r — escalating", prompt[:60])
        return None

    try:
        value = safe_eval(expr)
    except (_UnsafeExpression, SyntaxError, ValueError, TypeError,
            ZeroDivisionError, OverflowError) as e:
        logger.info("do_math: safe_eval rejected %r (%s) — escalating", expr, e)
        return None

    answer = _format_number(value)

    logger.info(
        "do_math: parse %dms — prompt=%r → expr=%r → %s",
        parse_ms, prompt[:60], expr[:80], answer,
    )
    return math_success_response(expr, answer)
