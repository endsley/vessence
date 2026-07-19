import datetime as dt
from pathlib import Path
from types import SimpleNamespace

from agent_skills import self_healing
from agent_skills.self_healing_helpers import (
    auto_repair_launch_decision,
    build_self_heal_job_markdown,
    env_flag_enabled,
    fingerprint,
    first_stack_frame,
    incident_requests_critical_auto_repair,
    incident_dedupe_result,
    incident_id,
    incident_json_path,
    incident_title_text,
    jsonable,
    new_incident_fingerprint_record,
    redacted_request_headers,
    self_heal_job_context_lines,
    self_heal_job_llm_fallback_section,
    self_heal_job_path,
    self_heal_job_steps_section,
    self_heal_job_title,
    self_heal_job_verification_section,
    should_auto_repair,
    slugify,
)


def test_self_healing_uses_extracted_helpers():
    assert self_healing._auto_repair_launch_decision is auto_repair_launch_decision
    assert self_healing._fingerprint is fingerprint
    assert self_healing._first_stack_frame is first_stack_frame
    assert self_healing._incident_id is incident_id
    assert self_healing._incident_requests_critical_auto_repair is incident_requests_critical_auto_repair
    assert self_healing._slugify is slugify
    assert self_healing._jsonable is jsonable
    assert self_healing._build_self_heal_job_markdown is build_self_heal_job_markdown
    assert self_healing._incident_json_path is incident_json_path
    assert self_healing._self_heal_job_path is self_heal_job_path
    assert self_healing._incident_dedupe_result is incident_dedupe_result
    assert self_healing._new_incident_fingerprint_record is new_incident_fingerprint_record


def test_env_flags_and_auto_repair_defaults():
    assert env_flag_enabled({}, "MISSING")
    assert not env_flag_enabled({"FLAG": "off"}, "FLAG")
    assert should_auto_repair(True, {"JANE_SELF_HEAL_AUTO_REPAIR": "0"})
    assert not should_auto_repair(None, {"JANE_SELF_HEAL_AUTO_REPAIR": "false"})


def test_auto_repair_launch_decision_updates_state_and_preserves_limits() -> None:
    now = dt.datetime(2026, 7, 2, 12, 0, tzinfo=dt.timezone.utc)
    state: dict = {}

    assert auto_repair_launch_decision(
        state,
        now=now,
        max_per_day=2,
        cooldown_sec=60,
    ) == "launch"
    assert state["auto_repair_day"] == "2026-07-02"
    assert state["auto_repair_count"] == 1
    assert state["last_auto_repair_at"] == now.isoformat()

    assert auto_repair_launch_decision(
        state,
        now=now + dt.timedelta(seconds=30),
        max_per_day=2,
        cooldown_sec=60,
    ) == "cooldown"
    assert state["auto_repair_count"] == 1

    assert auto_repair_launch_decision(
        state,
        now=now + dt.timedelta(seconds=90),
        max_per_day=2,
        cooldown_sec=60,
    ) == "launch"
    assert state["auto_repair_count"] == 2

    assert auto_repair_launch_decision(
        state,
        now=now + dt.timedelta(seconds=180),
        max_per_day=2,
        cooldown_sec=60,
    ) == "daily_cap"

    assert auto_repair_launch_decision(
        state,
        now=now + dt.timedelta(days=1),
        max_per_day=2,
        cooldown_sec=60,
    ) == "launch"
    assert state["auto_repair_day"] == "2026-07-03"
    assert state["auto_repair_count"] == 1


def test_incident_requests_critical_auto_repair_from_payload_or_tag() -> None:
    assert incident_requests_critical_auto_repair({
        "payload": {"auto_repair_priority": "critical"},
        "tags": [],
    })
    assert incident_requests_critical_auto_repair({
        "payload": {},
        "tags": ["waterlily", "Critical-Auto-Repair"],
    })
    assert not incident_requests_critical_auto_repair({
        "payload": {"auto_repair_priority": "normal"},
        "tags": ["waterlily"],
    })


def test_redacted_request_headers_keeps_visible_headers_and_secrets_redacted():
    headers = {
        "Authorization": "secret",
        "X-Trace": "x" * 600,
        "User-Agent": "browser",
        "Accept": "ignored",
    }

    assert redacted_request_headers(headers) == {
        "Authorization": "[redacted]",
        "X-Trace": "x" * 500,
        "User-Agent": "browser",
    }


def test_request_info_from_request_uses_header_redaction():
    request = SimpleNamespace(
        method="GET",
        url=SimpleNamespace(path="/api/test", query="a=1"),
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"Cookie": "secret", "Host": "example.test"},
    )

    assert self_healing.request_info_from_request(request) == {
        "method": "GET",
        "path": "/api/test",
        "query": "a=1",
        "client": "127.0.0.1",
        "headers": {"Cookie": "[redacted]", "Host": "example.test"},
    }


def test_stack_fingerprint_slug_and_incident_id_helpers():
    assert first_stack_frame("noise\n  File \"/tmp/a.py\", line 1\nmore") == (
        'File "/tmp/a.py", line 1'
    )
    assert len(fingerprint("a", "", "b")) == 24
    assert slugify("Jane Web/API!", 8) == "jane_web"
    assert slugify("!!!") == "incident"
    assert incident_id("Jane Web/API!", "abc123") == "jane_web_api_abc123"


def test_self_healing_incident_and_job_path_helpers_preserve_formats():
    incident = {
        "created_at": "2026-07-02T12:34:56+00:00",
        "id": "jane_web_abc123",
        "source": "Jane Web/API!",
        "category": "Runtime Exception",
    }

    assert incident_json_path(Path("/data/incidents"), incident) == (
        Path("/data/incidents") / "20260702T123456+0000_jane_web_abc123.json"
    )
    assert self_heal_job_path(Path("/repo/configs/job_queue"), 7, incident) == (
        Path("/repo/configs/job_queue") / "job_007_self_heal_jane_web_api_runtime_exception.md"
    )


def test_incident_dedupe_result_updates_existing_record_inside_rate_limit():
    incident = {"created_at": "2026-07-02T12:01:00+00:00"}
    record = {
        "last_seen_ts": 100.0,
        "count": 2,
        "incident_path": "/data/incidents/one.json",
        "job_path": "/repo/job.md",
        "first_seen_at": "2026-07-02T12:00:00+00:00",
    }

    result = incident_dedupe_result(
        record,
        incident,
        now_ts=150.0,
        rate_limit_sec=900,
    )

    assert result["deduped"] is True
    assert result["count"] == 3
    assert result["record"] == {
        **record,
        "last_seen_at": "2026-07-02T12:01:00+00:00",
        "last_seen_ts": 150.0,
        "count": 3,
    }
    assert result["incident_updates"] == {
        "deduped": True,
        "occurrence_count": 3,
        "incident_path": "/data/incidents/one.json",
        "job_path": "/repo/job.md",
    }


def test_incident_record_helpers_preserve_new_occurrence_state():
    incident = {
        "created_at": "2026-07-02T12:10:00+00:00",
        "occurrence_count": 4,
        "source": "jane_web",
        "category": "exception",
    }

    assert incident_dedupe_result(
        {"last_seen_ts": 100.0, "count": 3},
        incident,
        now_ts=2000.0,
        rate_limit_sec=900,
    ) == {"deduped": False, "count": 4}

    record = new_incident_fingerprint_record(
        {"first_seen_at": "2026-07-01T00:00:00+00:00"},
        incident,
        now_ts=2000.0,
        incident_path=Path("/data/incidents/two.json"),
        job_path=Path("/repo/job.md"),
    )

    assert record == {
        "first_seen_at": "2026-07-01T00:00:00+00:00",
        "last_seen_at": "2026-07-02T12:10:00+00:00",
        "last_seen_ts": 2000.0,
        "count": 4,
        "incident_path": "/data/incidents/two.json",
        "job_path": "/repo/job.md",
        "source": "jane_web",
        "category": "exception",
    }


def test_incident_title_and_jsonable_helpers():
    exception_incident = {
        "category": "exception",
        "request": {"path": "/api/chat"},
        "exception": {"type": "ValueError", "top_frame": "file.py:1:fn"},
    }
    report_incident = {
        "category": "android",
        "message": "Boom",
        "payload": {"exception_class": "IllegalStateException"},
    }

    assert incident_title_text(exception_incident) == "ValueError at /api/chat"
    assert incident_title_text(report_incident) == "IllegalStateException"
    assert jsonable({"date": dt.date(2026, 7, 2)}) == {"date": "2026-07-02"}


def test_self_heal_job_section_helpers_preserve_markdown_contract():
    incident = {
        "source": "jane_web",
        "category": "exception",
        "project_root": "/repo",
        "fingerprint": "abc123",
        "request": {"path": "/api/chat"},
        "exception": {"type": "ValueError", "top_frame": "file.py:1"},
    }

    assert self_heal_job_title(incident) == "Self-heal jane_web: ValueError at /api/chat"
    assert self_heal_job_context_lines(incident, default_project_root="/default") == [
        "## Context",
        "- Source: `jane_web`",
        "- Category: `exception`",
        "- Project root: `/repo`",
        "- Fingerprint: `abc123`",
        "- Request path: `/api/chat`",
    ]
    assert self_heal_job_context_lines(
        {"source": "worker", "category": "report", "request": {}},
        default_project_root="/default",
    )[3] == "- Project root: `/default`"
    assert self_heal_job_steps_section(Path("/data/incidents/incident.json")).startswith(
        "## Steps\n1. Read the incident JSON at `/data/incidents/incident.json`"
    )
    assert "Do not speculate from the stack trace alone." in self_heal_job_steps_section(
        Path("/data/incidents/incident.json")
    )
    assert "Codex/OpenAI first" in self_heal_job_llm_fallback_section()
    assert "Claude Code next" in self_heal_job_llm_fallback_section()
    assert "Vessence repair-failure notice" in self_heal_job_llm_fallback_section()
    assert "Antigravity CLI" not in self_heal_job_llm_fallback_section()
    assert self_heal_job_verification_section().endswith(
        "leave a clear report explaining the blocker and evidence checked."
    )


def test_build_self_heal_job_markdown_preserves_job_contract():
    incident = {
        "source": "jane_web",
        "category": "exception",
        "project_root": "/repo",
        "fingerprint": "abc123",
        "request": {"path": "/api/chat"},
        "exception": {"type": "ValueError", "top_frame": "file.py:1"},
    }

    body = build_self_heal_job_markdown(
        incident,
        Path("/data/incidents/incident.json"),
        created_date=dt.date(2026, 7, 2),
        default_project_root="/default",
    )

    assert body.startswith("# Job: Self-heal jane_web: ValueError at /api/chat\n")
    assert "Status: pending\nPriority: high\nCreated: 2026-07-02" in body
    assert "Incident: /data/incidents/incident.json" in body
    assert "- Project root: `/repo`" in body
    assert "- Fingerprint: `abc123`" in body
    assert "Do not speculate from the stack trace alone." in body
    assert "Codex/OpenAI first" in body
    assert "Claude Code next" in body
    assert "Vessence repair-failure notice" in body
    assert "Antigravity CLI" not in body
    assert body.endswith("leave a clear report explaining the blocker and evidence checked.\n")
