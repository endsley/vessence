from agent_skills import auto_commit_wip
from agent_skills.auto_commit_helpers import (
    auto_commit_message,
    auto_commit_phase,
    committable_status_lines,
)


def test_auto_commit_wip_exposes_helpers():
    assert auto_commit_wip._auto_commit_message is auto_commit_message
    assert auto_commit_wip._auto_commit_phase is auto_commit_phase
    assert auto_commit_wip._committable_status_lines is committable_status_lines


def test_committable_status_lines_filters_backup_noise_and_blank_lines():
    status = """
 M agent_skills/tool.py
?? .git.backup
?? notes.md

"""
    assert committable_status_lines(status) == [
        " M agent_skills/tool.py",
        "?? notes.md",
    ]


def test_auto_commit_phase_and_message_preserve_existing_shapes():
    assert auto_commit_phase(False) == "pre-self-improve WIP"
    assert auto_commit_phase(True) == "post-self-improve"
    assert auto_commit_message(
        phase="pre-self-improve WIP",
        timestamp="2026-07-02 12:00",
        changed_count=3,
    ) == (
        "auto-commit: pre-self-improve WIP (2026-07-02 12:00)\n\n"
        "3 file(s) changed. Committed automatically by the\n"
        "nightly self-improvement orchestrator."
    )
