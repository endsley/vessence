from agent_skills.ra_research_report_markdown import (
    build_deterministic_action_plan,
    build_deterministic_compressed_context,
    build_deterministic_recommendation_scheme,
    build_run_report_markdown,
    build_useful_report_markdown,
    default_clinician_questions,
    default_tracking_items,
    list_to_markdown,
    source_heading,
    source_trace_line,
    useful_finding_lines,
    useful_report_summary_groups,
)
from agent_skills.ra_research_report_tables import (
    EMPTY_EVIDENCE_ROW,
    action_plan_evidence_rows,
    markdown_cell,
    recommendation_scheme_evidence_rows,
)


def test_list_to_markdown_and_source_heading_clean_values():
    assert list_to_markdown([" first  item ", "", "second\nitem"]) == "- first item\n- second item"
    assert list_to_markdown(" one\nitem ") == "- one item"
    assert list_to_markdown([]) == "- None captured."
    assert source_heading({"source_id": "pmid-1", "title": "Long " * 40}, max_chars=20).startswith("`pmid-1` Long Long")


def test_ra_report_table_helpers_preserve_truncation_and_escaping():
    summary = {
        "source_id": "pmid-1",
        "title": "Treat | target " * 20,
        "study_type": "Guideline | RCT",
        "evidence_scope": "Full | text",
        "remission_relevance": "Relevant | " * 40,
        "artifact_dir": "/vault/artifact",
    }

    assert markdown_cell(" a | b\nc ", max_chars=5) == "a \\| b"
    assert action_plan_evidence_rows([summary])[0].startswith("| `pmid-1` Treat \\| target")
    assert "Guideline \\| RCT" in action_plan_evidence_rows([summary])[0]
    assert "Full \\| text" in action_plan_evidence_rows([summary])[0]
    assert recommendation_scheme_evidence_rows([summary])[0].startswith("| Treat \\| target")
    assert " | Full | text | " in recommendation_scheme_evidence_rows([summary])[0]
    assert action_plan_evidence_rows([]) == [EMPTY_EVIDENCE_ROW]
    assert recommendation_scheme_evidence_rows([]) == [EMPTY_EVIDENCE_ROW]


def test_ra_report_table_helpers_keep_existing_row_limits():
    summaries = [
        {
            "source_id": f"pmid-{index}",
            "title": f"title {index}",
            "study_type": "review",
            "evidence_scope": "abstract",
            "remission_relevance": "background",
        }
        for index in range(45)
    ]

    assert len(action_plan_evidence_rows(summaries)) == 40
    assert action_plan_evidence_rows(summaries)[-1].startswith("| `pmid-39`")
    assert len(recommendation_scheme_evidence_rows(summaries)) == 30
    assert recommendation_scheme_evidence_rows(summaries)[-1].startswith("| title 29")


def test_build_useful_report_markdown_includes_high_signal_sections_and_paths():
    high_signal = {
        "source_id": "pmid-1",
        "title": "Treat to target CDAI remission guidance",
        "study_type": "guideline",
        "evidence_scope": "open_access_full_text",
        "remission_relevance": "CDAI target selection changes what Kathia should ask about.",
        "main_findings": ["CDAI treat-to-target care improves remission monitoring."],
        "limitations": ["Monitor ESR, CRP, infection risk, and medication safety."],
        "actionable_implications": ["Ask whether CDAI is the active target."],
        "clinician_discussion_points": ["Which remission score is being used?"],
        "tests_or_monitoring": ["Track CDAI, swollen joints, ESR, and CRP."],
        "safety_concerns": ["Discuss infection risk before medication changes."],
        "url": "https://example.test/high",
    }
    low_signal = {
        "source_id": "pmid-2",
        "title": "Speculative scenario outside RA remission",
        "study_type": "review",
        "evidence_scope": "abstract_only",
        "remission_relevance": "Does not directly address rheumatoid arthritis remission.",
        "main_findings": ["Needs manual/LLM review before use."],
        "needs_llm_review": True,
        "url": "https://example.test/low",
    }

    report = build_useful_report_markdown(
        [high_signal, low_signal],
        [],
        {
            "discoveries": ["CDAI target choice matters this run."],
            "open_questions": ["Find monitoring intervals with better evidence."],
        },
        9,
        recommendation_path="/vault/scheme.md",
        action_plan_path="/vault/action.md",
        compressed_context_path="/vault/context.md",
        discoveries_path="/vault/discoveries.md",
    )

    assert "- This run processed 2 unique new or upgraded source summaries; the cache now has 9 sources." in report
    assert "- Main themes this run: treat-to-target and remission scoring, tests and biomarkers, safety and comorbidities." in report
    assert "- CDAI target choice matters this run." in report
    assert "### `pmid-1` Treat to target CDAI remission guidance" in report
    assert "- Evidence: guideline, open_access_full_text." in report
    assert "- Useful next step: Ask whether CDAI is the active target." in report
    assert "- Safety note: Discuss infection risk before medication changes." in report
    assert "`pmid-2` Speculative scenario outside RA remission: needs manual review before relying on it" in report
    assert "- Find monitoring intervals with better evidence." in report
    assert "- Living recommendation scheme: `/vault/scheme.md`" in report
    assert "- `pmid-1` Treat to target CDAI remission guidance | guideline, open_access_full_text | https://example.test/high" in report
    assert report.endswith("\n")


def test_useful_report_summary_groups_rank_signal_and_fallback_themes():
    high_signal = {
        "source_id": "pmid-high",
        "title": "Treat to target monitoring",
        "study_type": "guideline",
        "evidence_scope": "open_access_full_text",
        "remission_relevance": "CDAI treat-to-target scoring changes clinician questions.",
        "main_findings": ["Validated disease activity scoring matters."],
    }
    low_signal = {
        "source_id": "pmid-low",
        "title": "Speculative technology outside RA remission",
        "evidence_scope": "abstract_only",
        "remission_relevance": "Does not directly address rheumatoid arthritis remission.",
        "needs_llm_review": True,
    }

    groups = useful_report_summary_groups(
        [low_signal, high_signal, high_signal],
        [{"remission_relevance": "Diet and omega-3 evidence for rheumatoid arthritis."}],
    )

    assert groups["unique_new"] == [low_signal, high_signal]
    assert groups["ranked_new"][0] == high_signal
    assert groups["high_signal"] == [high_signal]
    assert groups["low_signal"] == [low_signal]
    assert "treat-to-target and remission scoring" in groups["themes"]


def test_useful_report_source_render_helpers_preserve_high_signal_shapes():
    summary = {
        "source_id": "pmid-1",
        "title": "Treat to target CDAI remission guidance",
        "study_type": "guideline",
        "evidence_scope": "open_access_full_text",
        "remission_relevance": "CDAI target selection changes what Kathia should ask about.",
        "main_findings": ["CDAI treat-to-target care improves remission monitoring."],
        "limitations": ["Monitor ESR, CRP, infection risk, and medication safety."],
        "actionable_implications": ["Ask whether CDAI is the active target."],
        "clinician_discussion_points": ["Which remission score is being used?"],
        "safety_concerns": ["Discuss infection risk before medication changes."],
        "url": "https://example.test/high",
    }

    assert useful_finding_lines(summary) == [
        "### `pmid-1` Treat to target CDAI remission guidance",
        "- Evidence: guideline, open_access_full_text.",
        "- Why it matters: CDAI target selection changes what Kathia should ask about.",
        "- Finding: CDAI treat-to-target care improves remission monitoring.",
        "- Useful next step: Ask whether CDAI is the active target.",
        "- Clinician question: Which remission score is being used?",
        "- Caveat: Monitor ESR, CRP, infection risk, and medication safety.",
        "- Safety note: Discuss infection risk before medication changes.",
    ]
    assert source_trace_line(summary) == (
        "- `pmid-1` Treat to target CDAI remission guidance | "
        "guideline, open_access_full_text | https://example.test/high"
    )


def test_build_useful_report_markdown_uses_defaults_without_signal():
    report = build_useful_report_markdown([], [], None, 0)

    assert "- This run processed 0 unique new or upgraded source summaries; the cache now has 0 sources." in report
    assert "- No new source rose above the high-signal threshold; treat this run mostly as cache-building." in report
    assert default_clinician_questions()[0] in report
    assert default_tracking_items()[0] in report
    assert "- No new source trace for this run." in report


def test_deterministic_ra_builders_include_timestamp_evidence_and_safety():
    summary = {
        "source_id": "pmid-1",
        "title": "Treat | target",
        "study_type": "Guideline",
        "evidence_scope": "Full text",
        "remission_relevance": "Supports CDAI scoring.",
        "artifact_dir": "/vault/artifact",
    }

    context = build_deterministic_compressed_context(
        [summary],
        updated_label="2026-07-02T12:00:00-04:00",
        mission_statement="Keep Kathia safe.",
    )
    action_plan = build_deterministic_action_plan([summary], updated_label="2026-07-02 12:00 EDT")
    scheme = build_deterministic_recommendation_scheme([summary], updated_label="2026-07-02 12:00 EDT")

    assert "Updated: 2026-07-02T12:00:00-04:00" in context
    assert "Mission: Keep Kathia safe." in context
    assert "`pmid-1` Treat | target: Supports CDAI scoring." in context
    assert "Last updated: 2026-07-02 12:00 EDT" in action_plan
    assert "`pmid-1` Treat \\| target" in action_plan
    assert "Do not stop/start/change DMARDs" in action_plan
    assert "RA Remission / Asymptomatic-State Research Scheme" in scheme
    assert "| Treat \\| target | Full text | Supports CDAI scoring. | /vault/artifact |" in scheme
    assert "Medication starts" in scheme


def test_deterministic_ra_builders_include_empty_evidence_rows():
    assert "| No sources processed yet | | | |" in build_deterministic_action_plan(
        [],
        updated_label="2026-07-02 12:00 EDT",
    )
    assert "| No sources processed yet | | | |" in build_deterministic_recommendation_scheme(
        [],
        updated_label="2026-07-02 12:00 EDT",
    )


def test_build_run_report_markdown_wraps_useful_report_and_source_details():
    summary = {
        "source_id": "pmid-3",
        "title": "RA remission monitoring review",
        "study_type": "systematic review",
        "evidence_scope": "open_access_full_text",
        "remission_relevance": "Monitoring changes clinician discussion.",
        "main_findings": ["CDAI and CRP monitoring were discussed."],
        "artifact_dir": "/vault/papers/pmid-3",
        "url": "https://example.test/pmid-3",
    }

    report = build_run_report_markdown(
        [summary],
        [],
        "SCHEME-" + ("x" * 3000),
        "ACTION-" + ("y" * 4000),
        11,
        None,
        generated_label="2026-07-02 12:00 EDT",
        recommendation_path="/vault/scheme.md",
        action_plan_path="/vault/action.md",
        compressed_context_path="/vault/context.md",
        latest_codex_synthesis_path="/vault/codex.md",
        discoveries_path="/vault/discoveries.md",
    )

    assert report.startswith("# RA Research Run 2026-07-02 12:00 EDT\n")
    assert "Recommendation file: `/vault/scheme.md`" in report
    assert "Latest Codex synthesis: `/vault/codex.md`" in report
    assert "## Most Useful Findings" in report
    assert "## New Source Details" in report
    assert "### RA remission monitoring review" in report
    assert "- Source ID: `pmid-3`" in report
    assert "- Saved artifact: `/vault/papers/pmid-3`" in report
    assert "- Usefulness label: useful signal" in report
    assert "## Standing Action Plan Snapshot\n\nACTION-" in report
    assert "## Standing Scheme Snapshot\n\nSCHEME-" in report
    assert report.endswith("\n")
