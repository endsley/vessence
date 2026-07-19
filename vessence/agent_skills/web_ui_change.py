"""Detect broken website extraction contracts and recover them safely.

Browser automation should not quietly return an empty value after a vendor
changes its UI.  Call :func:`require_extraction_values` after a successful
parse and :func:`recover_website_ui_change` from the outer exception handler.
For a safe, read-only extraction, the latter captures a redacted incident,
runs the existing Codex-first repair runner synchronously, then re-execs the
original command once so it uses the repaired code.

The repair is deliberately *not* retried for actions that can change remote
state (sending messages, uploads, payments, submissions).  Those incidents
still receive a review, but require an operator to rerun the action.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlparse


VESSENCE_HOME = Path(os.environ.get("VESSENCE_HOME", "/home/chieh/ambient/vessence")).resolve()
VESSENCE_DATA_HOME = Path(os.environ.get("VESSENCE_DATA_HOME", "/home/chieh/ambient/vessence-data")).resolve()
PYTHON = os.environ.get("VESSENCE_PYTHON", "/home/chieh/google-adk-env/adk-venv/bin/python")
RECOVERY_ATTEMPT_ENV = "JANE_WEB_UI_RECOVERY_ATTEMPT"
AUTO_REPAIR_ENV = "JANE_WEB_UI_AUTO_REPAIR"
REPAIR_TIMEOUT_ENV = "JANE_WEB_UI_REPAIR_TIMEOUT_SEC"

_SAFE_SKILL_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,80}$")
_SENSITIVE_OR_EXTERNAL_RE = re.compile(
    r"\b(?:captcha|mfa|two[- ]factor|2fa|password|credential|secret|"
    r"unauthori[sz]ed|forbidden|access denied|connection|dns|certificate|"
    r"network(?: is)? unreachable|rate limit|too many requests)\b",
    re.IGNORECASE,
)
_UI_FAILURE_RE = re.compile(
    r"\b(?:selector|locator|element|control|button|input|dropdown|menu|"
    r"dialog|modal|tab|row|table|form|link|file input)\b.*\b(?:not found|"
    r"missing|not visible|not attached|timed out|failed)\b|"
    r"\b(?:could not|unable to|failed to|did not)\s+(?:find|locate|click|"
    r"open|select|submit|load)\b|"
    r"\bno\s+(?:[a-z]+\s+){0,3}(?:invoice\s+(?:id|links|controls)|"
    r"bill\s+rows|account\s+cards|document\s+selection\s+checkbox)\s+"
    r"(?:were\s+)?found\b|"
    r"\breceipt\s+click\s+did\s+not\s+yield\b|"
    r"\bunexpected\s+(?:[a-z-]+\s+)?response\b|"
    r"\b(?:timeout|timed out)\b.*\b(?:locator|selector|element|page|wait)\b",
    re.IGNORECASE,
)


class ExtractionContractError(RuntimeError):
    """A site response was syntactically valid but lacks required output."""

    def __init__(self, missing_paths: Iterable[str]) -> None:
        self.missing_paths = tuple(missing_paths)
        super().__init__("Required extracted values were missing: " + ", ".join(self.missing_paths))


@dataclass(frozen=True)
class UIChangeIncident:
    """Safe structural data about a review request; never contains page text."""

    skill: str
    intent: str
    operation: str
    reason: str
    incident_path: str = ""


def require_extraction_values(payload: Mapping[str, Any], required_paths: Iterable[str]) -> None:
    """Raise when any declared extraction-contract value is absent or empty.

    Paths use a dotted mapping syntax (for example ``"meta.final_url"``).
    Numeric zero and ``False`` are valid values; empty strings, collections,
    and ``None`` are failures.  An intentional empty search result must use a
    separate explicit success flag rather than declaring its result list as
    required.
    """
    missing: list[str] = []
    for path in required_paths:
        value: Any = payload
        for part in str(path).split("."):
            if not isinstance(value, Mapping) or part not in value:
                value = None
                break
            value = value[part]
        if value is None or value == "" or value == [] or value == {}:
            missing.append(str(path))
    if missing:
        raise ExtractionContractError(missing)


def require_record_values(
    records: Iterable[Mapping[str, Any]],
    required_fields: Iterable[str],
    *,
    label: str,
) -> None:
    """Require every returned record to contain the declared key fields.

    This catches markup changes that leave a nonempty row list but turn a key
    parsed field into ``None`` or an empty string.  The error reports only a
    structural path, never the row contents.
    """
    rows = list(records)
    if not rows:
        raise ExtractionContractError([label])
    missing: list[str] = []
    fields = tuple(str(field) for field in required_fields)
    for index, row in enumerate(rows):
        for field in fields:
            value = row.get(field)
            if value is None or value == "":
                missing.append(f"{label}[{index}].{field}")
    if missing:
        raise ExtractionContractError(missing)


def suspected_ui_change(exc: BaseException) -> bool:
    """Return whether this failure is evidence of UI/selector drift.

    Authentication, CAPTCHA, credentials, network outages, and invalid caller
    input are deliberately excluded: changing code cannot safely repair them.
    """
    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
        return False
    if isinstance(exc, ExtractionContractError):
        return True
    text = str(exc or "")
    class_name = type(exc).__name__.lower()
    # A missing password *field* is selector drift.  A missing password value
    # is a credential blocker.  Therefore test explicit UI wording first.
    if "timeout" in class_name and any(token in text.lower() for token in ("locator", "selector", "element", "page", "wait")):
        return True
    if _UI_FAILURE_RE.search(text):
        return True
    if _SENSITIVE_OR_EXTERNAL_RE.search(text):
        return False
    return False


def recover_website_ui_change(
    *,
    skill: str,
    intent: str,
    operation: str,
    exc: BaseException,
    project_root: str | Path,
    retry_safe: bool,
    restart: Callable[[], None] | None = None,
) -> UIChangeIncident | None:
    """Queue a Codex-first repair and re-run one safe extraction after repair.

    The durable incident intentionally carries only the skill contract,
    operation, exception class/reason code, and repository path.  It does not
    include page text, CLI arguments, cookies, downloaded documents, or error
    strings, any of which can contain private data.
    """
    if not suspected_ui_change(exc):
        return None
    if not _SAFE_SKILL_RE.fullmatch(skill):
        raise ValueError(f"invalid website skill identifier: {skill!r}")
    root = _validated_project_root(project_root)
    incident = _capture_incident(skill=skill, intent=intent, operation=operation, exc=exc, project_root=root)
    if incident is None:
        return None

    attempted = os.environ.get(RECOVERY_ATTEMPT_ENV, "0")
    if attempted != "0" or os.environ.get("JANE_SELF_HEAL_ACTIVE") == "1":
        return incident
    if os.environ.get(AUTO_REPAIR_ENV, "1").strip().lower() not in {"1", "true", "yes", "on"}:
        return incident
    if not incident.incident_path:
        return incident

    if not _run_codex_first_repair(Path(incident.incident_path), root):
        return incident
    if not retry_safe:
        return incident
    os.environ[RECOVERY_ATTEMPT_ENV] = "1"
    if restart is not None:
        restart()
    else:
        os.execv(sys.executable, [sys.executable, *sys.argv])
    return incident


def _capture_incident(
    *,
    skill: str,
    intent: str,
    operation: str,
    exc: BaseException,
    project_root: Path,
) -> UIChangeIncident | None:
    # Import lazily so pure validation functions stay lightweight and testable.
    from agent_skills.self_healing import capture_report

    reason = _reason_code(exc)
    payload = {
        "skill": skill,
        "operation": _safe_text(operation, 120),
        "intent": _safe_text(intent, 600),
        "reason": reason,
        "exception_class": type(exc).__name__,
        "repair_instruction": (
            "Review the current website UI against this skill's declared intent. "
            "Restore the same read-only extraction using the new UI, update the "
            "skill contract/selectors, verify the required values, then retry once."
        ),
    }
    result = capture_report(
        source=f"website_ui_{skill}",
        category="website_ui_change",
        message="A declared website extraction contract failed; review current UI and repair the skill.",
        payload=payload,
        project_root=project_root,
        tags=["website-ui", "selector-drift", "codex-review"],
        auto_repair=False,
    )
    if result is None:
        return None
    return UIChangeIncident(
        skill=skill,
        intent=intent,
        operation=operation,
        reason=reason,
        incident_path=str(result.get("incident_path") or ""),
    )


def _run_codex_first_repair(incident_path: Path, project_root: Path) -> bool:
    timeout = _positive_int_env(REPAIR_TIMEOUT_ENV, 2100)
    allowed = _allowed_roots_env(project_root)
    env = {
        **os.environ,
        "VESSENCE_HOME": str(VESSENCE_HOME),
        "VESSENCE_DATA_HOME": str(VESSENCE_DATA_HOME),
        "PYTHONPATH": str(VESSENCE_HOME),
        "JANE_SELF_HEAL_ACTIVE": "1",
        "JANE_SELF_HEAL_PROJECT_ROOTS": allowed,
    }
    try:
        completed = subprocess.run(
            [PYTHON, str(VESSENCE_HOME / "agent_skills" / "self_healing_repair.py"), "--incident", str(incident_path)],
            cwd=str(project_root),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0 and _repair_finished(incident_path)


def _repair_finished(incident_path: Path) -> bool:
    try:
        data = json.loads(incident_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return data.get("status") == "repair_finished"


def _reason_code(exc: BaseException) -> str:
    if isinstance(exc, ExtractionContractError):
        return "required_value_missing"
    text = str(exc or "").lower()
    if "timeout" in text or "timeout" in type(exc).__name__.lower():
        return "selector_timeout"
    if any(token in text for token in ("selector", "locator", "element", "control")):
        return "selector_missing"
    return "ui_navigation_failed"


def _safe_text(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())[:limit]
    # Do not put URLs with query strings (often contain tokens) into incidents.
    return re.sub(r"https?://[^\s?]+\?[^\s]+", "[url-with-query-redacted]", text)


def _validated_project_root(value: str | Path) -> Path:
    root = Path(value).expanduser().resolve()
    defaults = {
        VESSENCE_HOME,
        Path("/home/chieh/ambient/jane-codex-skills").resolve(),
        Path("/home/chieh/code/waterlily").resolve(),
    }
    configured = {Path(part).expanduser().resolve() for part in os.environ.get("JANE_WEB_UI_REPAIR_ROOTS", "").split(":") if part}
    if root not in defaults | configured:
        raise ValueError(f"website UI repair root is not allowlisted: {root}")
    return root


def _allowed_roots_env(project_root: Path) -> str:
    values = [item for item in os.environ.get("JANE_SELF_HEAL_PROJECT_ROOTS", "").split(":") if item]
    canonical = str(project_root)
    if canonical not in values:
        values.append(canonical)
    return ":".join(values)


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        value = default
    return max(1, value)


__all__ = [
    "ExtractionContractError",
    "UIChangeIncident",
    "recover_website_ui_change",
    "require_record_values",
    "require_extraction_values",
    "suspected_ui_change",
]
