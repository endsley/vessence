import sys
import types

from memory.v1 import janitor_memory
from memory.v1.janitor_code_verification import (
    code_memory_records_from_collection,
    code_memory_verification_sort_key,
    code_verification_report_markdown,
    code_verification_prompt,
    code_verification_result,
    frontier_fix_prompt,
    is_code_memory,
    split_reverification_candidates,
)


def _memory():
    return {
        "id": "abcdef1234567890",
        "topic": "Project: vessence",
        "text": "The jane_web pipeline uses qwen for Stage 2.",
    }


def test_janitor_memory_uses_extracted_code_memory_detector():
    assert janitor_memory._is_code_memory is is_code_memory
    assert is_code_memory("The handler lives in jane_web/main.py")
    assert is_code_memory("Ollama keep_alive changed")
    assert not is_code_memory("Chieh likes tea")


def test_code_memory_records_from_collection_extracts_and_truncates_code_memories():
    records = code_memory_records_from_collection(
        {
            "ids": ["a", "b", "c"],
            "documents": [
                "jane_web/main.py " + ("x" * 600),
                "Chieh likes tea",
                "Ollama keep_alive changed",
            ],
            "metadatas": [
                {"topic": "Project", "code_verified_at": "2026-07-01"},
                {"topic": "Personal"},
                None,
            ],
        },
        max_text_chars=20,
    )

    assert records == [
        {
            "id": "a",
            "text": "jane_web/main.py xxx",
            "topic": "Project",
            "metadata": {"topic": "Project", "code_verified_at": "2026-07-01"},
        },
        {
            "id": "c",
            "text": "Ollama keep_alive ch",
            "topic": "",
            "metadata": {},
        },
    ]


def test_reverification_candidate_helpers_partition_and_sort_oldest_first():
    memories = [
        {"id": "new", "metadata": {}},
        {"id": "fresh", "metadata": {"code_verified_at": "2026-07-03"}},
        {"id": "old", "metadata": {"code_verified_at": "2026-06-01"}},
    ]

    eligible, skipped = split_reverification_candidates(
        memories,
        needs_reverification_fn=lambda meta: meta.get("code_verified_at") != "2026-07-03",
    )
    eligible.sort(key=code_memory_verification_sort_key)

    assert [memory["id"] for memory in eligible] == ["new", "old"]
    assert skipped == 1


def test_code_verification_prompt_preserves_codex_contract():
    prompt = code_verification_prompt(_memory())

    assert prompt.startswith("You are auditing ONE ChromaDB memory")
    assert "MEMORY (id=abcdef123456, topic=Project: vessence):" in prompt
    assert "The jane_web pipeline uses qwen for Stage 2." in prompt
    assert '"verdict": "ACCURATE|STALE|PARTIAL"' in prompt
    assert "no markdown fences" in prompt


def test_frontier_fix_prompt_preserves_frontier_contract():
    prompt = frontier_fix_prompt(
        _memory(),
        {
            "verdict": "STALE",
            "explanation": "Stage 2 changed",
            "corrected_text": "Corrected memory",
        },
    )

    assert prompt.startswith("Codex flagged this ChromaDB memory")
    assert "CODEX VERDICT: STALE" in prompt
    assert "CODEX EXPLANATION: Stage 2 changed" in prompt
    assert "CODEX SUGGESTED CORRECTION: Corrected memory" in prompt
    assert '"action": "update|delete|keep"' in prompt


def test_code_verification_result_and_report_preserve_summary_shape():
    result = code_verification_result(
        checked=3,
        stale=2,
        fixed=1,
        deleted=1,
        errors=0,
        skipped_recent=4,
        details=[
            {"id": "accurate-123456", "action": "accurate", "reason": "ok"},
            {"id": "updated-123456", "action": "updated", "reason": "rewrote"},
            {"id": "deleted-123456", "action": "deleted", "reason": "obsolete"},
        ],
    )

    assert result == {
        "checked": 3,
        "stale": 2,
        "fixed": 1,
        "deleted": 1,
        "errors": 0,
        "skipped_recent": 4,
        "details": [
            {"id": "accurate-123456", "action": "accurate", "reason": "ok"},
            {"id": "updated-123456", "action": "updated", "reason": "rewrote"},
            {"id": "deleted-123456", "action": "deleted", "reason": "obsolete"},
        ],
    }
    assert code_verification_report_markdown(
        timestamp="2026-07-03 12:00",
        result=result,
    ) == (
        "# Memory Verification Report — 2026-07-03 12:00\n\n"
        "Checked: 3 | Stale: 2 | Fixed: 1 | Deleted: 1 | Errors: 0 | Skipped recent: 4\n\n"
        "- **UPDATED** `updated-1234` — rewrote\n"
        "- **DELETED** `deleted-1234` — obsolete\n"
    )


def test_verify_code_memories_uses_split_candidates_without_undefined_name(tmp_path, monkeypatch):
    class FakeCollection:
        def get(self, include):
            assert include == ["documents", "metadatas"]
            return {
                "ids": ["mem-1"],
                "documents": ["The handler lives in jane_web/main.py"],
                "metadatas": [{"topic": "Project"}],
            }

    class FakeClient:
        def get_collection(self, name):
            assert name == "user_memories"
            return FakeCollection()

    fake_self_improve = types.ModuleType("agent_skills.self_improve_log")
    fake_self_improve.log_vocal_summary = lambda **kwargs: None
    monkeypatch.setitem(sys.modules, "agent_skills.self_improve_log", fake_self_improve)
    monkeypatch.setattr(janitor_memory, "get_chroma_client", lambda path: FakeClient())
    monkeypatch.setattr(janitor_memory, "_VESSENCE_HOME", str(tmp_path))
    monkeypatch.setattr(
        janitor_memory,
        "_verify_one_memory",
        lambda mem, codex_timeout=7200: {
            "verdict": "ACCURATE",
            "explanation": "matches source",
        },
    )
    monkeypatch.setattr(
        janitor_memory,
        "_stamp_code_verification",
        lambda *args, **kwargs: {"ok": True, "reason": ""},
    )
    (tmp_path / "configs").mkdir()

    result = janitor_memory.verify_code_memories()

    assert result == {
        "checked": 1,
        "stale": 0,
        "fixed": 0,
        "deleted": 0,
        "errors": 0,
        "skipped_recent": 0,
        "details": [{"id": "mem-1", "action": "accurate", "reason": "matches source"}],
    }
