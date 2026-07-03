"""Validation and issue helpers for the education homework auditor."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def validate_audit_mode(mode: str, *, reuse_attempt: bool) -> None:
    if mode not in ("full-grade", "audit-only"):
        raise ValueError(f"mode must be full-grade or audit-only, got {mode!r}")
    if reuse_attempt and mode != "audit-only":
        raise ValueError("--reuse-attempt requires --mode audit-only")


def validate_local_base_url(base_url: str, *, db_port: int) -> None:
    parsed = urlparse(base_url)
    if parsed.hostname in ("localhost", "127.0.0.1", "::1"):
        return
    raise RuntimeError(
        f"refusing to run against {base_url!r}: DB connection is hardcoded "
        f"to localhost:{db_port}; aborting to avoid cross-env attempt-id "
        f"confusion. Tunnel the remote DB through 127.0.0.1:{db_port} if "
        f"you really mean to audit a remote env."
    )


def auto_answer_unsupported_issue(exc: BaseException) -> dict[str, str]:
    return {
        "severity": "med",
        "kind": "auto_answer_unsupported",
        "message": f"{type(exc).__name__}: {exc}",
    }


def grader_canonical_mismatch_issue(submitted: Any, feedback_text: str | None) -> dict[str, str]:
    return {
        "severity": "high",
        "kind": "grader_canonical_mismatch",
        "message": (
            f"Grader rejected the canonical solution. "
            f"Submitted {submitted!r}; feedback: {feedback_text}"
        ),
    }


def unreliable_verdict_issue(verdict: str) -> dict[str, str]:
    return {
        "severity": "high",
        "kind": f"verdict_{verdict}",
        "message": (
            f"Submission verdict was {verdict!r} (concurrent "
            f"writer? attempt locked? unexpected response?) "
            f"— audit data for this question is unreliable."
        ),
    }
