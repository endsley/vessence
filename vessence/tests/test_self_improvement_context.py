from jane_web.self_improvement_context import (
    SELF_IMPROVEMENT_CONTEXT_END,
    _context_header_lines,
    _empty_context_lines,
    _entry_reference_line,
    _job_category_summary,
    _numbered_entry_reference_lines,
    _voice_response_style_message,
    build_self_improvement_context_block,
)


def test_self_improvement_context_helpers_preserve_header_summary_and_entry_shapes():
    assert _context_header_lines(
        log_path="/tmp/vocal.jsonl",
        tech_logs="/tmp/*.log",
        latest_report="/tmp/latest.md",
    ) == [
        "\n\n[SELF IMPROVEMENT CONTEXT]",
        "Readable latest report: /tmp/latest.md",
        "Vocal summary log file: /tmp/vocal.jsonl",
        "Technical job logs: /tmp/*.log",
    ]
    assert _job_category_summary(
        [
            {"job": "Transcript Review"},
            {"job": "Timer Audit"},
            {"job": "Transcript Review"},
            {},
        ]
    ) == "Transcript Review (2), Timer Audit (1), ? (1)"
    assert _entry_reference_line(
        2,
        {
            "timestamp": "2026-07-02T01:00:00Z",
            "job": "Timer Audit",
            "summary": " Cleaned a timer edge case. ",
        },
    ) == "2. [2026-07-02T01:00:00Z | Timer Audit | info] Cleaned a timer edge case."


def test_self_improvement_context_section_helpers_preserve_empty_and_numbered_shapes():
    entries = [
        {"timestamp": "2026-07-02T02:00:00Z", "job": "Transcript Review", "summary": "Fixed one."},
        {"timestamp": "2026-07-02T01:00:00Z", "job": "Timer Audit", "severity": "low", "summary": "Cleaned."},
    ]

    assert _empty_context_lines(
        log_path="/tmp/vocal.jsonl",
        tech_logs="/tmp/*.log",
        latest_report="/tmp/latest.md",
    ) == [
        "\n\n[SELF IMPROVEMENT CONTEXT]",
        "Readable latest report: /tmp/latest.md",
        "Vocal summary log file: /tmp/vocal.jsonl",
        "Technical job logs: /tmp/*.log",
        (
            "No recent self-improvement entries found (empty log or older than 14 days). "
            "Tell the user nothing's been logged yet and the nightly job may not have run recently."
        ),
        SELF_IMPROVEMENT_CONTEXT_END,
    ]
    style = _voice_response_style_message(entries)
    assert "RESPONSE STYLE" in style
    assert "Total entries in context window: 2 (most recent first)." in style
    assert "Job categories: Transcript Review (1), Timer Audit (1)." in style
    assert _numbered_entry_reference_lines(entries) == [
        "",
        "Entries (numbered for drill-down reference):",
        "1. [2026-07-02T02:00:00Z | Transcript Review | info] Fixed one.",
        "2. [2026-07-02T01:00:00Z | Timer Audit | low] Cleaned.",
        SELF_IMPROVEMENT_CONTEXT_END,
    ]


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
