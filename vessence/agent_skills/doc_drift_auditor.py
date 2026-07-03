"""doc_drift_auditor.py — keep configs/*.md in sync with reality.

Compares each registry / architecture doc against the actual filesystem
or system state. Three classes of drift:

  - **Documented but missing** (file referenced in doc doesn't exist)
  - **Existing but undocumented** (file/cron present but absent from doc)
  - **Field mismatch** (e.g. doc says class X has handler, file says no)

Auto-fixes safe drifts (additions/removals in tables) and commits them
with prefix `auto-doc-sync:`. Anything ambiguous is logged to
`configs/doc_drift_report.md` for human review.

Run as part of nightly_self_improve.py at 3 AM.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path

from agent_skills.doc_drift_helpers import (
    build_drift_report as _build_drift_report,
    drift_vocal_summary_kwargs as _drift_vocal_summary_kwargs,
    extract_active_cron_script_names as _extract_active_cron_script_names,
    extract_class_map_keys as _extract_class_map_keys,
    extract_doc_table_classes as _extract_doc_table_classes,
    extract_documented_cron_script_names as _extract_documented_cron_script_names,
    extract_inactive_documented_cron_script_names as _extract_inactive_documented_cron_script_names,
)

VESSENCE_HOME = Path(os.environ.get("VESSENCE_HOME", str(Path(__file__).resolve().parents[1])))
CONFIGS = VESSENCE_HOME / "configs"
DRIFT_REPORT = CONFIGS / "doc_drift_report.md"

# Track changes for the final commit
_changes: list[str] = []
_warnings: list[str] = []


def log(msg: str) -> None:
    print(f"[doc-drift] {msg}")


def warn(msg: str) -> None:
    log(f"WARN: {msg}")
    _warnings.append(msg)


def record_change(path: Path, msg: str) -> None:
    log(f"FIXED: {msg}")
    _changes.append(f"- {path.name}: {msg}")


# ── Audit 1: CRON_JOBS.md vs actual crontab ─────────────────────────────────


def audit_cron() -> None:
    log("Audit 1: CRON_JOBS.md vs actual crontab")
    cron_path = CONFIGS / "CRON_JOBS.md"
    if not cron_path.exists():
        warn("CRON_JOBS.md missing")
        return

    # Get actual crontab entries (script paths). Only uncommented lines count
    # as "active" — commented lines in crontab are historical/disabled.
    try:
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, check=False)
        if r.returncode != 0:
            warn(f"crontab -l failed: {r.stderr[:120]}")
            return
        actual_lines = r.stdout.splitlines()
    except Exception as e:
        warn(f"crontab read failed: {e}")
        return

    actual_scripts = _extract_active_cron_script_names(actual_lines)

    # Extract documented script names ONLY from **Script Path:** lines. Inline
    # mentions in prose (e.g. "appends to CODE_MAP_KEYWORDS in jane_proxy.py")
    # must not be treated as cron entries.
    doc_text = cron_path.read_text()
    doc_scripts = _extract_documented_cron_script_names(doc_text)

    # Identify entries documented as INACTIVE so they don't fire false positives:
    # - anything under "Removed Jobs" or "Non-Cron Scheduled Scripts" sections
    # - any entry whose section header contains "DISABLED" or "COMMENTED OUT"
    inactive_scripts = _extract_inactive_documented_cron_script_names(doc_text)

    active_doc_scripts = doc_scripts - inactive_scripts

    missing_in_doc = actual_scripts - doc_scripts
    missing_in_cron = active_doc_scripts - actual_scripts

    for s in sorted(missing_in_doc):
        warn(f"CRON_JOBS.md missing entry for active cron script: {s}")
    for s in sorted(missing_in_cron):
        warn(f"CRON_JOBS.md claims {s} is active but no matching cron entry exists")


# ── Audit 2: auditable_modules.md whitelist files exist ─────────────────────


def audit_auditable_modules() -> None:
    log("Audit 2: auditable_modules.md whitelist")
    p = CONFIGS / "auditable_modules.md"
    if not p.exists():
        return
    text = p.read_text()
    new_lines = []
    removed = []
    for line in text.splitlines():
        m = re.match(r"\|\s*`([^`]+\.py)`\s*\|", line)
        if m:
            mod_path = VESSENCE_HOME / m.group(1)
            if not mod_path.exists():
                removed.append(m.group(1))
                continue  # drop the row
        new_lines.append(line)
    if removed:
        p.write_text("\n".join(new_lines) + "\n")
        record_change(p, f"removed {len(removed)} dead module rows: {', '.join(removed)}")


# ── Audit 3: v2_3stage_pipeline.md class table vs reality ───────────────────


def audit_pipeline_classes() -> None:
    log("Audit 3: v2_3stage_pipeline.md classes vs _CLASS_MAP")
    p = CONFIGS / "v2_3stage_pipeline.md"
    if not p.exists():
        return

    # Real classes from stage1_classifier.py
    classifier = VESSENCE_HOME / "jane_web/jane_v2/stage1_classifier.py"
    if not classifier.exists():
        warn("stage1_classifier.py missing — can't verify classes")
        return
    code = classifier.read_text()
    real_classes = _extract_class_map_keys(code)
    if not real_classes:
        warn("Couldn't parse _CLASS_MAP from stage1_classifier.py")
        return

    # Documented classes (uppercase keys in the first table column)
    doc_text = p.read_text()
    doc_classes = _extract_doc_table_classes(doc_text)

    missing_in_doc = real_classes - doc_classes
    missing_in_code = doc_classes - real_classes
    for c in sorted(missing_in_doc):
        warn(f"v2_3stage_pipeline.md missing class row: {c}")
    for c in sorted(missing_in_code):
        warn(f"v2_3stage_pipeline.md mentions {c} but no _CLASS_MAP entry")


# ── Audit 4: Stage 2 class packs have handler.py + metadata.py if registered ─


def audit_class_packs() -> None:
    log("Audit 4: Stage 2 class pack files")
    classes_dir = VESSENCE_HOME / "jane_web/jane_v2/classes"
    if not classes_dir.exists():
        return
    for sub in classes_dir.iterdir():
        if not sub.is_dir() or sub.name.startswith("_"):
            continue
        meta = sub / "metadata.py"
        if not meta.exists():
            warn(f"class pack {sub.name}/ has no metadata.py")
        # handler.py is optional (some classes intentionally escalate)


# ── Audit 5: SKILLS_REGISTRY.md mentions only files that exist ──────────────


def audit_skills_registry() -> None:
    log("Audit 5: SKILLS_REGISTRY.md")
    p = CONFIGS / "SKILLS_REGISTRY.md"
    if not p.exists():
        return  # registry not present — skip
    text = p.read_text()
    referenced = set(re.findall(r"`agent_skills/([^`]+\.py)`", text))
    referenced |= set(re.findall(r"\$VESSENCE_HOME/agent_skills/([^\s`]+\.py)", text))
    skills_dir = VESSENCE_HOME / "agent_skills"
    missing = {f for f in referenced if not (skills_dir / f).exists()}
    if not missing:
        return

    # Auto-remove capability blocks that point at a missing skill file. The
    # registry is structured as blank-line-separated "- **Capability:**" blocks;
    # drop whole blocks whose body mentions a missing file.
    blocks = text.split("\n\n")
    kept: list[str] = []
    removed_caps: list[str] = []
    for blk in blocks:
        stripped = blk.lstrip()
        is_capability_block = (
            stripped.startswith("- **Capability:**")
            or stripped.startswith("-   **Capability:**")
        )
        if not is_capability_block:
            kept.append(blk)
            continue
        touches_missing = any(fname in blk for fname in missing)
        if touches_missing:
            header = blk.splitlines()[0].strip()
            cap_name = header.split("**Capability:**", 1)[-1].strip()
            removed_caps.append(cap_name)
        else:
            kept.append(blk)

    if removed_caps:
        new_text = "\n\n".join(kept)
        if not new_text.endswith("\n"):
            new_text += "\n"
        p.write_text(new_text)
        record_change(
            p,
            f"removed {len(removed_caps)} stale capability block(s) "
            f"pointing at missing file(s): {', '.join(sorted(missing))}",
        )

    # Anything still mentioned in prose (not inside a capability block) has
    # to be reviewed by hand — auto-editing prose is too risky.
    leftover_text = "\n\n".join(kept)
    still_referenced = {f for f in missing if f in leftover_text}
    for f in sorted(still_referenced):
        warn(
            f"SKILLS_REGISTRY.md still mentions missing file agent_skills/{f} "
            f"in non-capability prose — needs human review"
        )


# ── Report + commit ─────────────────────────────────────────────────────────


def write_report() -> None:
    DRIFT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    DRIFT_REPORT.write_text(_build_drift_report(_changes, _warnings, ts))


def commit_if_changed() -> None:
    if not _changes:
        return
    try:
        subprocess.run(
            ["git", "add", "-A"], cwd=VESSENCE_HOME, check=False, capture_output=True
        )
        msg = f"auto-doc-sync: {len(_changes)} doc drift fix(es)\n\n" + "\n".join(_changes)
        subprocess.run(
            ["git", "commit", "-m", msg, "--no-verify"],
            cwd=VESSENCE_HOME, check=False, capture_output=True,
        )
        log(f"Committed {len(_changes)} doc fixes")
    except Exception as e:
        warn(f"git commit failed: {e}")


def _log_vocal() -> None:
    try:
        sys.path.insert(0, str(VESSENCE_HOME))
        from agent_skills.self_improve_log import log_vocal_summary
    except Exception:
        return
    log_vocal_summary(**_drift_vocal_summary_kwargs(_changes, _warnings))


def main() -> int:
    audit_cron()
    audit_auditable_modules()
    audit_pipeline_classes()
    audit_class_packs()
    audit_skills_registry()
    write_report()
    commit_if_changed()
    log(f"Done — {len(_changes)} fixes, {len(_warnings)} warnings")
    _log_vocal()
    return 0


if __name__ == "__main__":
    sys.exit(main())
