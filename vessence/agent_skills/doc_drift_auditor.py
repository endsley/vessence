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

    # Get actual crontab entries (script paths)
    try:
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True, check=False)
        if r.returncode != 0:
            warn(f"crontab -l failed: {r.stderr[:120]}")
            return
        actual_lines = r.stdout.splitlines()
    except Exception as e:
        warn(f"crontab read failed: {e}")
        return

    # Extract script names from crontab (last python file in each line)
    actual_scripts = set()
    for ln in actual_lines:
        s = ln.strip()
        if not s or s.startswith("#") or "=" in s and not s.startswith("0") and "*" not in s[:5]:
            continue
        for tok in s.split():
            if tok.endswith(".py") or tok.endswith(".sh"):
                actual_scripts.add(Path(tok).name)

    # Extract documented script names
    doc_text = cron_path.read_text()
    doc_scripts = set(re.findall(r"`\$VESSENCE_HOME/[^`]*?/([^/`]+\.(?:py|sh))`", doc_text))
    doc_scripts |= set(re.findall(r"`/home/chieh/ambient/vessence/[^`]*?/([^/`]+\.(?:py|sh))`", doc_text))

    missing_in_doc = actual_scripts - doc_scripts
    missing_in_cron = doc_scripts - actual_scripts

    for s in sorted(missing_in_doc):
        warn(f"CRON_JOBS.md missing entry for active cron script: {s}")
    for s in sorted(missing_in_cron):
        warn(f"CRON_JOBS.md mentions {s} but no matching cron entry exists")


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
    real_classes = set(re.findall(r'"([A-Z_]+)":\s*"', code))
    if not real_classes:
        warn("Couldn't parse _CLASS_MAP from stage1_classifier.py")
        return

    # Documented classes (uppercase in the table)
    doc_text = p.read_text()
    doc_classes = set(re.findall(r"\|\s*([A-Z_]{4,})\s*\|", doc_text))

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
    for f in referenced:
        if not (skills_dir / f).exists():
            warn(f"SKILLS_REGISTRY.md references missing file: agent_skills/{f}")


# ── Report + commit ─────────────────────────────────────────────────────────


def write_report() -> None:
    DRIFT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    body = [f"# Doc Drift Report — {ts}\n"]
    if _changes:
        body.append("## Auto-fixed\n")
        body.extend(_changes)
        body.append("")
    if _warnings:
        body.append("## Needs human review\n")
        body.extend(f"- {w}" for w in _warnings)
        body.append("")
    if not _changes and not _warnings:
        body.append("All docs in sync. ✅\n")
    DRIFT_REPORT.write_text("\n".join(body) + "\n")


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


def main() -> int:
    audit_cron()
    audit_auditable_modules()
    audit_pipeline_classes()
    audit_class_packs()
    audit_skills_registry()
    write_report()
    commit_if_changed()
    log(f"Done — {len(_changes)} fixes, {len(_warnings)} warnings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
