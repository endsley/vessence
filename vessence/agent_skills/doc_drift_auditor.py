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
import ast
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


def _extract_class_map_keys(source: str) -> set[str]:
    """Return canonical class keys from stage1_classifier.py's _CLASS_MAP.

    The classifier accepts compatibility aliases such as ``NATIONALGRID BILLS``
    and ``NATIONALGRID_BILLS``. Documentation tables use underscore keys, so
    normalize whitespace aliases instead of relying on a quote regex that
    silently skips them.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "_CLASS_MAP" for t in node.targets):
            continue
        try:
            class_map = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            return set()
        if not isinstance(class_map, dict):
            return set()
        return {
            str(key).upper().replace(" ", "_")
            for key in class_map
            if isinstance(key, str)
        }
    return set()


def _extract_doc_table_classes(doc_text: str) -> set[str]:
    """Return uppercase class keys from the documented class table."""
    classes: set[str] = set()
    in_class_table = False
    for line in doc_text.splitlines():
        stripped = line.strip()
        if in_class_table and not stripped:
            break
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip().strip("`") for cell in stripped.strip("|").split("|")]
        if not cells:
            continue
        first_cell = cells[0].lower()
        if first_cell in {"class", "chromadb name"}:
            in_class_table = True
            continue
        if not in_class_table:
            continue
        candidate = cells[0]
        if re.fullmatch(r"[A-Z][A-Z0-9_]{3,}", candidate):
            classes.add(candidate)
    return classes


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

    actual_scripts = set()
    for ln in actual_lines:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        # Skip env-var assignments like SHELL=/bin/sh
        if "=" in s and not s.startswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "@")):
            continue
        for tok in s.split():
            if tok.endswith(".py") or tok.endswith(".sh"):
                actual_scripts.add(Path(tok).name)

    # Extract documented script names ONLY from **Script Path:** lines. Inline
    # mentions in prose (e.g. "appends to CODE_MAP_KEYWORDS in jane_proxy.py")
    # must not be treated as cron entries.
    doc_text = cron_path.read_text()
    script_path_re = re.compile(
        r"\*\*Script Path:\*\*\s*`[^`]*?/([^/`]+\.(?:py|sh))`"
    )
    doc_scripts = set(script_path_re.findall(doc_text))

    # Identify entries documented as INACTIVE so they don't fire false positives:
    # - anything under "Removed Jobs" or "Non-Cron Scheduled Scripts" sections
    # - any entry whose section header contains "DISABLED" or "COMMENTED OUT"
    inactive_scripts: set[str] = set()
    sections = re.split(r"^##\s+", doc_text, flags=re.MULTILINE)
    for sec in sections:
        if not sec.strip():
            continue
        header = sec.splitlines()[0]
        inactive_section = any(
            key in header
            for key in ("Removed Jobs", "Non-Cron Scheduled Scripts")
        )
        disabled_entry = any(
            key in header for key in ("DISABLED", "COMMENTED OUT", "Paused:")
        )
        if inactive_section or disabled_entry:
            inactive_scripts |= set(script_path_re.findall(sec))

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


def _log_vocal() -> None:
    try:
        sys.path.insert(0, str(VESSENCE_HOME))
        from agent_skills.self_improve_log import log_vocal_summary
    except Exception:
        return
    if not _changes and not _warnings:
        log_vocal_summary(
            job="Doc Drift Audit",
            summary=(
                "I checked that docs like the cron registry, skill "
                "registry, and pipeline class map still match the code. "
                "Everything lined up — no drift."
            ),
            severity="info",
        )
        return
    sev = "medium" if _warnings else "info"
    n_fix = len(_changes)
    n_warn = len(_warnings)
    log_vocal_summary(
        job="Doc Drift Audit",
        what_was_wrong=(
            f"I found {n_warn} spot{'s' if n_warn != 1 else ''} where "
            f"docs drifted from the code"
        ) if n_warn else (
            f"I found {n_fix} doc{'s' if n_fix != 1 else ''} that needed "
            "small fixes"
        ),
        why_it_mattered=(
            "Stale docs make it easy to ship changes that break "
            "undocumented behavior"
        ),
        what_was_done=(
            f"I auto-fixed {n_fix} and flagged the rest in the doc "
            f"drift report for you to review"
        ) if n_fix else (
            "I flagged them in the doc drift report for your review — "
            "the ambiguous ones need a human call"
        ),
        severity=sev,
    )


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
