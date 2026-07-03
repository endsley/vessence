"""Restricted arithmetic evaluator and formatting helpers for do_math."""
from __future__ import annotations

import ast
import math
import operator
import re


BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
SAFE_CALLS = {
    "sqrt": math.sqrt,
    "pow": pow,
    "abs": abs,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
}
MAX_EXPONENT = 1000
EXPR_LINE_RE = re.compile(r"^\s*EXPRESSION\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)

PROMPT_TEMPLATE = """\
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


class UnsafeExpression(ValueError):
    pass


def build_math_prompt(prompt: str) -> str:
    return PROMPT_TEMPLATE.format(prompt=(prompt or "").strip())


def math_llm_payload(
    prompt_text: str,
    *,
    model: str,
    num_ctx: int,
    keep_alive: str | int,
) -> dict:
    return {
        "model": model,
        "prompt": prompt_text,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 40,
            "num_ctx": num_ctx,
        },
        "keep_alive": keep_alive,
    }


def eval_node(node):
    if isinstance(node, ast.Expression):
        return eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            raise UnsafeExpression(f"non-numeric constant: {node.value!r}")
        if isinstance(node.value, (int, float)):
            return node.value
        raise UnsafeExpression(f"non-numeric constant: {node.value!r}")
    if isinstance(node, ast.BinOp):
        op = BIN_OPS.get(type(node.op))
        if op is None:
            raise UnsafeExpression(f"binary op not allowed: {type(node.op).__name__}")
        left = eval_node(node.left)
        right = eval_node(node.right)
        if isinstance(node.op, ast.Pow) and isinstance(right, (int, float)) and abs(right) > MAX_EXPONENT:
            raise UnsafeExpression(f"exponent too large: {right}")
        return op(left, right)
    if isinstance(node, ast.UnaryOp):
        op = UNARY_OPS.get(type(node.op))
        if op is None:
            raise UnsafeExpression(f"unary op not allowed: {type(node.op).__name__}")
        return op(eval_node(node.operand))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise UnsafeExpression("call target must be a bare name")
        fn = SAFE_CALLS.get(node.func.id)
        if fn is None:
            raise UnsafeExpression(f"function not allowed: {node.func.id}")
        if node.keywords:
            raise UnsafeExpression("keyword args not allowed")
        return fn(*[eval_node(arg) for arg in node.args])
    raise UnsafeExpression(f"node not allowed: {type(node).__name__}")


def safe_eval(expr: str) -> float | int:
    """Parse `expr` and evaluate with the restricted AST walker."""
    tree = ast.parse(expr.strip(), mode="eval")
    return eval_node(tree)


def extract_expression(raw: str) -> str | None:
    """Pull the first EXPRESSION line, or fall back to the first reply line."""
    match = EXPR_LINE_RE.search(raw)
    candidate = match.group(1) if match else raw.strip().splitlines()[0] if raw.strip() else ""
    candidate = candidate.strip().strip("`").strip()
    if not candidate or candidate.upper() == "NONE":
        return None
    candidate = candidate.split("#", 1)[0].strip()
    return candidate or None


def format_number(value: float | int) -> str:
    """Pretty-print ints, ordinary floats, and very small non-zero floats."""
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float) and value.is_integer():
        return f"{int(value):,}"
    numeric = float(value)
    rounded = round(numeric, 4)
    if rounded == 0 and numeric != 0:
        return f"{numeric:.6g}"
    return f"{rounded:,.4f}".rstrip("0").rstrip(".")
