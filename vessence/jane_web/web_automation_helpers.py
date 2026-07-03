"""Pure helpers for web automation API routes."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def web_plan_raw_steps(body: Mapping[str, Any]) -> list[Any]:
    raw_steps = body.get("steps") or []
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError("'steps' must be a non-empty array")
    return raw_steps


def web_plan_step_specs(raw_steps: list[Any]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for index, step in enumerate(raw_steps):
        if not isinstance(step, dict) or "action" not in step:
            raise ValueError(f"step {index} malformed — need dict with 'action'")
        specs.append(
            {
                "action": str(step["action"]),
                "args": step.get("args") or {},
                "confirm": bool(step.get("confirm", False)),
            }
        )
    return specs


def web_plan_label(body: Mapping[str, Any]) -> str:
    return str(body.get("label") or "adhoc")[:40]


def web_plan_headless(body: Mapping[str, Any]) -> bool | None:
    headless = body.get("headless")
    return headless if isinstance(headless, bool) else None


def web_plan_record_trace(body: Mapping[str, Any]) -> bool:
    return bool(body.get("record_trace", False))


def web_plan_profile_id(body: Mapping[str, Any]) -> str | None:
    profile_id = body.get("profile_id")
    if isinstance(profile_id, str) and profile_id.strip():
        return profile_id
    return None


def automation_result_payload(result: Any) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "run_id": result.run_id,
        "summary": result.summary,
        "data": result.data,
    }


def web_profile_create_values(body: Mapping[str, Any]) -> tuple[str, str]:
    name = (body.get("display_name") or "").strip()
    domain = (body.get("domain") or "").strip()
    return (name, domain)


def web_profile_capture_values(body: Mapping[str, Any]) -> tuple[str, str, int]:
    login_url = (body.get("login_url") or "").strip()
    success_pattern = (body.get("success_url_pattern") or "").strip()
    timeout_s = int(body.get("timeout_s") or 300)
    return (login_url, success_pattern, timeout_s)


def web_secret_create_values(body: Mapping[str, Any]) -> tuple[str, str, Any, Any, Any]:
    domain = (body.get("domain") or "").strip()
    label = (body.get("label") or "").strip()
    username = body.get("username") or ""
    password = body.get("password") or ""
    notes = body.get("notes") or ""
    return (domain, label, username, password, notes)


def web_secret_public_entry(entry: Any) -> dict[str, Any]:
    return {
        "secret_id": entry.secret_id,
        "domain": entry.domain,
        "label": entry.label,
        "created_at": entry.created_at,
        "last_used": entry.last_used,
    }
