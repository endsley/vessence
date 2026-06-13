import ast
import re
import sys
import types
from pathlib import Path

import pytest

from jane_web.jane_v2.classes.music_play import handler as music_handler
from jane_web.jane_v2.classes.music_play import metadata as music_metadata


MODULE_PATH = Path(
    "/home/chieh/ambient/vessence/jane_web/jane_v2/classes/music_play/handler.py"
)


def _playlist(pid="playlist-1", name="Test Playlist", tracks=None):
    return {
        "id": pid,
        "name": name,
        "tracks": tracks if tracks is not None else ["one.mp3", "two.mp3"],
    }


def _assert_documented_shape(result):
    assert isinstance(result, dict)
    assert isinstance(result.get("text"), str)
    assert "playlist_id" in result
    assert "playlist_name" in result


def _schema_kind_values():
    schema = music_metadata.PARAMS_SCHEMA["kind"]
    match = re.search(r"one of:\s*([^.]*)\.", schema)
    assert match, "PARAMS_SCHEMA['kind'] must document its enum values"
    return {part.strip() for part in match.group(1).split("|")}


@pytest.fixture
def mocked_playlist_db(monkeypatch):
    state = {"candidates": [], "playlists": {}}
    calls = {"list_playlists": 0, "get_playlist": []}

    vault_pkg = types.ModuleType("vault_web")
    vault_pkg.__path__ = []
    playlists_mod = types.ModuleType("vault_web.playlists")

    def list_playlists():
        calls["list_playlists"] += 1
        return list(state["candidates"])

    def get_playlist(playlist_id):
        calls["get_playlist"].append(playlist_id)
        return state["playlists"].get(playlist_id)

    playlists_mod.list_playlists = list_playlists
    playlists_mod.get_playlist = get_playlist
    monkeypatch.setitem(sys.modules, "vault_web", vault_pkg)
    monkeypatch.setitem(sys.modules, "vault_web.playlists", playlists_mod)
    return state, calls


@pytest.fixture
def mocked_library_resolver(monkeypatch):
    state = {"playlist": None}
    calls = []

    main_mod = types.ModuleType("jane_web.main")

    def create_music_playlist_from_query(query):
        calls.append(query)
        return state["playlist"]

    main_mod.create_music_playlist_from_query = create_music_playlist_from_query
    monkeypatch.setitem(sys.modules, "jane_web.main", main_mod)

    import jane_web

    monkeypatch.setattr(jane_web, "main", main_mod, raising=False)
    return state, calls


def test_none_and_empty_params_escalate_without_external_work(monkeypatch):
    def should_not_match(_query):
        raise AssertionError("playlist DB should not be queried without params")

    def should_not_resolve(_query):
        raise AssertionError("library resolver should not run without params")

    monkeypatch.setattr(music_handler, "_match_existing_playlist", should_not_match)
    monkeypatch.setattr(music_handler, "_ephemeral_from_library", should_not_resolve)

    assert music_handler.handle("", None) is None
    assert music_handler.handle("play music", {}) is None


def test_resume_escalates_without_external_work(monkeypatch):
    def should_not_match(_query):
        raise AssertionError("resume must not query playlists")

    def should_not_resolve(_query):
        raise AssertionError("resume must not create an ephemeral playlist")

    monkeypatch.setattr(music_handler, "_match_existing_playlist", should_not_match)
    monkeypatch.setattr(music_handler, "_ephemeral_from_library", should_not_resolve)

    assert (
        music_handler.handle(
            "continue playing", {"kind": "resume", "query": None}
        )
        is None
    )


@pytest.mark.parametrize("kind", ["", "podcast", "delete", "play music", "unknown"])
def test_missing_or_unknown_kind_escalates_without_side_effects(monkeypatch, kind):
    def should_not_match(_query):
        raise AssertionError("unknown kinds must not query playlists")

    def should_not_resolve(_query):
        raise AssertionError("unknown kinds must not create playlists")

    monkeypatch.setattr(music_handler, "_match_existing_playlist", should_not_match)
    monkeypatch.setattr(music_handler, "_ephemeral_from_library", should_not_resolve)

    assert music_handler.handle("play something", {"kind": kind, "query": "jazz"}) is None


def test_exact_existing_playlist_match_wins_over_v1_library(
    mocked_playlist_db, mocked_library_resolver
):
    db_state, db_calls = mocked_playlist_db
    library_state, library_calls = mocked_library_resolver
    db_state["candidates"] = [{"id": "coldplay", "name": "Coldplay"}]
    db_state["playlists"] = {
        "coldplay": _playlist("coldplay", "Coldplay", ["a.mp3", "b.mp3"])
    }
    library_state["playlist"] = _playlist("tmp", "Playing: coldplay")

    result = music_handler.handle(
        "play coldplay", {"kind": "playlist", "query": "  coldplay  "}
    )

    _assert_documented_shape(result)
    assert result == {
        "text": "Playing Coldplay (2 tracks). [MUSIC_PLAY:coldplay]",
        "playlist_id": "coldplay",
        "playlist_name": "Coldplay",
    }
    assert db_calls == {"list_playlists": 1, "get_playlist": ["coldplay"]}
    assert library_calls == []


def test_partial_existing_playlist_match_uses_vault_db(
    mocked_playlist_db, mocked_library_resolver
):
    db_state, db_calls = mocked_playlist_db
    _library_state, library_calls = mocked_library_resolver
    db_state["candidates"] = [
        {"id": "focus", "name": "Deep Focus Instrumentals"},
        {"id": "sleep", "name": "Sleep Sounds"},
    ]
    db_state["playlists"] = {
        "focus": _playlist("focus", "Deep Focus Instrumentals", ["one.mp3"])
    }

    result = music_handler.handle(
        "play focus", {"kind": "playlist", "query": "focus"}
    )

    _assert_documented_shape(result)
    assert result["text"] == "Playing Deep Focus Instrumentals (1 tracks). [MUSIC_PLAY:focus]"
    assert result["playlist_id"] == "focus"
    assert db_calls == {"list_playlists": 1, "get_playlist": ["focus"]}
    assert library_calls == []


def test_fuzzy_existing_playlist_match_uses_rapidfuzz_when_available(
    monkeypatch, mocked_playlist_db, mocked_library_resolver
):
    db_state, db_calls = mocked_playlist_db
    _library_state, library_calls = mocked_library_resolver
    db_state["candidates"] = [{"id": "lofi", "name": "Lo Fi Study Beats"}]
    db_state["playlists"] = {
        "lofi": _playlist("lofi", "Lo Fi Study Beats", ["beat.mp3"])
    }

    rapidfuzz_mod = types.ModuleType("rapidfuzz")
    rapidfuzz_mod.fuzz = types.SimpleNamespace(
        token_set_ratio=lambda query, name: 88
        if query == "lofi study" and name == "lo fi study beats"
        else 0
    )
    monkeypatch.setitem(sys.modules, "rapidfuzz", rapidfuzz_mod)

    result = music_handler.handle(
        "play lofi study", {"kind": "mood", "query": "lofi study"}
    )

    _assert_documented_shape(result)
    assert result["playlist_id"] == "lofi"
    assert "[MUSIC_PLAY:lofi]" in result["text"]
    assert db_calls == {"list_playlists": 1, "get_playlist": ["lofi"]}
    assert library_calls == []


def test_library_resolver_runs_when_no_existing_playlist_matches(
    mocked_playlist_db, mocked_library_resolver
):
    db_state, db_calls = mocked_playlist_db
    library_state, library_calls = mocked_library_resolver
    db_state["candidates"] = [{"id": "sleep", "name": "Sleep Sounds"}]
    library_state["playlist"] = _playlist("tmp-jazz", "Playing: jazz", ["jazz.mp3"])

    result = music_handler.handle("play jazz", {"kind": "genre", "query": "jazz"})

    _assert_documented_shape(result)
    assert result["text"] == "Playing Playing: jazz (1 tracks). [MUSIC_PLAY:tmp-jazz]"
    assert result["playlist_id"] == "tmp-jazz"
    assert db_calls == {"list_playlists": 1, "get_playlist": []}
    assert library_calls == ["jazz"]


def test_empty_query_for_shuffle_skips_vault_and_uses_library(
    mocked_playlist_db, mocked_library_resolver
):
    _db_state, db_calls = mocked_playlist_db
    library_state, library_calls = mocked_library_resolver
    library_state["playlist"] = _playlist("random", "Random Mix", ["a.mp3"])

    result = music_handler.handle("put on some music", {"kind": "shuffle", "query": ""})

    _assert_documented_shape(result)
    assert result["text"] == "Playing Random Mix (1 tracks). [MUSIC_PLAY:random]"
    assert db_calls == {"list_playlists": 0, "get_playlist": []}
    assert library_calls == [""]


def test_none_query_is_treated_as_empty_for_actionable_kind(
    mocked_playlist_db, mocked_library_resolver
):
    _db_state, db_calls = mocked_playlist_db
    library_state, library_calls = mocked_library_resolver
    library_state["playlist"] = _playlist("random", "Random Mix", [])

    result = music_handler.handle(None, {"kind": "song", "query": None})

    _assert_documented_shape(result)
    assert result["text"] == "Playing Random Mix (0 tracks). [MUSIC_PLAY:random]"
    assert db_calls == {"list_playlists": 0, "get_playlist": []}
    assert library_calls == [""]


def test_library_miss_returns_documented_failure_shape(
    mocked_playlist_db, mocked_library_resolver
):
    _db_state, _db_calls = mocked_playlist_db
    _library_state, library_calls = mocked_library_resolver

    result = music_handler.handle(
        "play not in the library", {"kind": "song", "query": "not in the library"}
    )

    assert result == {
        "text": "Unable to find the song in our list.",
        "playlist_id": None,
        "playlist_name": None,
    }
    assert library_calls == ["not in the library"]


def test_very_long_query_is_passed_to_library_without_crashing(
    mocked_playlist_db, mocked_library_resolver
):
    _db_state, _db_calls = mocked_playlist_db
    library_state, library_calls = mocked_library_resolver
    long_query = "ambient " * 10000
    library_state["playlist"] = _playlist("long", "Long Query Mix", ["track.mp3"])

    result = music_handler.handle(
        "play " + long_query, {"kind": "mood", "query": long_query}
    )

    _assert_documented_shape(result)
    assert result["playlist_id"] == "long"
    assert library_calls == [long_query.strip()]


def test_format_play_response_uses_defaults_and_omits_marker_without_id():
    result = music_handler._format_play_response({"tracks": None})

    assert result == {
        "text": "Playing that playlist (0 tracks).",
        "playlist_id": None,
        "playlist_name": "that playlist",
    }
    assert "[MUSIC_PLAY:" not in result["text"]


def test_normalize_collapses_case_edges_and_internal_whitespace():
    assert music_handler._normalize("  Lo   Fi\tStudy\nBeats  ") == "lo fi study beats"
    assert music_handler._normalize("") == ""
    assert music_handler._normalize(None) == ""


def test_vault_import_failure_falls_through_to_library(monkeypatch, mocked_library_resolver):
    library_state, library_calls = mocked_library_resolver
    library_state["playlist"] = _playlist("fallback", "Fallback Mix", ["one.mp3"])

    real_import = __import__

    def failing_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "vault_web.playlists":
            raise ImportError("blocked vault import")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", failing_import)

    result = music_handler.handle(
        "play anything", {"kind": "playlist", "query": "anything"}
    )

    _assert_documented_shape(result)
    assert result["playlist_id"] == "fallback"
    assert library_calls == ["anything"]


def test_v1_library_import_failure_escalates_after_vault_miss(mocked_playlist_db, monkeypatch):
    db_state, db_calls = mocked_playlist_db
    db_state["candidates"] = []

    real_import = __import__

    def failing_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "jane_web.main":
            raise ImportError("blocked library import")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", failing_import)

    result = music_handler.handle("play jazz", {"kind": "genre", "query": "jazz"})

    assert result == {
        "text": "Unable to find the song in our list.",
        "playlist_id": None,
        "playlist_name": None,
    }
    assert db_calls == {"list_playlists": 1, "get_playlist": []}


def test_actionable_kind_lookup_matches_metadata_enum_without_contradictions():
    schema_kinds = _schema_kind_values()
    actionable = music_handler._ACTIONABLE_KINDS

    assert schema_kinds == actionable | {"resume"}
    assert "resume" not in actionable
    assert actionable
    assert all(kind == kind.strip().lower() for kind in actionable)
    assert all(re.fullmatch(r"[a-z_]+", kind) for kind in actionable)
    assert actionable.isdisjoint(
        {"delete", "send", "send_message", "sms_send_direct", "end_conversation"}
    )


def test_kind_literals_referenced_by_handler_are_declared_in_metadata_or_escalate():
    source = MODULE_PATH.read_text()
    tree = ast.parse(source)
    compared_literals = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        left_is_kind = isinstance(node.left, ast.Name) and node.left.id == "kind"
        for comparator in node.comparators:
            if left_is_kind and isinstance(comparator, ast.Constant):
                if isinstance(comparator.value, str):
                    compared_literals.add(comparator.value)

    schema_kinds = _schema_kind_values()
    assert compared_literals <= schema_kinds
    assert compared_literals - music_handler._ACTIONABLE_KINDS == {"resume"}


@pytest.mark.parametrize("kind", sorted(music_handler._ACTIONABLE_KINDS))
def test_every_actionable_kind_is_reachable_and_returns_documented_shape(
    monkeypatch, kind
):
    calls = []

    def no_existing_playlist(query):
        calls.append(("db", query))
        return None

    def library_playlist(query):
        calls.append(("library", query))
        return _playlist(f"{kind}-id", f"{kind.title()} Mix", ["track.mp3"])

    monkeypatch.setattr(music_handler, "_match_existing_playlist", no_existing_playlist)
    monkeypatch.setattr(music_handler, "_ephemeral_from_library", library_playlist)

    result = music_handler.handle(
        f"play {kind}", {"kind": kind.upper(), "query": f" {kind} query "}
    )

    _assert_documented_shape(result)
    assert result["playlist_id"] == f"{kind}-id"
    assert result["playlist_name"] == f"{kind.title()} Mix"
    assert result["text"].endswith(f"[MUSIC_PLAY:{kind}-id]")
    assert calls == [("db", f"{kind} query"), ("library", f"{kind} query")]


def test_resume_schema_value_is_explicitly_documented_as_escalation(monkeypatch):
    assert "resume" in _schema_kind_values()
    assert "resume" in music_handler.__doc__
    assert "resume" in music_metadata.PARAMS_SCHEMA["kind"]

    def should_not_run(_query):
        raise AssertionError("resume is documented as escalate-only")

    monkeypatch.setattr(music_handler, "_match_existing_playlist", should_not_run)
    monkeypatch.setattr(music_handler, "_ephemeral_from_library", should_not_run)

    assert music_handler.handle("resume", {"kind": "resume", "query": ""}) is None


def test_music_play_class_registry_has_handler_that_returns_documented_shape(monkeypatch):
    from jane_web.jane_v2 import classes as class_registry

    monkeypatch.setattr(music_handler, "_match_existing_playlist", lambda _query: None)
    monkeypatch.setattr(
        music_handler,
        "_ephemeral_from_library",
        lambda query: _playlist("registry-id", f"Registry {query}", ["track.mp3"]),
    )

    registry = class_registry.get_registry(refresh=True)
    assert "music play" in registry
    assert registry["music play"]["handler"] is music_handler.handle

    result = registry["music play"]["handler"](
        "play registry jazz", params={"kind": "genre", "query": "jazz"}
    )
    _assert_documented_shape(result)
    assert result["text"] == "Playing Registry jazz (1 tracks). [MUSIC_PLAY:registry-id]"


def test_module_has_no_destructive_operations_or_confidence_free_side_effects():
    destructive_names = {
        "delete",
        "delete_playlist",
        "end_conversation",
        "send_message",
        "sms_send_direct",
        "sms_send",
        "remove",
        "unlink",
        "rmtree",
    }
    source = MODULE_PATH.read_text()
    tree = ast.parse(source)
    calls = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)

    assert calls.isdisjoint(destructive_names)


def test_module_has_no_direct_llm_integration_points():
    llm_import_roots = {
        "anthropic",
        "google.generativeai",
        "openai",
        "llm_brain",
        "jane_web.jane_v2.models",
    }
    llm_call_names = {
        "complete",
        "completion",
        "chat",
        "generate",
        "generate_content",
        "invoke_llm",
        "_phrase",
    }
    source = MODULE_PATH.read_text()
    tree = ast.parse(source)
    imported = set()
    calls = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)

    assert imported.isdisjoint(llm_import_roots)
    assert calls.isdisjoint(llm_call_names)
