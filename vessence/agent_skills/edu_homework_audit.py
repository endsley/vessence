"""Homework auditor for classes.chiehwu.com (chieh_class_v2 FastAPI app).

Logs in as a student via the dev-login bypass, starts an attempt on a
homework assignment, walks every question, submits the canonical answer
(read straight out of `attempts.question_seeds` JSON), and emits a Markdown
audit report flagging unrendered Jinja, unbalanced math delimiters, common
typos, grader/canonical-solution disagreement, and other content issues.

Two modes:

    full-grade  (default)  — start, render, submit, finish; report includes
                              live grader verdicts and final score.
    audit-only             — start, render, lint; do NOT submit or finish.
                              The unfinished attempt is deleted from the DB
                              after the run so it doesn't block real students.

Auth: GET /dev-login?email=<student> on a server with ALLOW_DEV_LOGIN=true.
DB:   reads MySQL via the cloud-sql-proxy at 127.0.0.1:3307 (root password
      from Secret Manager). The DB connection is teacher-grade — used only
      to read snapshot solutions and to clean up audit attempts.

Reproduces the Codex-discovered approach (May 2026 transcript) without the
system-Chrome+CDP dance: dev-login eliminates the OAuth wall entirely.

Usage
-----
    python edu_homework_audit.py --section 33 --hw 1
    python edu_homework_audit.py --section 33 --hw 2 --mode audit-only
    python edu_homework_audit.py --section 33 --hw 1 --student juliaprocess@gmail.com

    # Audit a homework someone is currently working on without disturbing
    # their in-flight answers (forces audit-only):
    python edu_homework_audit.py --section 33 --hw 2 --student chieh.t.wu@gmail.com \
        --mode audit-only --reuse-attempt

Output
------
    Markdown report at $VESSENCE_DATA_HOME/audit_reports/edu_<section>_<hw>_<ts>.md
    plus a JSON sidecar with the structured findings.
"""
from __future__ import annotations

import argparse
import dataclasses as dc
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import pymysql
import sympy as sp
from bs4 import BeautifulSoup

# claude_cli_llm lives next to this skill — used for the optional
# conceptual-review pass.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from claude_cli_llm import completion_json  # noqa: E402
    _LLM_AVAILABLE = True
except Exception:
    _LLM_AVAILABLE = False


DEFAULT_BASE_URL = "http://localhost:8501"
DEFAULT_STUDENT = "juliaprocess@gmail.com"
DB_HOST = "127.0.0.1"
DB_PORT = 3307
DB_NAME = "teaching_app"
DB_USER = "root"
DB_PASSWORD_SECRET = "TEACHING_APP_DB_ROOT_PASSWORD"


# ---------------------------------------------------------------------------
# Solution → form-response formatting (mirrors the JS in question.html)
# ---------------------------------------------------------------------------

def format_response(answer_type: str | None, solution: Any) -> str:
    """Convert a snapshot.solution into the string the answer form expects.

    The shapes mirror app/templates/student/question.html and the comparator
    inputs in app/services/grading.py. Raises ValueError for unsupported
    answer types — caller should catch and skip-with-warning.
    """
    at = answer_type or ""

    if at in ("", "number", "math_expression", "fraction", "text"):
        return str(solution)

    if at == "multiple_choice":
        return str(solution)

    if at == "vector":
        return _matlab_vec(solution)

    if at == "subspace_basis":
        # The snapshot's `solution` carries (A, dim, kind); the answer is
        # *any* basis of that subspace. Compute one with sympy.
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

    if at == "linear_system_solve":
        # snapshot.solution: {A, b, v, classification}. For "unique" the
        # `v` field holds the precomputed solution. For "infinite" the
        # form expects ANY particular solution (any v with A·v = b) — we
        # compute one with sympy. For "none" the v textarea is disabled
        # by the page JS, so we leave it blank.
        c = solution["classification"]
        if c == "unique":
            v_str = _matlab_vec(solution.get("v") or [])
        elif c == "infinite":
            v_str = _matlab_vec(_solve_particular(solution["A"], solution["b"]))
        else:  # "none"
            v_str = ""
        return json.dumps({"class": c, "v": v_str})

    if at == "classify_and_reach":
        return json.dumps({
            "class": solution["classification"],
            "reach": "yes" if solution.get("reachable") else "no",
        })

    if at == "invertibility_with_blank":
        # Snapshot solution shape: {"invertible": bool, "blank": str|None}
        # — see app/problems/Matrix_inverses/helpers.py.
        is_inv = bool(solution.get("invertible"))
        c = "invertible" if is_inv else "not_invertible"
        blank = "" if not is_inv else str(solution.get("blank") or "")
        return json.dumps({"class": c, "blank": blank})

    if at == "solve_system_with_basis":
        # Snapshot carries (A, b, classification, nullity). Answer is computed.
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

    raise ValueError(f"Unsupported answer_type for auto-answer: {at!r}")


def _matlab_vec(values) -> str:
    return "[" + "; ".join(_fmt_scalar(x) for x in values) + "]"


def _matlab_matrix(cols) -> str:
    if not cols or not cols[0]:
        return "[]"
    n_rows = len(cols[0])
    rows = []
    for r in range(n_rows):
        rows.append(" ".join(_fmt_scalar(cols[c][r]) for c in range(len(cols))))
    return "[" + "; ".join(rows) + "]"


def _fmt_scalar(x) -> str:
    """Format a scalar for the MATLAB-style answer field. Sympy Rationals
    become `a/b`; ints stay int; everything else falls through to str()."""
    if isinstance(x, sp.Rational):
        if x.q == 1:
            return str(x.p)
        return f"{x.p}/{x.q}"
    if isinstance(x, sp.Expr):
        # Simplified expression; use sympy printing.
        return sp.sstr(x)
    return str(x)


def _to_sym_matrix(rows) -> sp.Matrix:
    """Build a sympy Matrix from a list-of-lists, preserving exact rationals."""
    return sp.Matrix([[sp.nsimplify(c, rational=True) for c in row] for row in rows])


def _nullspace_basis(A_rows) -> list[list]:
    return [list(v) for v in _to_sym_matrix(A_rows).nullspace()]


def _columnspace_basis(A_rows) -> list[list]:
    return [list(v) for v in _to_sym_matrix(A_rows).columnspace()]


def _rowspace_basis(A_rows) -> list[list]:
    # rowspace() returns 1-row Matrix objects; transpose each to a column.
    return [list(v.T) for v in _to_sym_matrix(A_rows).rowspace()]


def _solve_unique(A_rows, b_col) -> list:
    A = _to_sym_matrix(A_rows)
    b = sp.Matrix([sp.nsimplify(c, rational=True) for c in b_col])
    try:
        x = A.solve(b)
    except (sp.matrices.common.NonInvertibleMatrixError, sp.matrices.common.ShapeError):
        # Fall back to linsolve — covers non-square but consistent systems
        # and surfaces "system is actually inconsistent" via ValueError below.
        return _solve_particular(A_rows, b_col)
    return list(x)


def _solve_particular(A_rows, b_col) -> list:
    """Find one solution to A·x = b. Underdetermined systems are fine — we
    pick the solution with all free parameters set to 0."""
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


# ---------------------------------------------------------------------------
# Static prompt linting
# ---------------------------------------------------------------------------

_TYPOS = {
    "recieve": "receive",
    "seperate": "separate",
    "occured": "occurred",
    "lenghth": "length",
    "definately": "definitely",
    "thier": "their",
    "untill": "until",
    "wich": "which",
    "begining": "beginning",
    "accomodate": "accommodate",
    "occurence": "occurrence",
    "neccessary": "necessary",
    "compatable": "compatible",
    "calender": "calendar",
    "consistant": "consistent",
    "independant": "independent",
    "dependant": "dependent",
    "existant": "existent",
    "noticable": "noticeable",
}


def lint_prompt(prompt_html: str, prompt_text: str) -> list[dict]:
    """Run cheap content checks on a question's prompt.

    `prompt_html` is the raw `qa.snapshot.prompt_latex` (HTML + LaTeX inline);
    `prompt_text` is the visible text after BeautifulSoup-stripping. We use
    `prompt_html` for delimiter checks (LaTeX lives in HTML) and `prompt_text`
    for typo / length checks.
    """
    issues: list[dict] = []

    # 1. Unrendered Jinja delimiters (template never got rendered).
    if "{{" in prompt_html or "{%" in prompt_html:
        issues.append({
            "severity": "high",
            "kind": "unrendered_jinja",
            "message": "Prompt contains unrendered Jinja delimiters ({{ or {%)",
        })

    # 2. Unbalanced inline math `$...$`. We strip $$...$$ blocks first.
    stripped = re.sub(r"\$\$.*?\$\$", "", prompt_html, flags=re.DOTALL)
    n_dollars = stripped.count("$")
    if n_dollars % 2 != 0:
        issues.append({
            "severity": "high",
            "kind": "unbalanced_math",
            "message": f"Odd number of `$` delimiters ({n_dollars} unpaired)",
        })

    # 3. Brace balance check (very rough; LaTeX uses {} heavily so we only
    #    flag a clearly suspicious ratio).
    opens = prompt_html.count("{")
    closes = prompt_html.count("}")
    if abs(opens - closes) > 2:
        issues.append({
            "severity": "med",
            "kind": "brace_mismatch",
            "message": f"Brace imbalance: {opens} `{{` vs {closes} `}}`",
        })

    # 4. Common typos in the visible text.
    low = prompt_text.lower()
    for bad, good in _TYPOS.items():
        if re.search(rf"\b{re.escape(bad)}\b", low):
            issues.append({
                "severity": "med",
                "kind": "typo",
                "message": f"Likely typo: '{bad}' -> '{good}'",
            })

    # 5. Suspiciously short prompt (renderer probably swallowed the body).
    if len(prompt_text.strip()) < 15:
        issues.append({
            "severity": "med",
            "kind": "short_prompt",
            "message": f"Prompt is only {len(prompt_text.strip())} visible chars",
        })

    # 6. Author markers leaking through.
    if re.search(r"\b(TODO|FIXME|XXX|HACK)\b", prompt_html):
        issues.append({
            "severity": "med",
            "kind": "marker",
            "message": "Prompt contains TODO/FIXME/XXX/HACK marker",
        })

    # 7. LaTeX math not wrapped in `$`. If we see `\frac`, `\sum`, etc.
    #    *outside* a `$...$` span and outside a `\begin{...}\end{...}`
    #    display-math environment, MathJax won't render it.
    no_math = re.sub(r"\$[^$]*\$", "", stripped)
    no_math = re.sub(r"\\begin\{[^}]+\}.*?\\end\{[^}]+\}", "", no_math, flags=re.DOTALL)
    if re.search(r"\\(frac|sum|prod|int|sqrt)\b", no_math):
        issues.append({
            "severity": "med",
            "kind": "unwrapped_latex",
            "message": "LaTeX command appears outside `$...$` (won't render)",
        })

    # 8. Stray Python `repr()` artifacts (e.g. "Fraction(1, 2)" -> renderer
    #    leaked the Python object instead of formatting it).
    if re.search(r"\bFraction\(\s*-?\d+,\s*-?\d+\s*\)", prompt_html):
        issues.append({
            "severity": "high",
            "kind": "fraction_repr_leak",
            "message": "Prompt contains a `Fraction(a, b)` Python repr — renderer didn't format it",
        })

    return issues


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _gcloud_secret(name: str) -> str:
    out = subprocess.run(
        ["gcloud", "secrets", "versions", "access", "latest", f"--secret={name}"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def db_connect():
    pwd = _gcloud_secret(DB_PASSWORD_SECRET)
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=pwd,
        database=DB_NAME, autocommit=True,
    )


def fetch_attempt_seeds(conn, attempt_id: int) -> list[dict]:
    cur = conn.cursor()
    cur.execute("SELECT question_seeds FROM attempts WHERE id = %s", (attempt_id,))
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"attempt {attempt_id} not found")
    return json.loads(row[0])


def fetch_attempt_summary(conn, attempt_id: int) -> dict:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, account_id, course_id, assignment_id, started_at, "
        "finished_at, score FROM attempts WHERE id = %s",
        (attempt_id,),
    )
    keys = ["id", "account_id", "course_id", "assignment_id",
            "started_at", "finished_at", "score"]
    row = cur.fetchone()
    return dict(zip(keys, row)) if row else {}


def find_open_attempt(conn, account_id: int, course_id: int, assignment_id: int) -> int | None:
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM attempts WHERE account_id = %s AND course_id = %s "
        "AND assignment_id = %s AND finished_at IS NULL "
        "ORDER BY id DESC LIMIT 1",
        (account_id, course_id, assignment_id),
    )
    row = cur.fetchone()
    return int(row[0]) if row else None


def delete_attempt(conn, attempt_id: int, *, account_id: int,
                   max_age_hours: int = 1) -> bool:
    """Delete an attempt — but ONLY if it belongs to the named account AND
    was started within `max_age_hours`. Returns True if a row was deleted.

    The age guard is a belt-and-suspenders safeguard: the audit student
    (juliaprocess) is by convention only used by this tool, but if a real
    student session were ever opened on that account, we don't want this
    cleanup to blow away their in-progress work.
    """
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM attempts WHERE id = %s AND account_id = %s "
        "AND finished_at IS NULL "
        "AND started_at >= (NOW() - INTERVAL %s HOUR)",
        (attempt_id, account_id, max_age_hours),
    )
    return cur.rowcount > 0


def lookup_account_id(conn, email: str) -> int:
    cur = conn.cursor()
    cur.execute("SELECT id FROM accounts WHERE email = %s", (email,))
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"no account with email {email!r}")
    return int(row[0])


def lookup_assignment_meta(conn, assignment_id: int) -> dict:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, course_id, kind, title FROM assignments WHERE id = %s",
        (assignment_id,),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError(f"assignment {assignment_id} not found")
    return {"id": row[0], "course_id": row[1], "kind": row[2], "title": row[3]}


def lookup_section_label(conn, section_id: int) -> str:
    cur = conn.cursor()
    cur.execute(
        "SELECT course_number, section_id, semester_year FROM class WHERE id = %s",
        (section_id,),
    )
    row = cur.fetchone()
    if not row:
        return f"section #{section_id}"
    return f"{row[0]} / {row[1]} / {row[2]}"


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

class EduClient:
    """Thin httpx wrapper that handles dev-login + CSRF for chieh_class_v2."""

    def __init__(self, base_url: str, student_email: str):
        self.base_url = base_url.rstrip("/")
        self.student_email = student_email
        self.client = httpx.Client(
            base_url=self.base_url,
            follow_redirects=False,
            timeout=15.0,
        )

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    @property
    def csrf_token(self) -> str | None:
        return self.client.cookies.get("csrf")

    def _csrf_headers(self) -> dict:
        tok = self.csrf_token
        return {"X-CSRF-Token": tok} if tok else {}

    def login(self) -> None:
        # The first GET also seeds the `csrf` cookie via middleware.
        r = self.client.get(f"/dev-login?email={self.student_email}")
        if r.status_code not in (302, 303, 307):
            raise RuntimeError(
                f"dev-login returned {r.status_code} (is ALLOW_DEV_LOGIN=true?)"
            )
        loc = r.headers.get("location", "")
        # The route only sets the session cookie on success. The redirect
        # target on failure is `"/"` (with no session set); on success it
        # is `/courses` for students, `/teach/...` for teachers, etc.
        if loc == "/" or loc.endswith("/login"):
            raise RuntimeError(
                f"dev-login redirected to {loc!r} — wrong email or dev-login disabled?"
            )
        if not self.client.cookies.get("session"):
            raise RuntimeError(
                "dev-login completed but no `session` cookie was set"
            )

    def start_attempt(self, section_id: int, assignment_id: int) -> int:
        r = self.client.post(
            f"/courses/{section_id}/hw/{assignment_id}/start",
            headers=self._csrf_headers(),
        )
        if r.status_code in (302, 303, 307):
            loc = r.headers.get("location", "")
            m = re.search(r"/attempt/(\d+)/q/0", loc)
            if m:
                return int(m.group(1))
            raise RuntimeError(f"start redirected to unexpected URL: {loc!r}")
        if r.status_code == 409:
            raise OpenAttemptExists()
        raise RuntimeError(f"start_attempt failed: HTTP {r.status_code}: {r.text[:200]}")

    def get_question_html(self, attempt_id: int, n: int) -> str:
        r = self.client.get(f"/attempt/{attempt_id}/q/{n}")
        if r.status_code != 200:
            raise RuntimeError(f"GET q{n} failed: {r.status_code}")
        return r.text

    def submit_answer(self, attempt_id: int, n: int, response: str,
                      client_version: int) -> str:
        r = self.client.post(
            f"/attempt/{attempt_id}/q/{n}/answer",
            data={"response": response, "client_version": client_version},
            headers=self._csrf_headers(),
        )
        if r.status_code != 200:
            raise RuntimeError(
                f"submit q{n} failed: {r.status_code}: {r.text[:200]}"
            )
        return r.text

    def finish(self, attempt_id: int) -> None:
        r = self.client.post(
            f"/attempt/{attempt_id}/finish",
            headers=self._csrf_headers(),
        )
        if r.status_code not in (302, 303, 307):
            raise RuntimeError(f"finish failed: {r.status_code}: {r.text[:200]}")


class OpenAttemptExists(Exception):
    pass


# ---------------------------------------------------------------------------
# Page parsers
# ---------------------------------------------------------------------------

def parse_prompt_from_question(html: str) -> tuple[str, str]:
    """Returns (raw_prompt_html, visible_text)."""
    soup = BeautifulSoup(html, "html.parser")
    div = soup.select_one("div.prompt")
    if not div:
        return "", ""
    raw_html = div.decode_contents()
    text = div.get_text(" ", strip=True)
    return raw_html, text


def parse_client_version(html: str) -> int:
    soup = BeautifulSoup(html, "html.parser")
    el = soup.select_one('input[name="client_version"]')
    if not el:
        return 0
    try:
        return int(el.get("value") or 0)
    except ValueError:
        return 0


def parse_answer_result(html: str) -> dict:
    """Parse the HTMX fragment returned after submitting an answer."""
    soup = BeautifulSoup(html, "html.parser")
    fb = soup.select_one("div.feedback")
    if not fb:
        return {"verdict": "unknown", "feedback_text": "", "displayed_response": None}
    classes = fb.get("class") or []
    text = fb.get_text(" ", strip=True)
    if "ok" in classes:
        verdict = "correct"
    elif "warn" in classes:
        verdict = "stale" if "already submitted" in text else "locked"
    elif "bad" in classes:
        verdict = "incorrect"
    else:
        verdict = "unknown"
    return {
        "verdict": verdict,
        "feedback_text": text,
        "displayed_response": _extract_displayed_response(fb),
    }


# Known answer_type identifiers — if any of these appear in the rendered
# "Your answer: <code>X</code>" slot, the `student_response` Jinja filter
# (or its caller) is broken and the answer-type name is leaking into the
# UI as the student's answer. See the 2026-05-10 filter-arg-swap bug.
_ANSWER_TYPE_NAMES = frozenset({
    "number", "text", "math_expression", "fraction", "multiple_choice",
    "vector", "subspace_basis", "linear_system_solve", "classify_and_reach",
    "invertibility_with_blank", "solve_system_with_basis",
})


def _extract_displayed_response(feedback_div) -> str | None:
    """Pull the rendered student-response text from a feedback panel.

    The templates render lines like `Your answer: <code>X</code>` or
    `You answered <code>X</code>`. We grab the first `<code>` immediately
    following such an introducer; returns None if no introducer is present
    (e.g. the simple `Correct.` panel for non-composite types in older
    template versions).
    """
    text = feedback_div.get_text(" ", strip=True)
    introducers = ("Your answer:", "You answered")
    if not any(intro in text for intro in introducers):
        return None
    for code in feedback_div.find_all("code"):
        prev = code.find_previous(string=True)
        if not prev:
            continue
        prev_str = str(prev)
        if any(intro in prev_str for intro in introducers):
            return code.get_text(strip=True)
    # Fallback: first <code> in the panel.
    first = feedback_div.find("code")
    return first.get_text(strip=True) if first else None


def lint_displayed_response(displayed: str | None, submitted: str | None,
                            answer_type: str) -> list[dict]:
    """Catch UI bugs where the rendered "Your answer:" doesn't reflect what
    the student actually submitted."""
    issues: list[dict] = []
    if displayed is None:
        return issues
    if displayed in _ANSWER_TYPE_NAMES:
        issues.append({
            "severity": "high",
            "kind": "displayed_response_is_answer_type",
            "message": (
                f"Rendered 'Your answer: {displayed}' is the literal "
                f"answer-type identifier — the student_response filter is "
                f"swallowing the response and showing the type instead "
                f"(check Jinja filter call signature)."
            ),
        })
    if submitted and displayed.strip() == "":
        issues.append({
            "severity": "med",
            "kind": "displayed_response_empty",
            "message": (
                f"Rendered 'Your answer:' is empty but the student submitted "
                f"{submitted!r} — display layer dropped the value."
            ),
        })
    if submitted and displayed.strip().lower() == "(none)" and submitted.strip():
        issues.append({
            "severity": "high",
            "kind": "displayed_response_none",
            "message": (
                f"Rendered 'Your answer: (none)' but the student submitted "
                f"{submitted!r} — display layer is treating a real response "
                f"as empty."
            ),
        })
    return issues


# ---------------------------------------------------------------------------
# Audit driver
# ---------------------------------------------------------------------------

@dc.dataclass
class QuestionFinding:
    n: int
    key: str
    answer_type: str
    solution: Any
    submitted_response: str | None
    verdict: str | None
    feedback_text: str | None
    prompt_text: str
    prompt_html: str
    issues: list[dict]
    error: str | None = None


_LLM_REVIEW_INSTRUCTIONS = """\
You are auditing a math homework assignment for clarity and correctness.
The course is undergraduate linear algebra at Northeastern University. The
prompts use LaTeX inside `$...$` and `$$...$$` (and `\\begin{align*}...`).

For each numbered prompt, return findings about:
  - factual or mathematical errors (severity: high)
  - internally contradictory wording (high)
  - missing information needed to solve (high)
  - ambiguous or unclear phrasing (med)
  - awkward or confusing wording (med)
  - real spelling/grammar mistakes (med) — IGNORE LaTeX commands and
    variable names; do not flag mathematical notation as a typo
  - minor stylistic suggestions (low)

DO NOT flag: valid LaTeX, MATLAB-style vector notation like [2; -1; 0],
single-letter variables, Greek letters, or correct math conventions.

Output ONLY a JSON object of the form:
{"reviews": [{"n": <int>, "issues": [{"severity": "high|med|low", "kind": "<short>", "message": "<one sentence>"}, ...]}, ...]}

If a prompt has no issues, return its entry with `"issues": []`.
Include an entry for every prompt in numeric order.

PROMPTS:
"""


def llm_conceptual_review(findings, *, model_tier: str = "agent",
                          timeout: int = 240,
                          batch_size: int = 10) -> dict[int, list[dict]]:
    """Batched LLM conceptual review.

    Splits ``findings`` into chunks of ``batch_size`` and issues one call
    per chunk; results are merged into a single ``{question_n: [issue,...]}``
    dict. Smaller batches keep each call comfortably under the per-call
    timeout (the previous "one shot for all 20 prompts" version was
    timing out around 240s on 20 prompts).

    Per-chunk failures degrade gracefully: the failed range is recorded
    under the synthetic key ``-1`` as a ``llm_batch_error`` issue tied to
    the lowest question number in that batch, and remaining chunks still
    run. The caller catches a fully-empty result by checking for any
    populated entries.
    """
    if not _LLM_AVAILABLE:
        raise RuntimeError("claude_cli_llm not importable")
    if batch_size < 1:
        raise ValueError(f"batch_size must be >= 1, got {batch_size}")

    out: dict[int, list[dict]] = {}
    errors: list[str] = []

    for start in range(0, len(findings), batch_size):
        chunk = findings[start:start + batch_size]
        if not chunk:
            continue
        parts = [_LLM_REVIEW_INSTRUCTIONS]
        for f in chunk:
            text = (f.prompt_text or "").strip()
            if not text:
                text = "<EMPTY PROMPT>"
            parts.append(f"\n[Q{f.n}] (key={f.key}, type={f.answer_type or 'default'})\n{text}\n")
        prompt = "".join(parts)

        try:
            raw = completion_json(prompt, tier=model_tier, timeout=timeout)
        except Exception as exc:
            qs = ", ".join(str(f.n) for f in chunk)
            errors.append(f"batch [{qs}] failed: {exc}")
            continue

        for entry in raw.get("reviews", []):
            n = entry.get("n")
            if n is None:
                continue
            issues = []
            for i in entry.get("issues", []) or []:
                sev = i.get("severity") or "low"
                kind = i.get("kind") or "llm_review"
                msg = i.get("message") or ""
                if not msg:
                    continue
                issues.append({
                    "severity": sev,
                    "kind": f"llm_{kind}",
                    "message": msg,
                })
            out[int(n)] = issues

    if errors and not out:
        # Every chunk failed — surface the first error so the caller's
        # graceful-degrade message is informative.
        raise RuntimeError("; ".join(errors))
    if errors:
        # Partial failure: stash a synthetic note so the report shows it.
        out.setdefault(-1, []).append({
            "severity": "low",
            "kind": "llm_partial_failure",
            "message": "; ".join(errors),
        })
    return out


def run_audit(*, base_url: str, student_email: str, section_id: int,
              assignment_id: int, mode: str,
              llm_review: bool = True,
              llm_tier: str = "agent",
              reuse_attempt: bool = False) -> dict:
    if mode not in ("full-grade", "audit-only"):
        raise ValueError(f"mode must be full-grade or audit-only, got {mode!r}")
    if reuse_attempt and mode != "audit-only":
        # Reusing the user's in-progress row means we must not submit on their
        # behalf or finish the attempt — otherwise we'd overwrite their answers
        # and lock them out of their own work.
        raise ValueError("--reuse-attempt requires --mode audit-only")

    # The DB is hardcoded to the local proxied teaching_app. Refuse to run
    # against a non-local base-url so that attempt_id correlation can't
    # accidentally cross environments (Codex review, 2026-05-10).
    parsed = urlparse(base_url)
    if parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise RuntimeError(
            f"refusing to run against {base_url!r}: DB connection is hardcoded "
            f"to localhost:{DB_PORT}; aborting to avoid cross-env attempt-id "
            f"confusion. Tunnel the remote DB through 127.0.0.1:{DB_PORT} if "
            f"you really mean to audit a remote env."
        )

    conn = db_connect()
    attempt_id: int | None = None
    account_id: int | None = None
    cleanup_attempt = False  # set True for audit-only after we own the row

    try:
        account_id = lookup_account_id(conn, student_email)
        meta = lookup_assignment_meta(conn, assignment_id)
        section_label = lookup_section_label(conn, section_id)

        with EduClient(base_url, student_email) as client:
            client.login()

            # Resume or start. Three paths:
            #   1) --reuse-attempt: attach to an existing open row, do NOT
            #      delete it, do NOT submit/finish, do NOT clean up at the
            #      end. The user is mid-attempt and we're just reading.
            #   2) Default: if a prior open attempt exists, delete it
            #      (audit student only, recent rows only — see delete_attempt)
            #      and start fresh so we get current snapshots.
            if reuse_attempt:
                attempt_id = find_open_attempt(
                    conn, account_id, section_id, assignment_id,
                )
                if attempt_id is None:
                    raise RuntimeError(
                        f"--reuse-attempt: no open attempt found for "
                        f"account={account_id} section={section_id} "
                        f"assignment={assignment_id}. Start an attempt in the "
                        f"browser first, or drop --reuse-attempt to start one."
                    )
                cleanup_attempt = False
            else:
                existing = find_open_attempt(
                    conn, account_id, section_id, assignment_id,
                )
                if existing is not None:
                    deleted = delete_attempt(
                        conn, existing, account_id=account_id, max_age_hours=24,
                    )
                    if not deleted:
                        raise RuntimeError(
                            f"refusing to clean up open attempt {existing}: "
                            f"older than 24h or owned by a different account. "
                            f"Manually finish or delete it before re-running."
                        )

                try:
                    attempt_id = client.start_attempt(section_id, assignment_id)
                except OpenAttemptExists:
                    attempt_id = find_open_attempt(
                        conn, account_id, section_id, assignment_id,
                    )
                    if attempt_id is None:
                        raise RuntimeError("409 from /start but no open attempt visible")
                cleanup_attempt = (mode == "audit-only")

            seeds = fetch_attempt_seeds(conn, attempt_id)
            findings: list[QuestionFinding] = []

            for n, qa in enumerate(seeds):
                snap = qa.get("snapshot", {})
                key = snap.get("key", "<unknown>")
                answer_type = snap.get("answer_type") or ""
                solution = snap.get("solution")

                try:
                    qhtml = client.get_question_html(attempt_id, n)
                except Exception as exc:
                    findings.append(QuestionFinding(
                        n=n, key=key, answer_type=answer_type, solution=solution,
                        submitted_response=None, verdict=None, feedback_text=None,
                        prompt_text="", prompt_html="", issues=[],
                        error=f"GET failed: {exc}",
                    ))
                    continue

                prompt_html, prompt_text = parse_prompt_from_question(qhtml)
                client_version = parse_client_version(qhtml)
                issues = lint_prompt(prompt_html, prompt_text)

                submitted, verdict, feedback_text, err = None, None, None, None
                if mode == "full-grade":
                    try:
                        submitted = format_response(answer_type, solution)
                    except (ValueError, KeyError, TypeError) as exc:
                        err = f"format unsupported: {exc}"
                        issues.append({
                            "severity": "med",
                            "kind": "auto_answer_unsupported",
                            "message": f"{type(exc).__name__}: {exc}",
                        })
                    else:
                        try:
                            rhtml = client.submit_answer(
                                attempt_id, n, submitted, client_version,
                            )
                            result = parse_answer_result(rhtml)
                            verdict = result["verdict"]
                            feedback_text = result["feedback_text"]
                            issues.extend(lint_displayed_response(
                                result.get("displayed_response"),
                                submitted, answer_type,
                            ))
                        except Exception as exc:
                            err = f"submit failed: {exc}"

                    # Canonical solution rejected by grader = real bug.
                    if verdict == "incorrect":
                        issues.append({
                            "severity": "high",
                            "kind": "grader_canonical_mismatch",
                            "message": (
                                f"Grader rejected the canonical solution. "
                                f"Submitted {submitted!r}; feedback: {feedback_text}"
                            ),
                        })
                    # Stale / locked / unknown verdicts mean the audit data
                    # for this question is unreliable; flag explicitly so the
                    # report doesn't quietly degrade.
                    elif verdict in ("stale", "locked", "unknown"):
                        issues.append({
                            "severity": "high",
                            "kind": f"verdict_{verdict}",
                            "message": (
                                f"Submission verdict was {verdict!r} (concurrent "
                                f"writer? attempt locked? unexpected response?) "
                                f"— audit data for this question is unreliable."
                            ),
                        })

                findings.append(QuestionFinding(
                    n=n, key=key, answer_type=answer_type, solution=solution,
                    submitted_response=submitted, verdict=verdict,
                    feedback_text=feedback_text, prompt_text=prompt_text,
                    prompt_html=prompt_html, issues=issues, error=err,
                ))

            if mode == "full-grade":
                client.finish(attempt_id)
                # Successful finish — nothing to clean up.
                cleanup_attempt = False

        # Optional conceptual review (single batched LLM call).
        llm_error = None
        if llm_review:
            try:
                review = llm_conceptual_review(findings, model_tier=llm_tier)
                for f in findings:
                    extra = review.get(f.n, [])
                    if extra:
                        f.issues.extend(extra)
            except Exception as exc:
                llm_error = f"LLM review skipped: {exc}"

        summary = fetch_attempt_summary(conn, attempt_id)
        if llm_error:
            summary["llm_review_error"] = llm_error

        # Audit-only: don't leave an open attempt blocking future runs.
        if cleanup_attempt:
            deleted = delete_attempt(
                conn, attempt_id, account_id=account_id, max_age_hours=24,
            )
            summary["cleaned_up"] = deleted
            cleanup_attempt = False  # already handled

        return {
            "section_id": section_id,
            "section_label": section_label,
            "assignment": meta,
            "student_email": student_email,
            "account_id": account_id,
            "attempt_id": attempt_id,
            "mode": mode,
            "summary": summary,
            "findings": [dc.asdict(f) for f in findings],
        }

    finally:
        # Belt-and-suspenders: if the audit raised mid-loop and we own a
        # live attempt row, clean it up so we don't block future runs.
        if cleanup_attempt and attempt_id is not None and account_id is not None:
            try:
                delete_attempt(
                    conn, attempt_id, account_id=account_id, max_age_hours=24,
                )
            except Exception:
                pass
        conn.close()


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def write_report(report: dict, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"edu_audit_s{report['section_id']}_a{report['assignment']['id']}_{ts}"
    md_path = out_dir / f"{stem}.md"
    json_path = out_dir / f"{stem}.json"

    findings = report["findings"]
    n_total = len(findings)
    n_correct = sum(1 for f in findings if f["verdict"] == "correct")
    n_issues = sum(len(f["issues"]) for f in findings)
    n_high = sum(1 for f in findings for i in f["issues"] if i["severity"] == "high")
    score = report["summary"].get("score")

    lines: list[str] = []
    lines.append(f"# HW Audit — {report['section_label']} · "
                 f"{report['assignment']['title']} (assignment #{report['assignment']['id']})")
    lines.append("")
    lines.append(f"- Mode: **{report['mode']}**")
    lines.append(f"- Student: `{report['student_email']}` (account {report['account_id']})")
    lines.append(f"- Attempt: `{report['attempt_id']}`")
    if report["mode"] == "full-grade":
        lines.append(f"- Score: **{score}** ({n_correct}/{n_total} correct)")
    lines.append(f"- Issues flagged: **{n_issues}** ({n_high} high-severity)")
    if report["summary"].get("llm_review_error"):
        lines.append(f"- LLM review: SKIPPED — {report['summary']['llm_review_error']}")
    lines.append("")

    # Summary table.
    lines.append("## Per-question summary")
    lines.append("")
    lines.append("| # | Key | Type | Verdict | Issues |")
    lines.append("|---|---|---|---|---|")
    for f in findings:
        verdict = f["verdict"] or "—"
        if verdict == "correct":
            verdict_cell = "OK"
        elif verdict == "incorrect":
            verdict_cell = "**WRONG**"
        else:
            verdict_cell = verdict
        n_iss = len(f["issues"])
        iss_cell = "—" if n_iss == 0 else (
            "**" + str(n_iss) + "**"
            if any(i["severity"] == "high" for i in f["issues"])
            else str(n_iss)
        )
        lines.append(
            f"| {f['n']} | `{f['key']}` | {f['answer_type'] or 'default'} "
            f"| {verdict_cell} | {iss_cell} |"
        )
    lines.append("")

    # Detailed sections (only for questions with issues OR errors).
    flagged = [f for f in findings if f["issues"] or f["error"]]
    if flagged:
        lines.append("## Flagged questions")
        lines.append("")
        for f in flagged:
            lines.append(f"### Q{f['n']} — `{f['key']}` ({f['answer_type'] or 'default'})")
            lines.append("")
            lines.append("**Prompt (visible text):**")
            lines.append("")
            lines.append("> " + (f["prompt_text"][:500] or "<empty>"))
            lines.append("")
            lines.append(f"- Canonical solution: `{json.dumps(f['solution'])}`")
            if f["submitted_response"] is not None:
                lines.append(f"- Submitted: `{f['submitted_response']}`")
            if f["verdict"]:
                lines.append(f"- Verdict: **{f['verdict']}**")
            if f["feedback_text"]:
                lines.append(f"- Server feedback: {f['feedback_text']}")
            if f["error"]:
                lines.append(f"- Error: `{f['error']}`")
            if f["issues"]:
                lines.append("- Issues:")
                for i in f["issues"]:
                    lines.append(f"  - **[{i['severity']}/{i['kind']}]** {i['message']}")
            lines.append("")

    md_path.write_text("\n".join(lines))
    json_path.write_text(json.dumps(report, default=str, indent=2))
    return md_path, json_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--section", type=int, required=True,
                        help="Section ID (the `class.id` row, e.g. 33 = DS3000-S26)")
    parser.add_argument("--hw", "--assignment", dest="assignment", type=int, required=True,
                        help="Assignment ID (the `assignments.id` row)")
    parser.add_argument("--student", default=DEFAULT_STUDENT,
                        help=f"Student email for dev-login (default: {DEFAULT_STUDENT})")
    parser.add_argument("--mode", choices=["full-grade", "audit-only"],
                        default="full-grade",
                        help="full-grade submits + finishes; audit-only just renders + lints")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL,
                        help=f"Server base URL (default: {DEFAULT_BASE_URL})")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="Output directory for reports "
                             "(default: $VESSENCE_DATA_HOME/audit_reports)")
    parser.add_argument("--no-llm-review", action="store_true",
                        help="Skip the LLM conceptual-review pass")
    parser.add_argument("--llm-tier", choices=["utility", "agent"],
                        default="agent",
                        help="LLM tier for conceptual review (default: agent)")
    parser.add_argument("--reuse-attempt", action="store_true",
                        help="Attach to the student's currently open attempt "
                             "instead of deleting + starting fresh. Forces "
                             "--mode audit-only so we never overwrite their "
                             "in-flight answers or finish for them. Use this "
                             "when auditing a homework you (or a student) are "
                             "actively working on.")
    args = parser.parse_args()

    if args.reuse_attempt and args.mode == "full-grade":
        # Surface the conflict at the CLI rather than as a deep RuntimeError.
        parser.error("--reuse-attempt requires --mode audit-only")

    out_dir = args.out_dir
    if out_dir is None:
        data_home = os.environ.get("VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data"))
        out_dir = Path(data_home) / "audit_reports"

    report = run_audit(
        base_url=args.base_url,
        student_email=args.student,
        section_id=args.section,
        assignment_id=args.assignment,
        mode=args.mode,
        llm_review=not args.no_llm_review,
        llm_tier=args.llm_tier,
        reuse_attempt=args.reuse_attempt,
    )
    md_path, json_path = write_report(report, out_dir)

    n_total = len(report["findings"])
    n_correct = sum(1 for f in report["findings"] if f["verdict"] == "correct")
    n_high = sum(1 for f in report["findings"]
                 for i in f["issues"] if i["severity"] == "high")
    score = report["summary"].get("score")

    print(f"Wrote report: {md_path}")
    print(f"Wrote JSON  : {json_path}")
    if report["mode"] == "full-grade":
        print(f"Score: {score} ({n_correct}/{n_total} correct)")
    print(f"High-severity issues: {n_high}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
