from jane_web.self_improvement_context import build_self_improvement_context_block


def test_build_self_improvement_context_block_empty_log_shape():
    block = build_self_improvement_context_block([])

    assert block.startswith("\n\n[SELF IMPROVEMENT CONTEXT]\n")
    assert "Readable latest report: $VESSENCE_HOME/configs/self_improvement_latest.md" in block
    assert "Vocal summary log file: $VESSENCE_DATA_HOME/self_improve_vocal_log.jsonl" in block
    assert "No recent self-improvement entries found" in block
    assert block.endswith("[END SELF IMPROVEMENT CONTEXT]")


def test_build_self_improvement_context_block_groups_jobs_and_numbers_entries():
    block = build_self_improvement_context_block(
        [
            {
                "timestamp": "2026-07-02T02:00:00Z",
                "job": "Transcript Review",
                "severity": "medium",
                "summary": "Fixed a transcript issue. ",
            },
            {
                "timestamp": "2026-07-02T01:00:00Z",
                "job": "Timer Audit",
                "severity": "low",
                "summary": "Cleaned a timer edge case.",
            },
            {
                "timestamp": "2026-07-02T00:00:00Z",
                "job": "Transcript Review",
                "summary": "Documented a transcript rule.",
            },
        ],
        log_path="/tmp/vocal.jsonl",
        tech_logs="/tmp/logs/*.log",
        latest_report="/tmp/latest.md",
    )

    assert "Readable latest report: /tmp/latest.md" in block
    assert "Vocal summary log file: /tmp/vocal.jsonl" in block
    assert "Technical job logs: /tmp/logs/*.log" in block
    assert "Total entries in context window: 3 (most recent first)." in block
    assert "Job categories: Transcript Review (2), Timer Audit (1)." in block
    assert "1. [2026-07-02T02:00:00Z | Transcript Review | medium] Fixed a transcript issue." in block
    assert "2. [2026-07-02T01:00:00Z | Timer Audit | low] Cleaned a timer edge case." in block
    assert "3. [2026-07-02T00:00:00Z | Transcript Review | info] Documented a transcript rule." in block
    assert block.endswith("[END SELF IMPROVEMENT CONTEXT]")
