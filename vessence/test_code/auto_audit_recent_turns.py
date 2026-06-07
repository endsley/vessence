from __future__ import annotations

import ast
import datetime as dt
import inspect
import json
import re
from pathlib import Path
from unittest.mock import Mock

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "vault_web" / "recent_turns.py"

PUBLIC_API = {
    "add",
    "get_recent",
    "clear",
    "count",
    "add_structured",
    "get_recent_structured",
    "get_active_state",
    "maybe_idle_flush",
}


@pytest.fixture()
def recent_turns(tmp_path, monkeypatch):
    db_path = tmp_path / "vault_web" / "vault_web.db"
    monkeypatch.setenv("VAULT_WEB_DB_PATH", str(db_path))

    from vault_web import database

    monkeypatch.setattr(database, "DB_PATH", str(db_path), raising=False)
    database.init_db()

    import vault_web.recent_turns as module

    return module


@pytest.fixture()
def module_source() -> str:
    return MODULE_PATH.read_text()


@pytest.fixture()
def module_ast(module_source: str) -> ast.Module:
    return ast.parse(module_source)


def _sqlite_timestamp(seconds_ago: int = 0) -> str:
    return (dt.datetime.now(dt.UTC) - dt.timedelta(seconds=seconds_ago)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _iso_timestamp(seconds_from_now: int = 0) -> str:
    return (dt.datetime.now(dt.UTC) + dt.timedelta(seconds=seconds_from_now)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _all_rows(recent_turns, session_id: str | None = None) -> list[dict]:
    sql = (
        "SELECT id, session_id, summary, created_at, structured, schema_version "
        "FROM recent_turns"
    )
    params: tuple = ()
    if session_id is not None:
        sql += " WHERE session_id = ?"
        params = (session_id,)
    sql += " ORDER BY id ASC"
    with recent_turns.get_db() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _insert_recent_row(
    recent_turns,
    session_id: str,
    summary: str = "summary",
    *,
    created_at: str | None = None,
    structured: dict | str | None = None,
    schema_version: int = 0,
) -> None:
    if isinstance(structured, dict):
        structured = json.dumps(structured, ensure_ascii=True)
    with recent_turns.get_db() as conn:
        conn.execute(
            """
            INSERT INTO recent_turns
                (session_id, summary, created_at, structured, schema_version)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session_id,
                summary,
                created_at or _sqlite_timestamp(),
                structured,
                schema_version,
            ),
        )


def _module_level_dict_assignments(tree: ast.Module) -> dict[str, ast.Dict]:
    mappings: dict[str, ast.Dict] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    mappings[target.id] = node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and isinstance(node.value, ast.Dict)
        ):
            mappings[node.target.id] = node.value
    return mappings


def test_public_api_matches_docstring(recent_turns):
    for name in PUBLIC_API:
        assert callable(getattr(recent_turns, name)), f"missing public API {name}"

    assert recent_turns.DEFAULT_MAX_TURNS == 20
    assert recent_turns.STRUCTURED_SCHEMA_VERSION == 1
    assert recent_turns.IDLE_FLUSH_SECONDS == 30


def test_database_schema_has_documented_recent_turns_columns_and_index(recent_turns):
    with recent_turns.get_db() as conn:
        columns = {
            row["name"]: row
            for row in conn.execute("PRAGMA table_info(recent_turns)").fetchall()
        }
        indexes = {
            row["name"]
            for row in conn.execute("PRAGMA index_list(recent_turns)").fetchall()
        }

    assert {
        "id",
        "session_id",
        "summary",
        "created_at",
        "structured",
        "schema_version",
    } <= set(columns)
    assert columns["summary"]["notnull"] == 1
    assert columns["session_id"]["notnull"] == 1
    assert "idx_recent_turns_session_id" in indexes


def test_add_get_count_and_clear_round_trip_oldest_to_newest(recent_turns):
    sid = "behavior-roundtrip"

    for i in range(5):
        recent_turns.add(sid, f"  turn-{i}  ")

    assert recent_turns.count(sid) == 5
    assert recent_turns.get_recent(sid, n=3) == ["turn-2", "turn-3", "turn-4"]
    assert recent_turns.get_recent(sid, n=99) == [
        "turn-0",
        "turn-1",
        "turn-2",
        "turn-3",
        "turn-4",
    ]

    recent_turns.clear(sid)
    assert recent_turns.count(sid) == 0
    assert recent_turns.get_recent(sid) == []


def test_fifo_eviction_is_true_fifo_and_session_scoped(recent_turns):
    for i in range(5):
        recent_turns.add("session-a", f"a-{i}", max_keep=3)
    for i in range(2):
        recent_turns.add("session-b", f"b-{i}", max_keep=3)

    assert recent_turns.count("session-a") == 3
    assert recent_turns.get_recent("session-a", n=20) == ["a-2", "a-3", "a-4"]
    assert recent_turns.get_recent("session-b", n=20) == ["b-0", "b-1"]


def test_zero_keep_deletes_inserted_turn_and_keeps_other_sessions(recent_turns):
    recent_turns.add("keep-zero", "gone", max_keep=0)
    recent_turns.add("other", "still here", max_keep=20)

    assert recent_turns.count("keep-zero") == 0
    assert recent_turns.get_recent("other") == ["still here"]


def test_get_recent_zero_limit_returns_empty_list(recent_turns):
    recent_turns.add("limit-zero", "one")
    recent_turns.add("limit-zero", "two")

    assert recent_turns.get_recent("limit-zero", n=0) == []
    assert recent_turns.get_recent_structured("limit-zero", n=0) == []


def test_whitespace_and_empty_inputs_are_noops_without_db_rows(recent_turns):
    recent_turns.add("", "message")
    recent_turns.add("empty-summary", "")
    recent_turns.add("blank-summary", " \n\t ")
    recent_turns.add_structured("", {"summary": "message"})
    recent_turns.add_structured("empty-record", {})

    assert _all_rows(recent_turns) == []
    assert recent_turns.get_recent("") == []
    assert recent_turns.get_recent_structured("") == []
    assert recent_turns.count("") == 0
    assert recent_turns.maybe_idle_flush("") is False


def test_none_inputs_return_neutral_values_without_writing(recent_turns):
    recent_turns.add(None, "message")  # type: ignore[arg-type]
    recent_turns.add("none-summary", None)  # type: ignore[arg-type]
    recent_turns.add_structured(None, {"summary": "message"})  # type: ignore[arg-type]
    recent_turns.add_structured("none-record", None)  # type: ignore[arg-type]
    recent_turns.clear(None)  # type: ignore[arg-type]

    state = recent_turns.get_active_state(None)  # type: ignore[arg-type]

    assert _all_rows(recent_turns) == []
    assert recent_turns.get_recent(None) == []  # type: ignore[arg-type]
    assert recent_turns.get_recent_structured(None) == []  # type: ignore[arg-type]
    assert recent_turns.count(None) == 0  # type: ignore[arg-type]
    assert state == {
        "pending_action": None,
        "pending_turn_id": None,
        "last_intent": "",
        "last_entities": {},
        "recent_summaries": [],
    }


def test_malformed_summary_type_does_not_write_partial_row(recent_turns):
    try:
        recent_turns.add("bad-summary", object())  # type: ignore[arg-type]
    except (AttributeError, TypeError):
        pass

    assert recent_turns.count("bad-summary") == 0


@pytest.mark.parametrize("bad_record", ["not a mapping", object(), [("ok", "x", "y")]])
def test_malformed_structured_record_type_does_not_corrupt_db(
    recent_turns, bad_record, caplog
):
    caplog.set_level("WARNING")

    recent_turns.add_structured("bad-record", bad_record)  # type: ignore[arg-type]

    assert recent_turns.count("bad-record") == 0
    assert "recent_turns.add_structured failed" in caplog.text


def test_non_json_serializable_structured_record_is_rejected_without_partial_row(
    recent_turns, caplog
):
    caplog.set_level("WARNING")

    recent_turns.add_structured(
        "bad-json",
        {
            "summary": "will not serialize",
            "entities": {"bad": object()},
        },
    )

    assert recent_turns.count("bad-json") == 0
    assert "recent_turns.add_structured failed" in caplog.text


def test_very_long_legacy_summary_round_trips_without_truncation(recent_turns):
    sid = "long-legacy"
    long_summary = "x" * 10000

    recent_turns.add(sid, long_summary)

    assert recent_turns.get_recent(sid) == [long_summary]
    assert _all_rows(recent_turns, sid)[0]["summary"] == long_summary


def test_very_long_auto_structured_summary_is_compacted(recent_turns):
    sid = "long-structured"
    recent_turns.add_structured(
        sid,
        {
            "user_text": "u" * 1000,
            "assistant_text": "a" * 1000,
            "intent": "long",
        },
    )

    record = recent_turns.get_recent_structured(sid)[0]

    assert len(record["summary"]) == 600
    assert record["summary"].endswith("...")
    assert recent_turns.get_recent(sid) == [record["summary"]]


def test_compact_formatter_collapses_internal_newlines_and_strips_edges(recent_turns):
    summary = recent_turns._format_turn_compact(" hi\nthere ", " ok\nJane ")

    assert summary == "user: hi there\njane: ok Jane"


def test_add_structured_normalizes_defaults_and_overwrites_session_id(recent_turns):
    sid = "structured-defaults"

    recent_turns.add_structured(
        sid,
        {
            "session_id": "wrong-session",
            "user_text": "hello",
            "assistant_text": "hi",
            "intent": "greeting",
            "entities": {"name": "Jane"},
        },
    )

    records = recent_turns.get_recent_structured(sid)
    assert len(records) == 1
    record = records[0]
    assert record["schema_version"] == 1
    assert record["session_id"] == sid
    assert record["intent"] == "greeting"
    assert record["stage"] == "stage2"
    assert record["entities"] == {"name": "Jane"}
    assert re.fullmatch(r"[0-9a-f]{16}", record["turn_id"])
    assert dt.datetime.strptime(record["created_at"], "%Y-%m-%dT%H:%M:%SZ")
    assert record["summary"] == "user: hello\njane: hi"

    row = _all_rows(recent_turns, sid)[0]
    assert row["schema_version"] == 1
    assert json.loads(row["structured"]) == record


def test_add_structured_preserves_caller_summary_for_legacy_readers(recent_turns):
    sid = "structured-summary"

    recent_turns.add_structured(
        sid,
        {
            "summary": "custom caller summary",
            "user_text": "ignored for summary",
            "assistant_text": "also ignored",
            "intent": "custom",
        },
    )

    assert recent_turns.get_recent(sid) == ["custom caller summary"]
    assert recent_turns.get_recent_structured(sid)[0]["summary"] == (
        "custom caller summary"
    )


def test_structured_fifo_eviction_preserves_newest_records_oldest_first(recent_turns):
    sid = "structured-fifo"
    for i in range(6):
        recent_turns.add_structured(
            sid,
            {
                "turn_id": f"turn-{i}",
                "summary": f"summary-{i}",
                "intent": f"intent-{i}",
            },
            max_keep=4,
        )

    records = recent_turns.get_recent_structured(sid, n=20)

    assert [record["turn_id"] for record in records] == [
        "turn-2",
        "turn-3",
        "turn-4",
        "turn-5",
    ]
    assert recent_turns.get_recent(sid, n=20) == [
        "summary-2",
        "summary-3",
        "summary-4",
        "summary-5",
    ]


def test_get_recent_structured_synthesizes_legacy_rows(recent_turns):
    sid = "legacy-row"
    recent_turns.add(sid, "user: hi / jane: hello")

    record = recent_turns.get_recent_structured(sid)[0]

    assert record == {
        "schema_version": 0,
        "summary": "user: hi / jane: hello",
        "stage": "legacy",
        "intent": "",
        "user_text": "",
        "assistant_text": "",
    }


def test_malformed_structured_json_falls_back_to_legacy_record(recent_turns):
    sid = "malformed-json-row"
    _insert_recent_row(
        recent_turns,
        sid,
        summary="fallback summary",
        structured="{not valid json",
        schema_version=1,
    )

    record = recent_turns.get_recent_structured(sid)[0]

    assert record["schema_version"] == 0
    assert record["summary"] == "fallback summary"
    assert record["stage"] == "legacy"


def test_get_active_state_returns_newest_pending_intent_entities_and_summaries(
    recent_turns,
):
    sid = "active-state"
    recent_turns.add_structured(
        sid,
        {
            "turn_id": "older",
            "summary": "older summary",
            "intent": "weather",
            "entities": {"city": "Boston"},
            "pending_action": {
                "type": "STAGE2_FOLLOWUP",
                "handler_class": "weather",
                "status": "awaiting_user",
                "data": {"awaiting": "city"},
            },
        },
    )
    recent_turns.add_structured(
        sid,
        {
            "turn_id": "newer",
            "summary": "newer summary",
            "intent": "timer",
            "entities": {"duration_ms": 300000},
            "pending_action": {
                "type": "STAGE2_FOLLOWUP",
                "handler_class": "timer",
                "status": "open",
                "data": {"awaiting": "label"},
            },
        },
    )

    state = recent_turns.get_active_state(sid)

    assert state["pending_turn_id"] == "newer"
    assert state["pending_action"]["handler_class"] == "timer"
    assert state["last_intent"] == "timer"
    assert state["last_entities"] == {"duration_ms": 300000}
    assert state["recent_summaries"] == ["older summary", "newer summary"]


def test_get_active_state_resolved_handler_suppresses_older_open_pending(
    recent_turns,
):
    sid = "resolved-suppresses"
    recent_turns.add_structured(
        sid,
        {
            "turn_id": "open",
            "summary": "open timer",
            "pending_action": {
                "type": "STAGE2_FOLLOWUP",
                "handler_class": "timer",
                "status": "awaiting_user",
                "data": {"awaiting": "label"},
            },
        },
    )
    recent_turns.add_structured(
        sid,
        {
            "turn_id": "resolved",
            "summary": "resolved timer",
            "pending_action": {
                "type": "STAGE2_FOLLOWUP",
                "handler_class": "timer",
                "status": "resolved",
            },
        },
    )

    state = recent_turns.get_active_state(sid)

    assert state["pending_action"] is None
    assert state["pending_turn_id"] is None


def test_get_active_state_cancelled_type_suppresses_older_type_only_pending(
    recent_turns,
):
    sid = "cancelled-type"
    recent_turns.add_structured(
        sid,
        {
            "turn_id": "open",
            "summary": "stage3 waiting",
            "pending_action": {
                "type": "STAGE3_FOLLOWUP",
                "status": "awaiting_user",
                "question": "Which one?",
            },
        },
    )
    recent_turns.add_structured(
        sid,
        {
            "turn_id": "cancelled",
            "summary": "cancelled waiting",
            "pending_action": {
                "type": "STAGE3_FOLLOWUP",
                "status": "cancelled",
            },
        },
    )

    assert recent_turns.get_active_state(sid)["pending_action"] is None


def test_pending_active_status_and_expiration_rules(recent_turns):
    assert recent_turns._pending_is_active(None) is False
    assert recent_turns._pending_is_active({}) is False
    assert recent_turns._pending_is_active({"status": "awaiting_user"}) is True
    assert recent_turns._pending_is_active({"status": "open"}) is True
    assert recent_turns._pending_is_active({"status": "resolved"}) is False
    assert recent_turns._pending_is_active({"status": "cancelled"}) is False
    assert recent_turns._pending_is_active({"expires_at": _iso_timestamp(60)}) is True
    assert recent_turns._pending_is_active({"expires_at": _iso_timestamp(-60)}) is False
    assert recent_turns._pending_is_active({"expires_at": "not-a-date"}) is True


def test_get_active_state_ignores_expired_pending_actions(recent_turns):
    sid = "expired-pending"
    recent_turns.add_structured(
        sid,
        {
            "turn_id": "expired",
            "summary": "expired",
            "pending_action": {
                "type": "SEND_MESSAGE_CONFIRMATION",
                "status": "awaiting_user",
                "expires_at": _iso_timestamp(-120),
            },
        },
    )

    assert recent_turns.get_active_state(sid)["pending_action"] is None


def test_malformed_pending_expiration_is_treated_as_active(recent_turns):
    sid = "malformed-expiration"
    recent_turns.add_structured(
        sid,
        {
            "turn_id": "malformed",
            "summary": "malformed expiration",
            "pending_action": {
                "type": "SEND_MESSAGE_CONFIRMATION",
                "status": "awaiting_user",
                "expires_at": "tomorrow-ish",
                "data": {"draft_id": "d1"},
            },
        },
    )

    state = recent_turns.get_active_state(sid)

    assert state["pending_turn_id"] == "malformed"
    assert state["pending_action"]["data"] == {"draft_id": "d1"}


def test_maybe_idle_flush_returns_false_for_empty_missing_and_recent_sessions(
    recent_turns,
):
    assert recent_turns.maybe_idle_flush("", idle_seconds=30) is False
    assert recent_turns.maybe_idle_flush("missing", idle_seconds=30) is False

    _insert_recent_row(
        recent_turns,
        "recent",
        "recent row",
        created_at=_sqlite_timestamp(seconds_ago=5),
    )

    assert recent_turns.maybe_idle_flush("recent", idle_seconds=30) is False
    assert recent_turns.get_recent("recent") == ["recent row"]


def test_maybe_idle_flush_deletes_only_stale_rows_for_target_session(recent_turns):
    _insert_recent_row(
        recent_turns,
        "stale-target",
        "old target",
        created_at=_sqlite_timestamp(seconds_ago=120),
    )
    _insert_recent_row(
        recent_turns,
        "stale-other",
        "old other",
        created_at=_sqlite_timestamp(seconds_ago=120),
    )

    assert recent_turns.maybe_idle_flush("stale-target", idle_seconds=30) is True

    assert recent_turns.get_recent("stale-target") == []
    assert recent_turns.get_recent("stale-other") == ["old other"]


def test_maybe_idle_flush_skips_active_pending_action_even_when_stale(recent_turns):
    sid = "stale-active-pending"
    record = {
        "schema_version": 1,
        "turn_id": "pending",
        "session_id": sid,
        "created_at": _iso_timestamp(-120),
        "summary": "confirm send",
        "user_text": "tell Bob hi",
        "assistant_text": "Send it?",
        "stage": "stage2",
        "intent": "send message",
        "pending_action": {
            "type": "SEND_MESSAGE_CONFIRMATION",
            "status": "awaiting_user",
            "expires_at": _iso_timestamp(120),
            "data": {"draft_id": "d1"},
        },
    }
    _insert_recent_row(
        recent_turns,
        sid,
        "confirm send",
        created_at=_sqlite_timestamp(seconds_ago=120),
        structured=record,
        schema_version=1,
    )

    assert recent_turns.maybe_idle_flush(sid, idle_seconds=30) is False
    assert recent_turns.count(sid) == 1


def test_maybe_idle_flush_flushes_expired_pending_action(recent_turns):
    sid = "stale-expired-pending"
    record = {
        "schema_version": 1,
        "turn_id": "expired",
        "session_id": sid,
        "created_at": _iso_timestamp(-120),
        "summary": "expired confirmation",
        "user_text": "tell Bob hi",
        "assistant_text": "Send it?",
        "stage": "stage2",
        "intent": "send message",
        "pending_action": {
            "type": "SEND_MESSAGE_CONFIRMATION",
            "status": "awaiting_user",
            "expires_at": _iso_timestamp(-60),
            "data": {"draft_id": "d1"},
        },
    }
    _insert_recent_row(
        recent_turns,
        sid,
        "expired confirmation",
        created_at=_sqlite_timestamp(seconds_ago=120),
        structured=record,
        schema_version=1,
    )

    assert recent_turns.maybe_idle_flush(sid, idle_seconds=30) is True
    assert recent_turns.count(sid) == 0


def test_maybe_idle_flush_preserves_row_written_after_staleness_check(
    recent_turns, monkeypatch
):
    sid = "concurrent-writer"
    _insert_recent_row(
        recent_turns,
        sid,
        "old stale row",
        created_at=_sqlite_timestamp(seconds_ago=120),
    )

    def insert_concurrent_row(_session_id):
        recent_turns.add(_session_id, "new concurrent row")
        return {"pending_action": None}

    monkeypatch.setattr(recent_turns, "get_active_state", insert_concurrent_row)

    assert recent_turns.maybe_idle_flush(sid, idle_seconds=30) is True
    assert recent_turns.get_recent(sid) == ["new concurrent row"]


def test_maybe_idle_flush_invalid_created_at_is_non_destructive(recent_turns):
    sid = "invalid-created-at"
    _insert_recent_row(
        recent_turns,
        sid,
        "bad timestamp",
        created_at="not-a-sqlite-date",
    )

    assert recent_turns.maybe_idle_flush(sid, idle_seconds=30) is False
    assert recent_turns.get_recent(sid) == ["bad timestamp"]


def test_db_failure_paths_log_and_return_neutral_values(recent_turns, monkeypatch, caplog):
    caplog.set_level("WARNING")

    def broken_get_db():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(recent_turns, "get_db", broken_get_db)

    recent_turns.add("db-down", "summary")
    recent_turns.clear("db-down")
    recent_turns.add_structured("db-down", {"summary": "structured"})

    assert recent_turns.get_recent("db-down") == []
    assert recent_turns.get_recent_structured("db-down") == []
    assert recent_turns.count("db-down") == 0
    assert recent_turns.maybe_idle_flush("db-down") is False
    assert "recent_turns.add failed" in caplog.text
    assert "recent_turns.clear failed" in caplog.text
    assert "recent_turns.add_structured failed" in caplog.text
    assert "recent_turns.get_recent failed" in caplog.text
    assert "recent_turns.get_recent_structured failed" in caplog.text
    assert "recent_turns.count failed" in caplog.text
    assert "recent_turns.maybe_idle_flush failed" in caplog.text


def test_add_uses_bound_db_params_for_insert_and_fifo_trim(recent_turns, monkeypatch):
    real_get_db = recent_turns.get_db
    calls: list[tuple[str, tuple]] = []

    class RecordingConnection:
        def __init__(self):
            self._conn = real_get_db()

        def __enter__(self):
            self._conn.__enter__()
            return self

        def __exit__(self, exc_type, exc, tb):
            try:
                return self._conn.__exit__(exc_type, exc, tb)
            finally:
                self._conn.close()

        def execute(self, sql, params=()):
            calls.append((sql, tuple(params)))
            return self._conn.execute(sql, params)

    monkeypatch.setattr(recent_turns, "get_db", RecordingConnection)

    recent_turns.add("query-spy", "hello", max_keep=7)

    assert len(calls) == 2
    assert "INSERT INTO recent_turns" in calls[0][0]
    assert calls[0][1] == ("query-spy", "hello")
    assert "DELETE FROM recent_turns" in calls[1][0]
    assert calls[1][1] == ("query-spy", "query-spy", 7)


def test_no_llm_provider_imports_or_calls_exist_in_fast_fifo_module(module_ast):
    forbidden_fragments = {
        "openai",
        "anthropic",
        "ollama",
        "litellm",
        "generativeai",
        "genai",
        "local_llm",
        "call_llm",
        "stage1_classify",
    }
    offenders: set[str] = set()

    for node in ast.walk(module_ast):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            names.extend(alias.name for alias in node.names)
            for name in names:
                lowered = name.lower()
                if any(fragment in lowered for fragment in forbidden_fragments):
                    offenders.add(name)
        elif isinstance(node, ast.Name):
            lowered = node.id.lower()
            if any(fragment == lowered for fragment in forbidden_fragments):
                offenders.add(node.id)
        elif isinstance(node, ast.Attribute):
            lowered = node.attr.lower()
            if any(fragment == lowered for fragment in forbidden_fragments):
                offenders.add(node.attr)

    assert offenders == set()


def test_structural_no_mapping_lookup_table_or_registry_is_present(module_ast):
    mappings = _module_level_dict_assignments(module_ast)

    assert mappings == {}, (
        "recent_turns is a FIFO storage module. If a module-level mapping, "
        "lookup table, or registry is added, add reachability and contradiction "
        "tests for every key and value."
    )


def test_structural_delete_statements_are_session_scoped(module_source):
    delete_literals = [
        node.value
        for node in ast.walk(ast.parse(module_source))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and "DELETE FROM recent_turns" in node.value
    ]

    assert delete_literals, "expected destructive DELETE statements to be audited"
    for sql in delete_literals:
        normalized = " ".join(sql.split())
        assert "WHERE session_id = ?" in normalized


def test_structural_idle_flush_delete_is_timestamp_guarded(module_source):
    normalized = " ".join(module_source.split())

    assert (
        "DELETE FROM recent_turns WHERE session_id = ? AND created_at <= ?"
        in normalized
    )


def test_structural_idle_flush_uses_strict_threshold_not_borderline_flush(
    module_ast,
):
    maybe_idle_flush = next(
        node
        for node in module_ast.body
        if isinstance(node, ast.FunctionDef) and node.name == "maybe_idle_flush"
    )
    comparisons = [
        node
        for node in ast.walk(maybe_idle_flush)
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name)
    ]

    has_age_lte_idle = any(
        comp.left.id == "age"
        and any(isinstance(op, ast.LtE) for op in comp.ops)
        and any(
            isinstance(comparator, ast.Name) and comparator.id == "idle_seconds"
            for comparator in comp.comparators
        )
        for comp in comparisons
    )
    has_age_gte_idle = any(
        comp.left.id == "age"
        and any(isinstance(op, ast.GtE) for op in comp.ops)
        and any(
            isinstance(comparator, ast.Name) and comparator.id == "idle_seconds"
            for comparator in comp.comparators
        )
        for comp in comparisons
    )

    assert has_age_lte_idle
    assert not has_age_gte_idle


@pytest.mark.parametrize(
    ("func_name", "args"),
    [
        ("add", ("", "summary")),
        ("add", ("sid", "")),
        ("clear", ("",)),
        ("count", ("",)),
        ("get_recent", ("",)),
        ("get_recent_structured", ("",)),
        ("maybe_idle_flush", ("",)),
        ("add_structured", ("", {"summary": "summary"})),
        ("add_structured", ("sid", {})),
    ],
)
def test_structural_empty_input_guards_run_before_db_access(
    recent_turns, monkeypatch, func_name, args
):
    get_db = Mock(side_effect=AssertionError("empty input should not touch DB"))
    monkeypatch.setattr(recent_turns, "get_db", get_db)

    result = getattr(recent_turns, func_name)(*args)

    assert result in (None, 0, [], False)
    get_db.assert_not_called()


def test_structural_no_direct_message_send_or_conversation_end_actions(module_ast):
    forbidden_function_names = {
        "send_message",
        "sms_send",
        "sms_send_direct",
        "email_send",
        "delete_message",
        "delete_email",
        "end_conversation",
    }
    function_names = {
        node.name for node in ast.walk(module_ast) if isinstance(node, ast.FunctionDef)
    }

    assert function_names.isdisjoint(forbidden_function_names)


def test_structural_no_handler_dispatch_registry_or_handler_entrypoint(
    module_ast, module_source
):
    class_names = {
        node.name for node in ast.walk(module_ast) if isinstance(node, ast.ClassDef)
    }
    function_names = {
        node.name for node in ast.walk(module_ast) if isinstance(node, ast.FunctionDef)
    }
    suspicious_registry_names = {
        name
        for name in _module_level_dict_assignments(module_ast)
        if any(marker in name.lower() for marker in ("registry", "handler", "dispatch"))
    }

    assert class_names == set()
    assert "handle" not in function_names
    assert suspicious_registry_names == set()
    assert "class_registry" not in module_source


def test_public_functions_keep_documented_return_shapes(recent_turns):
    assert recent_turns.add("shape", "summary") is None
    assert recent_turns.clear("shape-missing") is None
    assert isinstance(recent_turns.get_recent("shape"), list)
    assert all(isinstance(item, str) for item in recent_turns.get_recent("shape"))
    assert isinstance(recent_turns.get_recent_structured("shape"), list)
    assert all(
        isinstance(item, dict) for item in recent_turns.get_recent_structured("shape")
    )
    assert isinstance(recent_turns.get_active_state("shape"), dict)
    assert isinstance(recent_turns.count("shape"), int)
    assert isinstance(recent_turns.maybe_idle_flush("shape"), bool)


def test_documented_signatures_do_not_gain_unreviewed_required_params(recent_turns):
    expected = {
        "add": ["session_id", "summary", "max_keep"],
        "get_recent": ["session_id", "n"],
        "clear": ["session_id"],
        "count": ["session_id"],
        "add_structured": ["session_id", "record", "max_keep"],
        "get_recent_structured": ["session_id", "n"],
        "get_active_state": ["session_id", "lookback"],
    }

    for func_name, params in expected.items():
        assert list(inspect.signature(getattr(recent_turns, func_name)).parameters) == (
            params
        )
