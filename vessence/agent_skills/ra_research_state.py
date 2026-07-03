"""State payload helpers for the RA research cron."""

from __future__ import annotations

from pathlib import Path
from typing import Any


ACTIVE_RESEARCH_STATUS = "active_until_chieh_stops_or_kathia_confirmed_asymptomatic"


def default_research_state(*, created_at: str, mission_statement: str) -> dict[str, Any]:
    return {
        "created_at": created_at,
        "processed_sources": {},
        "query_offsets": {},
        "last_report_sent_at": None,
        "last_report_source_count": 0,
        "initial_report_sent": False,
        "run_count": 0,
        "status": ACTIVE_RESEARCH_STATUS,
        "mission": mission_statement,
    }


def record_run_started(state: dict[str, Any], *, started_at: str, mission_statement: str) -> None:
    state["status"] = ACTIVE_RESEARCH_STATUS
    state["mission"] = mission_statement
    state["run_count"] = int(state.get("run_count", 0)) + 1
    state["last_run_started_at"] = started_at


def record_run_artifacts(
    state: dict[str, Any],
    *,
    finished_at: str,
    new_source_count: int,
    report_path: Path,
    html_report_path: Path,
    recommendation_path: Path,
    action_plan_path: Path,
    last_action_plan_path: Path,
    compressed_context_path: Path,
    discoveries_path: Path,
    run_cache_dir: Path,
    codex_path: Path | None,
    smart_provider: str,
    smart_model_label: str,
) -> None:
    state["last_run_finished_at"] = finished_at
    state["last_new_source_count"] = new_source_count
    state["last_report_path"] = str(report_path)
    state["last_html_report_path"] = str(html_report_path)
    state["recommendation_path"] = str(recommendation_path)
    state["action_plan_path"] = str(action_plan_path)
    state["last_action_plan_path"] = str(last_action_plan_path)
    state["compressed_context_path"] = str(compressed_context_path)
    state["discoveries_path"] = str(discoveries_path)
    state["last_run_cache_dir"] = str(run_cache_dir)
    state["last_codex_synthesis_path"] = str(codex_path) if codex_path else None
    state["smart_provider"] = smart_provider
    state["smart_model_label"] = smart_model_label


def record_delivery_result(
    state: dict[str, Any],
    *,
    report_notification_sent: bool,
    report_channel: str,
) -> bool:
    email_sent = report_notification_sent if report_channel == "email" else False
    state["last_email_sent_this_run"] = email_sent
    state["last_report_notification_sent_this_run"] = report_notification_sent
    state["last_report_channel"] = report_channel
    return email_sent


def run_result_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "new_sources": int(state.get("last_new_source_count", 0)),
        "total_sources": len(state.get("processed_sources", {})),
        "report_path": str(state.get("last_report_path", "")),
        "html_report_path": str(state.get("last_html_report_path", "")),
        "recommendation_path": str(state.get("recommendation_path", "")),
        "action_plan_path": str(state.get("action_plan_path", "")),
        "compressed_context_path": str(state.get("compressed_context_path", "")),
        "codex_synthesis_path": str(state.get("last_codex_synthesis_path") or ""),
        "email_sent": bool(state.get("last_email_sent_this_run")),
        "report_notification_sent": bool(state.get("last_report_notification_sent_this_run")),
        "report_channel": str(state.get("last_report_channel", "")),
        "run_count": int(state.get("run_count", 0)),
        "initial_report_sent": bool(state.get("initial_report_sent")),
    }
