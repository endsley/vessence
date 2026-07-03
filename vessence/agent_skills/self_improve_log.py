"""self_improve_log.py — shared vocal-summary writer for self-improve jobs.

Each nightly self-improvement job can call `log_vocal_summary()` to record a
short, TTS-friendly 1-3 sentence summary of what it did. Jane reads these
summaries when the user asks "what did you fix last night" or similar.

Storage: $VESSENCE_DATA_HOME/self_improve_vocal_log.jsonl
Format: one JSON object per line:
    {
        "timestamp": ISO-8601 UTC,
        "job": "<job name>",
        "summary": "<1-3 sentence spoken-friendly summary>",
        "severity": "critical|medium|low|info",
        "what_was_wrong": "<one sentence>",
        "why_it_mattered": "<one sentence>",
        "what_was_done": "<one sentence>",
    }

The summary field is a pre-composed vocal response (what Jane will speak);
the three structured fields support richer rendering if a consumer wants
to recompose it. Either "summary" alone OR the three structured fields
must be present.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
from pathlib import Path

from agent_skills.self_improve_log_helpers import (
    SEVERITIES as _SEVERITIES,
    TIMESTAMP_FORMAT as _TIMESTAMP_FORMAT,
    build_vocal_summary_record as _build_vocal_summary_record,
    recent_summaries_from_lines as _recent_summaries_from_lines,
)

logger = logging.getLogger(__name__)

_VESSENCE_DATA_HOME = Path(os.environ.get(
    "VESSENCE_DATA_HOME",
    str(Path.home() / "ambient" / "vessence-data"),
))
VOCAL_LOG_PATH = _VESSENCE_DATA_HOME / "self_improve_vocal_log.jsonl"


def log_vocal_summary(
    job: str,
    *,
    summary: str | None = None,
    what_was_wrong: str | None = None,
    why_it_mattered: str | None = None,
    what_was_done: str | None = None,
    severity: str = "info",
) -> None:
    """Append a single vocal-summary entry to the log.

    Call this AFTER successfully making a change so Jane can answer
    questions like "what did you fix last night". Keep each field to a
    SINGLE sentence — this is meant for TTS, not a written report. No
    code, no jargon, no symbols like `()` or `[]`.

    Args:
        job: Short name of the job (e.g. "Transcript Review").
        summary: Full pre-composed 1-3 sentence vocal summary. If given,
            the structured fields are optional.
        what_was_wrong: One-sentence plain description of the problem.
        why_it_mattered: One-sentence plain description of user impact.
        what_was_done: One-sentence plain description of the fix.
        severity: "critical" | "medium" | "low" | "info".
    """
    timestamp = dt.datetime.utcnow().strftime(_TIMESTAMP_FORMAT)
    record = _build_vocal_summary_record(
        job,
        timestamp=timestamp,
        summary=summary,
        what_was_wrong=what_was_wrong,
        why_it_mattered=why_it_mattered,
        what_was_done=what_was_done,
        severity=severity,
    )
    if record is None:
        logger.warning("log_vocal_summary: empty summary for job=%r — skipping", job)
        return

    VOCAL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with VOCAL_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    logger.info("self_improve_log: recorded [%s] %s — %s",
                record["severity"], job, record["summary"][:100])


def read_recent_summaries(
    days: int = 7,
    limit: int | None = 30,
) -> list[dict]:
    """Return the most recent vocal-summary entries.

    Args:
        days: Look back this many days from now (default 7).
        limit: Cap the number returned (default 30). None for no cap.

    Returns newest-first.
    """
    if not VOCAL_LOG_PATH.exists():
        return []
    cutoff = dt.datetime.utcnow() - dt.timedelta(days=days)
    with VOCAL_LOG_PATH.open(encoding="utf-8") as f:
        return _recent_summaries_from_lines(f, cutoff=cutoff, limit=limit)
