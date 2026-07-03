from agent_skills import qwen_orchestrator
from agent_skills.qwen_orchestrator_helpers import (
    finalized_harvested_context,
    harvested_context_section,
    package_name_from_requirement,
    search_name_for_package,
)


def test_qwen_orchestrator_exposes_helpers():
    assert qwen_orchestrator._finalized_harvested_context is finalized_harvested_context
    assert qwen_orchestrator._harvested_context_section is harvested_context_section
    assert qwen_orchestrator._package_name_from_requirement is package_name_from_requirement
    assert qwen_orchestrator._search_name_for_package is search_name_for_package


def test_package_name_from_requirement_preserves_existing_split_rules():
    assert package_name_from_requirement("requests==2.31.0") == "requests"
    assert package_name_from_requirement("httpx>=0.27  # client") == "httpx"
    assert package_name_from_requirement("pydantic[email]<=2.0") == "pydantic"
    assert package_name_from_requirement("  # comment only") is None
    assert package_name_from_requirement("   ") is None


def test_search_name_for_package_converts_dashes_to_underscores():
    assert search_name_for_package("google-cloud-storage") == "google_cloud_storage"
    assert search_name_for_package("requests") == "requests"


def test_harvested_context_section_limits_lines_and_preserves_header_shape():
    stdout = "\n".join(f"line {idx}" for idx in range(1, 8))
    assert harvested_context_section("def ", stdout, max_lines=3) == (
        "--- Matches for 'def ' ---\nline 1\nline 2\nline 3\n\n"
    )
    assert harvested_context_section("def ", "") == ""


def test_finalized_harvested_context_uses_fallback_when_empty():
    assert finalized_harvested_context("") == "No idiomatic context harvested."
    assert finalized_harvested_context("context") == "context"
