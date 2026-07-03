"""Pure helpers for self_healing.py."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any


SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "x-csrf-token",
    "x-jane-self-heal-token",
    "x-api-key",
}

VISIBLE_HEADER_NAMES = {"host", "referer", "user-agent", "content-type"}
DISABLED_VALUES = {"0", "false", "no", "off"}


def env_flag_enabled(environ: Mapping[str, str], name: str, default: str = "1") -> bool:
    return environ.get(name, default).strip().lower() not in DISABLED_VALUES


def should_auto_repair(auto_repair: bool | None, environ: Mapping[str, str]) -> bool:
    if auto_repair is not None:
        return auto_repair
    return env_flag_enabled(environ, "JANE_SELF_HEAL_AUTO_REPAIR", "1")


def auto_repair_launch_decision(
    state: dict[str, Any],
    *,
    now: datetime,
    max_per_day: int,
    cooldown_sec: int,
) -> str:
    """Update auto-repair state and return launch, daily_cap, or cooldown."""
    today = now.date().isoformat()
    day = state.setdefault("auto_repair_day", today)
    if day != today:
        state["auto_repair_day"] = today
        state["auto_repair_count"] = 0

    count = int(state.get("auto_repair_count") or 0)
    if count >= max_per_day:
        return "daily_cap"

    last = float(state.get("last_auto_repair_ts") or 0)
    now_ts = now.timestamp()
    if last and now_ts - last < cooldown_sec:
        return "cooldown"

    state["last_auto_repair_ts"] = now_ts
    state["last_auto_repair_at"] = now.isoformat()
    state["auto_repair_count"] = count + 1
    return "launch"


def redacted_request_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    redacted = {}
    for key, value in headers.items():
        lower_key = key.lower()
        if lower_key in SENSITIVE_HEADER_NAMES:
            redacted[key] = "[redacted]"
        elif lower_key.startswith("x-") or lower_key in VISIBLE_HEADER_NAMES:
            redacted[key] = str(value)[:500]
    return redacted


def first_stack_frame(stack: str) -> str:
    for line in stack.splitlines():
        clean = line.strip()
        if clean.startswith("at ") or clean.startswith("File "):
            return clean[:240]
    return ""


def fingerprint(*parts: str) -> str:
    joined = "\n".join(str(part or "") for part in parts)
    return hashlib.sha256(joined.encode("utf-8", errors="replace")).hexdigest()[:24]


def slugify(value: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return (slug[:max_len] or "incident").strip("_") or "incident"


def incident_id(source: str, incident_fingerprint: str) -> str:
    return f"{slugify(source, 32)}_{incident_fingerprint}"


def incident_json_path(incident_dir: Path, incident: dict[str, Any]) -> Path:
    created = str(incident["created_at"]).replace(":", "").replace("-", "")
    return Path(incident_dir) / f"{created}_{incident['id']}.json"


def self_heal_job_path(job_queue_dir: Path, job_number: int, incident: dict[str, Any]) -> Path:
    source = slugify(str(incident.get("source", "unknown")), 28)
    category = slugify(str(incident.get("category", "incident")), 24)
    return Path(job_queue_dir) / f"job_{job_number:03d}_self_heal_{source}_{category}.md"


def incident_dedupe_result(
    record: Mapping[str, Any],
    incident: dict[str, Any],
    *,
    now_ts: float,
    rate_limit_sec: int,
) -> dict[str, Any]:
    last_seen = float(record.get("last_seen_ts") or 0)
    count = int(record.get("count") or 0) + 1
    if last_seen and now_ts - last_seen < rate_limit_sec:
        updated_record = dict(record)
        updated_record.update({
            "last_seen_at": incident["created_at"],
            "last_seen_ts": now_ts,
            "count": count,
        })
        return {
            "deduped": True,
            "count": count,
            "record": updated_record,
            "incident_updates": {
                "deduped": True,
                "occurrence_count": count,
                "incident_path": record.get("incident_path"),
                "job_path": record.get("job_path"),
            },
        }
    return {"deduped": False, "count": count}


def new_incident_fingerprint_record(
    existing_record: Mapping[str, Any],
    incident: dict[str, Any],
    *,
    now_ts: float,
    incident_path: Path,
    job_path: Path,
) -> dict[str, Any]:
    return {
        "first_seen_at": existing_record.get("first_seen_at") or incident["created_at"],
        "last_seen_at": incident["created_at"],
        "last_seen_ts": now_ts,
        "count": incident["occurrence_count"],
        "incident_path": str(incident_path),
        "job_path": str(job_path),
        "source": incident["source"],
        "category": incident["category"],
    }


def incident_title_text(incident: dict[str, Any]) -> str:
    if incident.get("category") == "exception":
        exc = incident.get("exception", {})
        return (
            f"{exc.get('type', 'Exception')} at "
            f"{incident.get('request', {}).get('path', '') or exc.get('top_frame', '')}"
        )
    payload = incident.get("payload", {})
    return str(payload.get("exception_class") or incident.get("message") or incident.get("category"))[:120]


def build_self_heal_job_markdown(
    incident: dict[str, Any],
    incident_path: Path,
    *,
    created_date: date,
    default_project_root: Path | str,
) -> str:
    title = f"Self-heal {incident.get('source', 'unknown')}: {incident_title_text(incident)}"
    project_root = incident.get("project_root") or str(default_project_root)
    return f"""# Job: {title}
Status: pending
Priority: high
Created: {created_date.isoformat()}
Auto-generated: true
Source: jane_self_healing
Incident: {incident_path}

## Objective
Jane should inspect the incident evidence, diagnose the root cause, and apply a
minimal, verified fix if the evidence supports one.

## Context
- Source: `{incident.get("source", "")}`
- Category: `{incident.get("category", "")}`
- Project root: `{project_root}`
- Fingerprint: `{incident.get("fingerprint", "")}`
- Request path: `{incident.get("request", {}).get("path", "")}`

## Steps
1. Read the incident JSON at `{incident_path}` and the relevant service logs.
2. Inspect source code before explaining the cause. Do not speculate from the stack trace alone.
3. Reproduce with a focused test or command when feasible.
4. If the root cause is clear, patch the smallest relevant surface.
5. Do not revert unrelated dirty work. Preserve user changes.
6. Run focused verification. Broaden tests only if the fix touches shared behavior.
7. Record the outcome in the incident report and work log.

## Verification
- The failing route/action no longer throws the captured error.
- A focused test, syntax check, or local smoke test covers the fixed path.
- If no safe fix is possible, leave a clear report explaining the blocker and evidence checked.
"""


def jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return json.loads(json.dumps(value, default=str))
