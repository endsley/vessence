from jane_web.evidence_context import (
    append_required_memory_evidence,
    initial_evidence_metadata,
    prepend_architecture_context,
)


def test_initial_evidence_metadata_matches_pipeline_defaults():
    assert initial_evidence_metadata() == {
        "required": False,
        "requires_code": False,
        "requires_memory": False,
        "memory_evidence": False,
        "memory_chars": 0,
        "memory_chars_after_dedup": 0,
        "architecture_context_chars": 0,
    }


def test_prepend_architecture_context_wraps_verify_block():
    assert prepend_architecture_context("VERIFY", "") == "VERIFY"

    wrapped = prepend_architecture_context("VERIFY", "Architecture snapshot")

    assert wrapped.startswith("<jane_architecture>\n")
    assert "Authoritative snapshot of Jane's system." in wrapped
    assert "Architecture snapshot\n</jane_architecture>\n\nVERIFY" in wrapped


def test_append_required_memory_evidence_ignores_blank_and_wraps_present_text():
    assert append_required_memory_evidence("VERIFY", "") == "VERIFY"
    assert append_required_memory_evidence("VERIFY", "  ") == "VERIFY"

    assert append_required_memory_evidence("VERIFY", "memory hit") == (
        "VERIFY\n\n[REQUIRED CHROMA MEMORY EVIDENCE]\n"
        "memory hit"
        "\n[END REQUIRED CHROMA MEMORY EVIDENCE]"
    )
