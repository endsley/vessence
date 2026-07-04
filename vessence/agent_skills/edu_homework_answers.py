"""Answer formatting helpers for the education homework auditor."""
from __future__ import annotations

import json
from typing import Any

import sympy as sp


SIMPLE_ANSWER_TYPES = {"", "number", "math_expression", "fraction", "text", "multiple_choice"}


def format_response(answer_type: str | None, solution: Any) -> str:
    """Convert a snapshot.solution into the string the answer form expects."""
    at = answer_type or ""

    if at in SIMPLE_ANSWER_TYPES:
        return str(solution)

    if at == "vector":
        return _matlab_vec(solution)

    if at == "subspace_basis":
        return _format_subspace_basis(solution)

    if at == "linear_system_solve":
        return _format_linear_system_solve(solution)

    if at == "classify_and_reach":
        return _format_classify_and_reach(solution)

    if at == "invertibility_with_blank":
        return _format_invertibility_with_blank(solution)

    if at == "solve_system_with_basis":
        return _format_solve_system_with_basis(solution)

    raise ValueError(f"Unsupported answer_type for auto-answer: {at!r}")


def _format_subspace_basis(solution: Any) -> str:
    A = solution["A"]
    kind = solution["kind"]
    if kind == "null_space":
        cols = _nullspace_basis(A)
    elif kind == "column_space":
        cols = _columnspace_basis(A)
    elif kind == "row_space":
        cols = _rowspace_basis(A)
    else:
        raise ValueError(f"unknown subspace kind: {kind!r}")
    return _matlab_matrix(cols)


def _format_linear_system_solve(solution: Any) -> str:
    c = solution["classification"]
    if c == "unique":
        v_str = _matlab_vec(solution.get("v") or [])
    elif c == "infinite":
        v_str = _matlab_vec(_solve_particular(solution["A"], solution["b"]))
    else:
        v_str = ""
    return json.dumps({"class": c, "v": v_str})


def _format_classify_and_reach(solution: Any) -> str:
    return json.dumps({
        "class": solution["classification"],
        "reach": "yes" if solution.get("reachable") else "no",
    })


def _format_invertibility_with_blank(solution: Any) -> str:
    is_inv = bool(solution.get("invertible"))
    c = "invertible" if is_inv else "not_invertible"
    blank = "" if not is_inv else str(solution.get("blank") or "")
    return json.dumps({"class": c, "blank": blank})


def _format_solve_system_with_basis(solution: Any) -> str:
    c = solution["classification"]
    A = solution.get("A")
    b = solution.get("b")
    if c == "unique":
        x = _solve_unique(A, b)
        return json.dumps({"class": c, "v": _matlab_vec(x), "M": ""})
    if c == "infinite":
        x_p = _solve_particular(A, b)
        ns = _nullspace_basis(A)
        cols = [x_p] + ns
        return json.dumps({"class": c, "v": "", "M": _matlab_matrix(cols)})
    return json.dumps({"class": c, "v": "", "M": ""})


def _matlab_vec(values) -> str:
    return "[" + "; ".join(_fmt_scalar(x) for x in values) + "]"


def _matlab_matrix(cols) -> str:
    if not cols or not cols[0]:
        return "[]"
    n_rows = len(cols[0])
    rows = []
    for row_index in range(n_rows):
        rows.append(" ".join(_fmt_scalar(cols[col][row_index]) for col in range(len(cols))))
    return "[" + "; ".join(rows) + "]"


def _fmt_scalar(x) -> str:
    if isinstance(x, sp.Rational):
        if x.q == 1:
            return str(x.p)
        return f"{x.p}/{x.q}"
    if isinstance(x, sp.Expr):
        return sp.sstr(x)
    return str(x)


def _to_sym_matrix(rows) -> sp.Matrix:
    return sp.Matrix([[sp.nsimplify(c, rational=True) for c in row] for row in rows])


def _nullspace_basis(A_rows) -> list[list]:
    return [list(v) for v in _to_sym_matrix(A_rows).nullspace()]


def _columnspace_basis(A_rows) -> list[list]:
    return [list(v) for v in _to_sym_matrix(A_rows).columnspace()]


def _rowspace_basis(A_rows) -> list[list]:
    return [list(v.T) for v in _to_sym_matrix(A_rows).rowspace()]


def _solve_unique(A_rows, b_col) -> list:
    A = _to_sym_matrix(A_rows)
    b = sp.Matrix([sp.nsimplify(c, rational=True) for c in b_col])
    try:
        x = A.solve(b)
    except (sp.matrices.common.NonInvertibleMatrixError, sp.matrices.common.ShapeError):
        return _solve_particular(A_rows, b_col)
    return list(x)


def _solve_particular(A_rows, b_col) -> list:
    A = _to_sym_matrix(A_rows)
    b = sp.Matrix([sp.nsimplify(c, rational=True) for c in b_col])
    n = A.cols
    syms = sp.symbols(f"x0:{n}")
    sol_set = sp.linsolve((A, b), syms)
    if sol_set == sp.S.EmptySet:
        raise ValueError("system has no solution; classification was wrong")
    sol = next(iter(sol_set))
    free = set().union(*(sp.sympify(s).free_symbols for s in sol))
    subs = {s: 0 for s in free}
    return [sp.sympify(s).subs(subs) for s in sol]
