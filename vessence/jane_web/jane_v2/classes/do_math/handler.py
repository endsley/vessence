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

import ast
import logging
import math
import operator
import re
import time

logger = logging.getLogger(__name__)


# ── Safe evaluator ──────────────────────────────────────────────────────────

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_SAFE_CALLS = {
    "sqrt": math.sqrt,
    "pow": pow,
    "abs": abs,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
}


class _UnsafeExpression(ValueError):
    pass


_MAX_EXPONENT = 1000  # blocks DoS via 9**9**9 — see Gemini review 2026-04-24


def _eval_node(node):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise _UnsafeExpression(f"non-numeric constant: {node.value!r}")
    if isinstance(node, ast.BinOp):
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise _UnsafeExpression(f"binary op not allowed: {type(node.op).__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Pow) and isinstance(right, (int, float)) and abs(right) > _MAX_EXPONENT:
            raise _UnsafeExpression(f"exponent too large: {right}")
        return op(left, right)
    if isinstance(node, ast.UnaryOp):
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            raise _UnsafeExpression(f"unary op not allowed: {type(node.op).__name__}")
        return op(_eval_node(node.operand))
    if isinstance(node, ast.Call):
        # Only bare-name calls into the safe set, no nested attribute access.
        if not isinstance(node.func, ast.Name):
            raise _UnsafeExpression("call target must be a bare name")
        fn = _SAFE_CALLS.get(node.func.id)
        if fn is None:
            raise _UnsafeExpression(f"function not allowed: {node.func.id}")
        if node.keywords:
            raise _UnsafeExpression("keyword args not allowed")
        return fn(*[_eval_node(a) for a in node.args])
    raise _UnsafeExpression(f"node not allowed: {type(node).__name__}")


def safe_eval(expr: str) -> float | int:
    """Parse `expr` and evaluate with the restricted ast walker."""
    tree = ast.parse(expr.strip(), mode="eval")
    return _eval_node(tree)


# ── LLM expression extractor ────────────────────────────────────────────────

_PROMPT_TEMPLATE = """\
Translate the user's spoken arithmetic question into a single Python expression.

Allowed operators: + - * / ** %
Allowed functions: sqrt(x), pow(x, y), abs(x), round(x), floor(x), ceil(x)
Numbers may be int or float. No variables, no names, no quotes.

If the user is NOT asking for a numeric computation (e.g. they're venting
about math, asking how division works, asking about time/dates), output
exactly: NONE

Examples:
User: "what's 17 times 23"
EXPRESSION: 17 * 23

User: "25 divided by 5"
EXPRESSION: 25 / 5

User: "what's 15 percent of 80"
EXPRESSION: 0.15 * 80

User: "square root of 144"
EXPRESSION: sqrt(144)

User: "7 times 8 plus 3"
EXPRESSION: 7 * 8 + 3

User: "what's 2 to the 10th power"
EXPRESSION: 2 ** 10

User: "math is hard"
EXPRESSION: NONE

Now translate this:
User: "{prompt}"
EXPRESSION:"""


async def _call_local_llm(prompt_text: str) -> str:
    import httpx
    from jane_web.jane_v2.models import (
        LOCAL_LLM,
        LOCAL_LLM_NUM_CTX,
        LOCAL_LLM_TIMEOUT,
        OLLAMA_KEEP_ALIVE,
        OLLAMA_URL,
    )
    body = {
        "model": LOCAL_LLM,
        "prompt": prompt_text,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 40,
            "num_ctx": LOCAL_LLM_NUM_CTX,
        },
        "keep_alive": OLLAMA_KEEP_ALIVE,
    }
    async with httpx.AsyncClient(timeout=LOCAL_LLM_TIMEOUT) as client:
        r = await client.post(OLLAMA_URL, json=body)
        r.raise_for_status()
        try:
            from jane_web.jane_v2.models import record_ollama_activity
            record_ollama_activity()
        except Exception:
            pass
        return (r.json().get("response") or "").strip()


_EXPR_LINE_RE = re.compile(r"^\s*EXPRESSION\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


def _extract_expression(raw: str) -> str | None:
    """Pull the first EXPRESSION: line, or fall back to the whole reply if
    the model omitted the prefix. Strip any trailing prose."""
    m = _EXPR_LINE_RE.search(raw)
    candidate = m.group(1) if m else raw.strip().splitlines()[0] if raw.strip() else ""
    candidate = candidate.strip().strip("`").strip()
    if not candidate or candidate.upper() == "NONE":
        return None
    # Drop any trailing comment or text after the expression — we only
    # accept what the safe parser will accept anyway.
    candidate = candidate.split("#", 1)[0].strip()
    return candidate or None


# ── Result formatting ───────────────────────────────────────────────────────

def _format_number(n: float | int) -> str:
    """Pretty-print results: keep ints as ints, round floats to 4 decimals
    and drop trailing zeros. Very small non-zero floats fall back to a
    higher-precision form so 1/20000 doesn't render as "0"."""
    if isinstance(n, bool):
        n = int(n)
    if isinstance(n, int):
        return f"{n:,}"
    if isinstance(n, float) and n.is_integer():
        return f"{int(n):,}"
    f = float(n)
    rounded = round(f, 4)
    if rounded == 0 and f != 0:
        s = f"{f:.6g}"
        if "e" in s or "E" in s:
            return s
        return s
    s = f"{rounded:,.4f}".rstrip("0").rstrip(".")
    return s


# ── Entry point ─────────────────────────────────────────────────────────────

async def handle(prompt: str, context: str = "") -> dict | None:
    full_prompt = _PROMPT_TEMPLATE.format(prompt=prompt.strip())

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
    reply = f"{answer}."

    logger.info(
        "do_math: parse %dms — prompt=%r → expr=%r → %s",
        parse_ms, prompt[:60], expr[:80], answer,
    )
    return {"text": reply, "thought": f"computed {expr} = {answer}"}
