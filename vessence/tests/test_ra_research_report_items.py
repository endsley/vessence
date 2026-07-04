from agent_skills.ra_research_report_items import (
    collect_report_items,
    evidence_strength_score,
    evidence_label,
    filter_report_items,
    infer_report_themes,
    is_low_value_summary,
    is_strong_evidence_type,
    is_usable_report_item,
    lacks_direct_remission_relevance,
    low_value_reason,
    psoriatic_without_rheumatoid_focus,
    speculative_summary_text,
    summary_noise_penalty,
    summary_signal_score,
    summary_text_blob,
    summary_usefulness_score,
)


def test_summary_text_blob_and_signal_score_rewards_actionable_evidence():
    summary = {
        "title": "Treat-to-target guideline",
        "study_type": "guideline",
        "evidence_scope": "guideline_or_review_page",
        "main_findings": ["DAS28 and CDAI targets were emphasized."],
        "actionable_implications": ["Ask rheumatologist about the target score."],
        "tests_or_monitoring": ["Track ESR/CRP."],
        "food_diet_implications": ["Diet is adjunctive."],
        "technology_implications": ["Wearable tracking may help logs."],
    }

    assert "das28 and cdai" in summary_text_blob(summary)
    assert summary_signal_score(summary) == 15
    assert is_strong_evidence_type(summary)
    assert not is_low_value_summary(summary)


def test_summary_signal_score_components_preserve_strength_usefulness_and_noise_rules():
    summary = {
        "main_findings": ["Finding"],
        "actionable_implications": ["Action"],
        "tests_or_monitoring": ["Track CRP."],
        "food_diet_implications": ["Diet is adjunctive."],
        "technology_implications": ["Wearable tracking."],
        "needs_llm_review": True,
    }
    text = "needs manual/llm review and does not directly address speculative scenario"

    assert evidence_strength_score("guideline randomized systematic cohort review", "abstract_only") == 19
    assert summary_usefulness_score(summary) == 7
    assert summary_noise_penalty(summary, text) == -15


def test_low_value_text_predicates_preserve_shared_noise_rules():
    assert lacks_direct_remission_relevance("This did not directly address remission.")
    assert lacks_direct_remission_relevance("This does not directly address remission.")
    assert lacks_direct_remission_relevance("This is not directly address focused.")
    assert psoriatic_without_rheumatoid_focus("psoriatic arthritis only")
    assert not psoriatic_without_rheumatoid_focus("psoriatic arthritis and rheumatoid arthritis")
    assert speculative_summary_text("speculative scenario planning")


def test_low_value_reason_and_score_penalties_match_noisy_evidence_rules():
    summary = {
        "evidence_scope": "abstract_only",
        "main_findings": ["Needs manual/LLM review and does not directly address remission strategy."],
        "limitations": ["Speculative scenario planning only."],
        "needs_llm_review": True,
    }

    assert summary_signal_score(summary) == -15
    assert low_value_reason(summary) == (
        "needs manual review before relying on it; abstract-only; "
        "does not directly answer remission/asymptomatic strategy; "
        "speculative/future-facing rather than actionable"
    )
    assert is_low_value_summary(summary)


def test_abstract_only_is_not_low_value_when_signal_score_is_enough():
    summary = {
        "study_type": "randomized trial",
        "evidence_scope": "abstract_only",
        "main_findings": ["RA remission outcome was measured."],
    }

    assert low_value_reason(summary) == "abstract-only"
    assert summary_signal_score(summary) == 5
    assert not is_low_value_summary(summary)


def test_directness_penalty_can_be_overridden_by_strong_high_score_evidence():
    summary = {
        "study_type": "guideline",
        "evidence_scope": "open_access_full_text",
        "main_findings": ["This does not directly address Kathia but discusses rheumatoid arthritis remission."],
        "actionable_implications": ["Clarify disease activity target."],
    }

    assert summary_signal_score(summary) == 8
    assert not is_low_value_summary(summary)


def test_report_item_filters_drop_unhelpful_or_wrong_disease_items():
    items = [
        "",
        "No safety concerns were noted.",
        "Safety outcomes were similar between arms.",
        "Feasibility concerns limited implementation.",
        "Lupus-specific outcome.",
        "Ask about CDAI target.",
    ]

    assert not is_usable_report_item("mentions SLE population")
    assert filter_report_items(items) == ["Ask about CDAI target."]


def test_collect_report_items_filters_dedupes_and_limits():
    summaries = [
        {"clinician_discussion_points": ["Ask about CDAI target.", "ask about cdai target.", "No safety concerns captured."]},
        {"actionable_implications": ["Track morning stiffness.", "Track CRP."]},
    ]

    assert collect_report_items(
        summaries,
        ("clinician_discussion_points", "actionable_implications"),
        max_items=2,
    ) == ["Ask about CDAI target.", "Track morning stiffness."]


def test_evidence_label_defaults_and_theme_inference():
    assert evidence_label({}) == "unknown, unknown scope"

    themes = infer_report_themes(
        [
            {"title": "DAS28 treat to target with methotrexate safety"},
            {"main_findings": ["CDAI treat to target and Boolean remission scoring"]},
        ],
        limit=2,
    )

    assert themes == ["treat-to-target and remission scoring", "medication strategy"]
