from pathlib import Path

from agent_skills import ra_research_cron
from agent_skills.ra_research_state import (
    ACTIVE_RESEARCH_STATUS,
    default_research_state,
    record_delivery_result,
    record_run_artifacts,
    record_run_started,
    run_result_payload,
)


def test_ra_research_cron_uses_state_helpers():
    assert ra_research_cron._default_research_state is default_research_state
    assert ra_research_cron._record_run_started is record_run_started
    assert ra_research_cron._record_run_artifacts is record_run_artifacts
    assert ra_research_cron._record_delivery_result is record_delivery_result
    assert ra_research_cron._run_result_payload is run_result_payload


def test_default_research_state_preserves_contract_shape():
    assert default_research_state(created_at="now", mission_statement="mission") == {
        "created_at": "now",
        "processed_sources": {},
        "query_offsets": {},
        "last_report_sent_at": None,
        "last_report_source_count": 0,
        "initial_report_sent": False,
        "run_count": 0,
        "status": ACTIVE_RESEARCH_STATUS,
        "mission": "mission",
    }


def test_record_run_started_preserves_status_and_increment_behavior():
    state = {"run_count": "4", "status": "old", "mission": "old"}

    record_run_started(state, started_at="start", mission_statement="new mission")

    assert state["status"] == ACTIVE_RESEARCH_STATUS
    assert state["mission"] == "new mission"
    assert state["run_count"] == 5
    assert state["last_run_started_at"] == "start"


def test_run_artifacts_delivery_and_payload_preserve_result_contract():
    state = {"processed_sources": {"a": {}, "b": {}}, "run_count": 7, "initial_report_sent": True}

    record_run_artifacts(
        state,
        finished_at="finish",
        new_source_count=3,
        report_path=Path("/vault/report.md"),
        html_report_path=Path("/vault/report.html"),
        recommendation_path=Path("/vault/recommendation.md"),
        action_plan_path=Path("/vault/action-plan.md"),
        last_action_plan_path=Path("/vault/action-plan-run.md"),
        compressed_context_path=Path("/vault/context.md"),
        discoveries_path=Path("/vault/discoveries.md"),
        run_cache_dir=Path("/data/cache/run"),
        codex_path=None,
        smart_provider="codex",
        smart_model_label="frontier",
    )
    email_sent = record_delivery_result(state, report_notification_sent=True, report_channel="app")

    assert email_sent is False
    assert state["last_codex_synthesis_path"] is None
    assert state["last_action_plan_path"] == "/vault/action-plan-run.md"
    assert state["smart_provider"] == "codex"
    assert run_result_payload(state) == {
        "new_sources": 3,
        "total_sources": 2,
        "report_path": "/vault/report.md",
        "html_report_path": "/vault/report.html",
        "recommendation_path": "/vault/recommendation.md",
        "action_plan_path": "/vault/action-plan.md",
        "compressed_context_path": "/vault/context.md",
        "codex_synthesis_path": "",
        "email_sent": False,
        "report_notification_sent": True,
        "report_channel": "app",
        "run_count": 7,
        "initial_report_sent": True,
    }


def test_email_delivery_result_maps_notification_to_email_flag():
    state = {}

    email_sent = record_delivery_result(state, report_notification_sent=True, report_channel="email")

    assert email_sent is True
    assert run_result_payload(state)["email_sent"] is True
