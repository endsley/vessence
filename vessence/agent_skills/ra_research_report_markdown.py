"""Markdown assembly helpers for app-facing RA research reports."""

from __future__ import annotations

import textwrap
from typing import Any

from agent_skills.ra_research_report_items import (
    collect_report_items,
    evidence_label,
    filter_report_items,
    infer_report_themes,
    is_low_value_summary,
    low_value_reason,
    summary_signal_score,
)
from agent_skills.ra_research_report_tables import action_plan_evidence_rows, recommendation_scheme_evidence_rows
from agent_skills.ra_research_text import clean_text, dedupe_summaries, list_values, text_value


def list_to_markdown(values: Any) -> str:
    if isinstance(values, list) and values:
        return "\n".join(f"- {clean_text(str(value))}" for value in values if str(value).strip())
    if values:
        return f"- {clean_text(str(values))}"
    return "- None captured."


def source_heading(summary: dict[str, Any], max_chars: int = 120) -> str:
    source_id = summary.get("source_id", "")
    title = text_value(summary.get("title", "Untitled source"), max_chars)
    return f"`{source_id}` {title}" if source_id else title


def default_clinician_questions() -> list[str]:
    return [
        "Which validated target is being used for Kathia right now: CDAI, SDAI, DAS28, RAPID3, or ACR/EULAR Boolean remission?",
        "If she is not at target, what is the next clinician-supervised adjustment and the reassessment date?",
        "Are symptoms tracking active inflammation, residual pain/fatigue, medication side effects, or another process?",
        "What medication safety labs, infection precautions, vaccine updates, or steroid-sparing steps are relevant to her current regimen?",
    ]


def default_tracking_items() -> list[str]:
    return [
        "Morning stiffness duration, pain, fatigue, function, flares, and swollen/tender joint pattern.",
        "Current medications, missed doses, side effects, infections, steroid/NSAID use, and what improves or worsens symptoms.",
        "Recent ESR/CRP, clinician disease activity score, tender/swollen joint count, and medication safety labs from visits.",
    ]


def build_deterministic_compressed_context(
    summaries: list[dict[str, Any]],
    *,
    updated_label: str,
    mission_statement: str,
) -> str:
    lines = [
        "# RA Research Compressed Context",
        "",
        f"Updated: {updated_label}",
        "",
        f"Mission: {mission_statement}",
        "",
        "## Evidence Learned So Far",
    ]
    for summary in summaries[:40]:
        lines.append(
            f"- `{summary.get('source_id', '')}` {summary.get('title', '')}: "
            f"{clean_text(str(summary.get('remission_relevance', '')))[:350]} "
            f"(scope: {summary.get('evidence_scope', '')}; artifact: {summary.get('artifact_dir', '')})"
        )
    lines.extend(
        [
            "",
            "## Standing Safety Boundary",
            "- This is research support, not medical advice.",
            "- Medication, supplement, steroid, biologic, or JAK inhibitor changes require Kathia's rheumatologist.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def build_deterministic_action_plan(
    summaries: list[dict[str, Any]],
    *,
    updated_label: str,
) -> str:
    evidence_rows = action_plan_evidence_rows(summaries)
    header = textwrap.dedent(
        f"""\
        # RA Recommendation Plan

        Last updated: {updated_label}

        ## Executive Summary

        Current evidence base is still small. The best-supported strategy so far
        is rheumatologist-led treat-to-target care with validated disease-activity
        monitoring and shared decisions. This plan is a research/action dossier
        for Chieh and Kathia to discuss with her clinician.

        ## At-Home Actions Now

        1. **Build a symptom and treatment log.** Track morning stiffness, pain,
           fatigue, function, flares, side effects, infections, missed doses, and
           what improves or worsens symptoms.
        2. **Prepare a one-page rheumatology visit brief.** Bring current symptoms,
           medication list, side effects, flare history, and top questions.
        3. **Use adjunct habits as symptom support.** Food, sleep, movement, stress,
           oral health, and trigger tracking can be started carefully, but they do
           not replace disease-control treatment.

        ## Tracking Steps

        - Weekly: symptoms, morning stiffness, fatigue, function, flares, side
          effects, missed doses, diet/sleep/activity notes.
        - At visits: clinician disease activity score, labs, medication plan,
          safety monitoring, target date for reassessment.

        ## Tests To Discuss

        1. **Define the target and score.** Ask which validated score is being used
           to judge remission or low disease activity: CDAI, SDAI, DAS28, or
           ACR/EULAR Boolean remission criteria.
        2. **Make medication strategy explicit with the rheumatologist.** If not
           at target, ask what evidence-supported escalation or adjustment is
           appropriate for Kathia's current regimen and risk profile.

        - Disease activity score used by the rheumatologist.
        - ESR/CRP trends.
        - Tender/swollen joint count.
        - RF/anti-CCP status if not already known.
        - Medication-specific safety labs, especially for DMARDs.
        - Imaging such as ultrasound/MRI only if the rheumatologist thinks it
          would clarify inflammatory activity versus residual pain.

        ## Food/Diet Options

        - Treat diet as an adjunct, not a replacement for disease control.
        - Research priority: Mediterranean/anti-inflammatory dietary patterns,
          omega-3/fish intake, weight/metabolic health, alcohol interactions with
          medication safety, and trigger tracking.
        - No supplement should be added without medication-interaction review.

        ## Lifestyle Changes

        - Low-impact aerobic activity and strength/mobility work as tolerated.
        - Sleep regularity and fatigue tracking.
        - Stress reduction as symptom-support, not as a standalone RA treatment.
        - Smoking avoidance and oral/periodontal health review.

        ## Medical Strategy Questions

        - What is Kathia's current target and timeline for reassessment?
        - If she is not at target, what is the next clinician-supervised step?
        - Are steroids being used, and what is the steroid-sparing plan?
        - What safety monitoring is required for her exact medications?

        ## Emerging Technology / Neuromodulation

        - Research priority: vagus-nerve stimulation, auricular stimulation,
          bioelectronic medicine, wearables, and digital symptom tracking.
        - Treat as experimental/clinician-discussion until enough high-quality RA
          evidence is cached.

        ## What Not To Do Without Clinician

        - Do not stop/start/change DMARDs, biologics, JAK inhibitors, steroids,
          NSAIDs, or supplements from this dossier alone.

        ## Evidence Matrix

        | Source | Type | Scope | Implication |
        |---|---|---|---|
        """
    ).strip()

    footer = textwrap.dedent(
        """\
        ## What Would Change This Plan

        - Evidence that Kathia is already in objective remission but remains
          symptomatic would shift focus toward residual pain/fatigue mechanisms.
        - Evidence of active inflammation despite treatment would shift focus
          toward clinician-supervised escalation or adjustment.
        - Strong RCT/guideline evidence for a diet, lifestyle intervention, or
          technology would move it from research priority to clinician-discussion
          recommendation.
        """
    ).strip() + "\n"
    return header + "\n" + "\n".join(evidence_rows) + "\n\n" + footer


def build_deterministic_recommendation_scheme(
    summaries: list[dict[str, Any]],
    *,
    updated_label: str,
) -> str:
    evidence_rows = recommendation_scheme_evidence_rows(summaries)
    header = textwrap.dedent(
        f"""\
        # RA Remission / Asymptomatic-State Research Scheme

        Last updated: {updated_label}

        ## Status

        This loop remains active until Chieh explicitly stops it or Kathia is
        confirmed asymptomatic/in sustained remission. The script cannot verify
        Kathia's symptoms directly, so this document treats status as **ongoing**.

        ## Safety Boundary

        This is a research dossier, not medical advice. Medication starts,
        stops, dose changes, biologic/JAK inhibitor choices, steroid use, and
        supplement decisions must go through Kathia's rheumatologist.

        ## Current Working Model

        1. Use treat-to-target care with the rheumatologist: define remission or
           low disease activity as the target, measure disease activity regularly,
           and adjust therapy if the target is not met.
        2. Separate "feels asymptomatic" from validated remission. Ask for the
           specific measure being used: CDAI, SDAI, DAS28, or ACR/EULAR Boolean
           remission criteria.
        3. Keep the medication conversation clinician-led. The research loop
           can prepare questions and evidence summaries, but it should not
           recommend unsupervised DMARD, biologic, JAK inhibitor, or steroid changes.
        4. Track modifiable adjuncts that plausibly affect inflammation or
           symptoms: exercise/strength, sleep, stress, smoking exposure, oral
           health, weight/metabolic health, diet quality, and carefully reviewed
           supplements only when safe with her medications.
        5. Track patient-important symptoms separately: morning stiffness,
           fatigue, pain, function, swollen/tender joints, flares, side effects,
           infections, and work/home impact.

        ## Minimum Data To Personalize This

        - Current RA medications, doses, start dates, missed doses, and side effects.
        - Recent ESR/CRP and the rheumatologist's disease activity score.
        - Tender/swollen joint count if available.
        - Morning stiffness duration, fatigue, pain, sleep, and flare log.
        - Comorbidities, pregnancy plans, infection history, vaccines, and supplement list.

        ## Evidence Register

        | Source | Scope | Remission relevance | Saved artifact |
        |---|---|---|---|
        """
    ).strip()

    footer = textwrap.dedent(
        """\
        ## Next Research Questions

        - Which treat-to-target escalation patterns have the best remission odds
          for patients matching Kathia's current therapy history?
        - Which lifestyle adjuncts have randomized-trial evidence for clinically
          meaningful disease activity, pain, or fatigue improvement?
        - Which predictors distinguish inflammatory activity from residual pain,
          central sensitization, osteoarthritis, or fatigue when formal remission
          criteria are partly met?
        - What monitoring schedule best catches loss of remission early while
          avoiding overtreatment?
        """
    ).strip() + "\n"
    return header + "\n" + "\n".join(evidence_rows) + "\n\n" + footer


def useful_report_summary_groups(
    new_summaries: list[dict[str, Any]],
    all_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    unique_new = dedupe_summaries(new_summaries)
    ranked_new = sorted(unique_new, key=summary_signal_score, reverse=True)
    high_signal = [
        summary for summary in ranked_new
        if summary_signal_score(summary) >= 3 and not is_low_value_summary(summary)
    ][:5]
    low_signal = [
        summary for summary in sorted(unique_new, key=summary_signal_score)
        if is_low_value_summary(summary)
    ][:6]
    themes = infer_report_themes(unique_new) or infer_report_themes(all_summaries[:30])
    return {
        "unique_new": unique_new,
        "ranked_new": ranked_new,
        "high_signal": high_signal,
        "low_signal": low_signal,
        "themes": themes,
    }


def useful_finding_lines(summary: dict[str, Any]) -> list[str]:
    findings = list_values(summary.get("main_findings"), max_items=2, max_chars=260)
    actions = filter_report_items(list_values(summary.get("actionable_implications"), max_items=2, max_chars=240))
    questions = filter_report_items(list_values(summary.get("clinician_discussion_points"), max_items=2, max_chars=240))
    caveats = filter_report_items(list_values(summary.get("limitations"), max_items=1, max_chars=240))
    safety = filter_report_items(list_values(summary.get("safety_concerns"), max_items=1, max_chars=240))
    lines = [
        f"### {source_heading(summary)}",
        f"- Evidence: {evidence_label(summary)}.",
        f"- Why it matters: {text_value(summary.get('remission_relevance'), 340) or 'No remission relevance captured.'}",
    ]
    for finding in findings:
        lines.append(f"- Finding: {finding}")
    for action in actions:
        lines.append(f"- Useful next step: {action}")
    for question in questions:
        lines.append(f"- Clinician question: {question}")
    for caveat in caveats:
        lines.append(f"- Caveat: {caveat}")
    for flag in safety:
        if not flag.lower().startswith("no safety concerns"):
            lines.append(f"- Safety note: {flag}")
    return lines


def source_trace_line(summary: dict[str, Any]) -> str:
    return f"- {source_heading(summary, 120)} | {evidence_label(summary)} | {summary.get('url', '')}"


def build_useful_report_markdown(
    new_summaries: list[dict[str, Any]],
    all_summaries: list[dict[str, Any]],
    codex_result: dict[str, Any] | None,
    source_count: int,
    *,
    recommendation_path: Any = "",
    action_plan_path: Any = "",
    compressed_context_path: Any = "",
    discoveries_path: Any = "",
) -> str:
    groups = useful_report_summary_groups(new_summaries, all_summaries)
    unique_new = groups["unique_new"]
    ranked_new = groups["ranked_new"]
    high_signal = groups["high_signal"]
    low_signal = groups["low_signal"]
    themes = groups["themes"]
    discoveries = list_values((codex_result or {}).get("discoveries"), max_items=5, max_chars=260)
    open_questions = list_values((codex_result or {}).get("open_questions"), max_items=5, max_chars=260)
    useful_for_questions = high_signal or [summary for summary in ranked_new if not is_low_value_summary(summary)]
    safety_flags = collect_report_items(useful_for_questions, ("safety_concerns",), max_items=4)

    lines = [
        "## Bottom Line",
        f"- This run processed {len(unique_new)} unique new or upgraded source summar{'y' if len(unique_new) == 1 else 'ies'}; the cache now has {source_count} sources.",
    ]
    if themes:
        lines.append(f"- Main themes this run: {', '.join(themes)}.")
    if high_signal:
        best = high_signal[0]
        lines.append(
            f"- Highest-value item: {source_heading(best, 95)}. Practical read: "
            f"{text_value(best.get('remission_relevance'), 260) or 'use as background evidence only.'}"
        )
    else:
        lines.append("- No new source rose above the high-signal threshold; treat this run mostly as cache-building.")
    lines.append(
        "- The standing practical path remains clinician-led treat-to-target care, objective disease-activity scoring, symptom tracking, and no unsupervised medication/supplement changes."
    )

    if discoveries:
        lines.extend(["", "## What Changed This Run"])
        lines.extend(f"- {item}" for item in discoveries)
    elif high_signal:
        lines.extend(["", "## What Changed This Run"])
        for summary in high_signal[:4]:
            lines.append(
                f"- {source_heading(summary, 90)}: {text_value(summary.get('remission_relevance'), 260)}"
            )
    else:
        lines.extend(["", "## What Changed This Run", "- Nothing strong enough to change the current plan; the run mostly added background sources."])

    lines.extend(["", "## Most Useful Findings"])
    if not high_signal:
        lines.append("- None this run. The report is flagging this explicitly instead of burying the signal in a source list.")
    for summary in high_signal:
        lines.extend(useful_finding_lines(summary))

    questions = collect_report_items(
        useful_for_questions,
        ("clinician_discussion_points", "actionable_implications"),
        max_items=6,
    ) or default_clinician_questions()
    lines.extend(["", "## Questions For Rheumatologist"])
    lines.extend(f"- {item}" for item in questions)

    tracking = collect_report_items(
        useful_for_questions,
        ("tests_or_monitoring", "lifestyle_implications", "food_diet_implications"),
        max_items=6,
    ) or default_tracking_items()
    lines.extend(["", "## What To Track"])
    lines.extend(f"- {item}" for item in tracking)

    lines.extend(["", "## Safety Flags"])
    if safety_flags:
        lines.extend(f"- {item}" for item in safety_flags)
    else:
        lines.append("- No new specific safety flag was extracted, but medication, supplement, steroid, biologic, JAK inhibitor, NSAID, or device decisions still require the rheumatologist.")

    lines.extend(["", "## Low-Value Or Noisy Sources"])
    if low_signal:
        for summary in low_signal:
            lines.append(f"- {source_heading(summary, 100)}: {low_value_reason(summary)}.")
    else:
        lines.append("- No obvious low-value/noisy source was added this run.")

    next_focus = open_questions or [
        "Prioritize evidence that changes a practical decision for Kathia, not broad background reviews.",
        "Keep separating objective inflammatory activity from residual pain, fatigue, function, and medication side effects.",
        "Prefer guidelines, randomized trials, systematic reviews, and directly RA-focused monitoring evidence over speculative future-tech articles.",
    ]
    lines.extend(["", "## Next Run Focus"])
    lines.extend(f"- {item}" for item in next_focus[:5])

    lines.extend(
        [
            "",
            "## Full Files",
            f"- Living recommendation scheme: `{recommendation_path}`",
            f"- Action plan: `{action_plan_path}`",
            f"- Compressed context for future runs: `{compressed_context_path}`",
            f"- Discoveries log: `{discoveries_path}`",
        ]
    )

    lines.extend(["", "## Source Trace"])
    if unique_new:
        for summary in unique_new:
            lines.append(source_trace_line(summary))
    else:
        lines.append("- No new source trace for this run.")

    return "\n".join(lines).strip() + "\n"


def build_run_report_markdown(
    new_summaries: list[dict[str, Any]],
    all_summaries: list[dict[str, Any]],
    recommendation_text: str,
    action_plan_text: str,
    source_count: int,
    codex_result: dict[str, Any] | None,
    *,
    generated_label: str,
    recommendation_path: Any,
    action_plan_path: Any,
    compressed_context_path: Any,
    latest_codex_synthesis_path: Any,
    discoveries_path: Any,
) -> str:
    useful_report = build_useful_report_markdown(
        new_summaries,
        all_summaries,
        codex_result,
        source_count,
        recommendation_path=recommendation_path,
        action_plan_path=action_plan_path,
        compressed_context_path=compressed_context_path,
        discoveries_path=discoveries_path,
    )
    lines = [
        f"# RA Research Run {generated_label}",
        "",
        f"New or upgraded source summaries: {len(dedupe_summaries(new_summaries))}",
        f"Cached sources: {source_count}",
        f"Recommendation file: `{recommendation_path}`",
        f"Action plan: `{action_plan_path}`",
        f"Compressed context: `{compressed_context_path}`",
        f"Latest Codex synthesis: `{latest_codex_synthesis_path}`",
        f"Discoveries log: `{discoveries_path}`",
        "",
        useful_report,
        "",
        "## New Source Details",
    ]
    unique_new = dedupe_summaries(new_summaries)
    if not unique_new:
        lines.append("- No new sources processed this run; cached recommendation scheme was refreshed.")
    for summary in unique_new:
        lines.extend(
            [
                f"### {summary.get('title', 'Untitled')}",
                f"- Source ID: `{summary.get('source_id', '')}`",
                f"- URL: {summary.get('url', '')}",
                f"- Scope: {summary.get('evidence_scope', '')}",
                f"- Evidence type: {summary.get('study_type', '')}",
                f"- Saved artifact: `{summary.get('artifact_dir', '')}`",
                f"- Remission relevance: {summary.get('remission_relevance', '')}",
                f"- Usefulness label: {'low-value/noisy - ' + low_value_reason(summary) if is_low_value_summary(summary) else 'useful signal'}",
                f"- Signal score: {summary_signal_score(summary)}",
                "",
            ]
        )
    lines.extend(
        [
            "## Standing Action Plan Snapshot",
            "",
            action_plan_text[:3500],
            "",
            "## Standing Scheme Snapshot",
            "",
            recommendation_text[:2500],
        ]
    )
    return "\n".join(lines).strip() + "\n"
