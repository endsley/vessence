"""Report delivery decision and payload helpers for RA research cron."""

from __future__ import annotations

import datetime as dt
import textwrap
from typing import Any


def parse_iso_datetime(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except Exception:
        return None


def should_send_report(
    state: dict[str, Any],
    force: bool,
    *,
    now: dt.datetime,
    initial_report_after_runs: int,
    report_interval_hours: int,
    parse_iso_fn=parse_iso_datetime,
) -> bool:
    if force:
        return True
    run_count = int(state.get("run_count", 0))
    if not state.get("initial_report_sent"):
        return run_count >= initial_report_after_runs
    last = parse_iso_fn(state.get("last_report_sent_at"))
    if last is None:
        return run_count >= initial_report_after_runs
    return (now - last) >= dt.timedelta(hours=report_interval_hours)


def app_report_message(new_count: int, total_sources: int) -> str:
    if new_count == 1:
        source_phrase = "1 new/upgraded source summary"
    else:
        source_phrase = f"{new_count} new/upgraded source summaries"
    return f"{source_phrase}; {total_sources} cached sources total. Tap to read the HTML report."


def normalize_report_channel(channel: str | None) -> str:
    normalized = (channel or "app").strip().lower()
    if normalized in {"email", "gmail"}:
        return "email"
    if normalized in {"none", "off", "disabled"}:
        return "disabled"
    return "app"


def build_app_report_payload(
    *,
    report_id: str,
    report_path: Any,
    html_report_path: Any,
    new_count: int,
    total_sources: int,
    created_at: str,
) -> dict[str, Any]:
    return {
        "id": f"ra_report_{report_id}",
        "type": "report_ready",
        "report_kind": "ra_research",
        "title": "RA research update ready",
        "message": app_report_message(new_count, total_sources),
        "created_at": created_at,
        "timestamp": created_at,
        "final": True,
        "report_id": report_id,
        "report_url": f"/api/research/ra/reports/{report_id}.html",
        "web_url": f"/research/ra/reports/{report_id}",
        "markdown_path": str(report_path),
        "html_path": str(html_report_path),
        "new_sources": new_count,
        "total_sources": total_sources,
    }


def mark_app_report_sent(
    state: dict[str, Any],
    *,
    created_at: str,
    total_sources: int,
    html_report_path: Any,
) -> None:
    state["last_report_sent_at"] = created_at
    state["last_report_source_count"] = total_sources
    state["initial_report_sent"] = True
    state["last_report_error"] = None
    state["last_report_channel"] = "app"
    state["last_html_report_path"] = str(html_report_path)


def email_report_subject(date_label: str) -> str:
    return f"RA research update: remission/asymptomatic evidence ({date_label})"


def build_email_report_body(
    *,
    processed_count: int,
    report_path: Any,
    recommendation_path: Any,
    action_plan_path: Any,
    action_plan_text: str,
    recommendation_text: str,
) -> str:
    return textwrap.dedent(
        f"""\
        Chieh,

        The RA remission research cron is still running. It has processed and cached {processed_count} sources so far.

        Latest report:
        {report_path}

        Latest living recommendation scheme:
        {recommendation_path}

        Latest action plan:
        {action_plan_path}

        Action plan snapshot:

        {action_plan_text[:12000]}

        Research scheme snapshot:

        {recommendation_text[:6000]}

        Safety boundary: this is a research dossier for discussion with Kathia and her rheumatologist, not medical advice. Medication, supplement, or treatment changes should not be made from this report alone.
        """
    ).strip()


def mark_email_report_sent(state: dict[str, Any], *, sent_at: str, processed_count: int) -> None:
    state["last_report_sent_at"] = sent_at
    state["last_report_source_count"] = processed_count
    state["initial_report_sent"] = True
    state["last_report_error"] = None
