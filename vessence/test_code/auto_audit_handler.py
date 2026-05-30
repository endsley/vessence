from __future__ import annotations

import ast
import builtins
import inspect
import re
import sys
import types
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MODULE_PATH = (
    REPO_ROOT / "jane_web" / "jane_v2" / "classes" / "music_play" / "handler.py"
)

from jane_web.jane_v2 import classes as class_registry
from jane_web.jane_v2 import stage1_classifier, stage2_dispatcher
from jane_web.jane_v2.classes.music_play import handler as music_handler
from jane_web.jane_v2.classes.music_play import metadata as music_metadata


DOCUMENTED_KINDS = {
    "artist",
    "genre",
    "mood",
    "playlist",
    "resume",
    "shuffle",
    "song",
}
ACTIONABLE_KINDS = DOCUMENTED_KINDS - {"resume"}

DESTRUCTIVE_NAMES = {
    "delete",
    "delete_email",
    "delete_message",
    "delete_messages",
    "delete_playlist",
    "end_conversation",
    "remove",
    "send_message",
    "sms_send_direct",
    "trash",
    "update_playlist",
}

LLM_OR_NETWORK_ROOTS = {
    "anthropic",
    "google.generativeai",
    "httpx",
    "openai",
    "requests",
}


@pytest.fixture
def module_source() -> str:
    return MODULE_PATH.read_text()


@pytest.fixture
def module_ast(module_source: str) -> ast.Module:
    return ast.parse(module_source)


def _schema_kind_values() -> set[str]:
    schema_text = music_metadata.PARAMS_SCHEMA["kind"].lower()
    enum_part = schema_text.split("one of:", 1)[1].split(".", 1)[0]
    return {part.strip() for part in enum_part.split("|") if part.strip()}


def _assert_stage2_shape(result: dict | None, *, playable: bool) -> None:
    assert isinstance(result, dict)
    assert isinstance(result.get("text"), str)
    assert result["text"]
    assert "playlist_id" in result
    assert "playlist_name" in result
    if playable:
        assert result["playlist_id"]
        assert result["playlist_name"]
        assert f"[MUSIC_PLAY:{result['playlist_id']}]" in result["text"]
    else:
        assert result["playlist_id"] is None
        assert result["playlist_name"] is None
        assert "[MUSIC_PLAY:" not in result["text"]


def _install_fake_playlists(
    monkeypatch: pytest.MonkeyPatch,
    playlists: list[dict],
    records: dict[str, dict] | None = None,
) -> dict[str, object]:
    calls: dict[str, object] = {"list": 0, "get": []}
    records = records or {
        item["id"]: {
            "id": item["id"],
            "name": item.get("name", ""),
            "tracks": item.get("tracks", []),
        }
        for item in playlists
    }

    vault_pkg = types.ModuleType("vault_web")
    playlist_mod = types.ModuleType("vault_web.playlists")

    def list_playlists() -> list[dict]:
        calls["list"] = int(calls["list"]) + 1
        return list(playlists)

    def get_playlist(playlist_id: str) -> dict:
        cast_get_calls = calls["get"]
        assert isinstance(cast_get_calls, list)
        cast_get_calls.append(playlist_id)
        return records[playlist_id]

    playlist_mod.list_playlists = list_playlists
    playlist_mod.get_playlist = get_playlist
    vault_pkg.playlists = playlist_mod

    monkeypatch.setitem(sys.modules, "vault_web", vault_pkg)
    monkeypatch.setitem(sys.modules, "vault_web.playlists", playlist_mod)
    return calls


def _install_fake_library(
    monkeypatch: pytest.MonkeyPatch, playlist: dict | None
) -> list[str]:
    calls: list[str] = []
    main_mod = types.ModuleType("jane_web.main")

    def create_music_playlist_from_query(query: str) -> dict | None:
        calls.append(query)
        return playlist

    main_mod.create_music_playlist_from_query = create_music_playlist_from_query
    monkeypatch.setitem(sys.modules, "jane_web.main", main_mod)
    return calls


def _block_import(monkeypatch: pytest.MonkeyPatch, blocked_name: str) -> None:
    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == blocked_name or name.startswith(f"{blocked_name}."):
            raise RuntimeError(f"blocked import: {blocked_name}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)


def _qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _qualified_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _call_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _qualified_name(node.func)
            if name:
                names.add(name)
    return names


def _import_roots(tree: ast.Module) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
            if node.module.startswith("google.generativeai"):
                roots.add("google.generativeai")
    return roots


def _call_safely(prompt: str, params) -> dict | None:
    try:
        return music_handler.handle(prompt, params=params)
    except (AttributeError, TypeError):
        return None


def test_normalize_collapses_whitespace_lowercases_and_accepts_none():
    assert music_handler._normalize("  The\tScientist\nLive   ") == "the scientist live"
    assert music_handler._normalize("") == ""
    assert music_handler._normalize(None) == ""


def test_format_play_response_adds_marker_and_documented_shape():
    result = music_handler._format_play_response(
        {"id": "playlist-123", "name": "Coldplay", "tracks": ["a.mp3", "b.mp3"]}
    )

    assert result == {
        "text": "Playing Coldplay (2 tracks). [MUSIC_PLAY:playlist-123]",
        "playlist_id": "playlist-123",
        "playlist_name": "Coldplay",
    }


def test_format_play_response_without_id_omits_marker_but_keeps_shape():
    result = music_handler._format_play_response({"name": "Loose Tracks", "tracks": None})

    assert result == {
        "text": "Playing Loose Tracks (0 tracks).",
        "playlist_id": None,
        "playlist_name": "Loose Tracks",
    }
    assert "[MUSIC_PLAY:" not in result["text"]


@pytest.mark.parametrize("params", [None, {}])
def test_empty_or_none_params_escalate_before_external_integrations(monkeypatch, params):
    monkeypatch.setattr(
        music_handler,
        "_match_existing_playlist",
        lambda query: pytest.fail("playlist lookup should not run"),
    )
    monkeypatch.setattr(
        music_handler,
        "_ephemeral_from_library",
        lambda query: pytest.fail("library resolver should not run"),
    )

    assert music_handler.handle("play something", params=params) is None


def test_resume_escalates_without_db_or_library(monkeypatch):
    monkeypatch.setattr(
        music_handler,
        "_match_existing_playlist",
        lambda query: pytest.fail("resume should not search playlists"),
    )
    monkeypatch.setattr(
        music_handler,
        "_ephemeral_from_library",
        lambda query: pytest.fail("resume should not call the scanner"),
    )

    assert (
        music_handler.handle(
            "continue playing",
            params={"kind": "  RESUME  ", "query": None},
        )
        is None
    )


@pytest.mark.parametrize(
    "params",
    [
        {"query": "Coldplay"},
        {"kind": "", "query": "Coldplay"},
        {"kind": "   ", "query": "Coldplay"},
    ],
)
def test_missing_kind_escalates_without_db_or_library(monkeypatch, params):
    monkeypatch.setattr(
        music_handler,
        "_match_existing_playlist",
        lambda query: pytest.fail("missing kind should not search playlists"),
    )
    monkeypatch.setattr(
        music_handler,
        "_ephemeral_from_library",
        lambda query: pytest.fail("missing kind should not call the scanner"),
    )

    assert music_handler.handle("play Coldplay", params=params) is None


def test_existing_playlist_exact_match_preempts_library(monkeypatch):
    calls = _install_fake_playlists(
        monkeypatch,
        [{"id": "pl1", "name": "Road Trip"}],
        {"pl1": {"id": "pl1", "name": "Road Trip", "tracks": ["a", "b", "c"]}},
    )
    monkeypatch.setattr(
        music_handler,
        "_ephemeral_from_library",
        lambda query: pytest.fail("exact playlist match should not fall through"),
    )

    result = music_handler.handle(
        "play road trip",
        params={"kind": "playlist", "query": " road   trip "},
    )

    assert calls == {"list": 1, "get": ["pl1"]}
    _assert_stage2_shape(result, playable=True)
    assert result["text"] == "Playing Road Trip (3 tracks). [MUSIC_PLAY:pl1]"


def test_existing_playlist_substring_match_preempts_library(monkeypatch):
    calls = _install_fake_playlists(
        monkeypatch,
        [
            {"id": "other", "name": "Workout"},
            {"id": "target", "name": "2026 Road Trip Mix"},
        ],
        {
            "other": {"id": "other", "name": "Workout", "tracks": ["x"]},
            "target": {"id": "target", "name": "2026 Road Trip Mix", "tracks": ["a"]},
        },
    )
    monkeypatch.setattr(
        music_handler,
        "_ephemeral_from_library",
        lambda query: pytest.fail("substring playlist match should not fall through"),
    )

    result = music_handler.handle(
        "play road trip",
        params={"kind": "playlist", "query": "road trip"},
    )

    assert calls == {"list": 1, "get": ["target"]}
    _assert_stage2_shape(result, playable=True)
    assert result["playlist_id"] == "target"


def test_existing_playlist_fuzzy_match_uses_highest_score(monkeypatch):
    calls = _install_fake_playlists(
        monkeypatch,
        [
            {"id": "low", "name": "Morning Mix"},
            {"id": "high", "name": "Evening Relaxation"},
            {"id": "skip", "name": "Classical Piano"},
        ],
        {
            "low": {"id": "low", "name": "Morning Mix", "tracks": ["a"]},
            "high": {"id": "high", "name": "Evening Relaxation", "tracks": ["b", "c"]},
            "skip": {"id": "skip", "name": "Classical Piano", "tracks": ["d"]},
        },
    )
    rapidfuzz_mod = types.ModuleType("rapidfuzz")
    scores = {
        "morning mix": 82,
        "evening relaxation": 94,
        "classical piano": 10,
    }
    rapidfuzz_mod.fuzz = types.SimpleNamespace(
        token_set_ratio=lambda query, name: scores[name]
    )
    monkeypatch.setitem(sys.modules, "rapidfuzz", rapidfuzz_mod)

    result = music_handler._match_existing_playlist("relax tracks")

    assert calls == {"list": 1, "get": ["high"]}
    assert result == {"id": "high", "name": "Evening Relaxation", "tracks": ["b", "c"]}


def test_empty_playlist_query_does_not_hit_database(monkeypatch):
    calls = _install_fake_playlists(monkeypatch, [{"id": "pl1", "name": "Anything"}])

    assert music_handler._match_existing_playlist("   ") is None
    assert calls == {"list": 0, "get": []}


def test_no_existing_playlist_candidates_do_not_fetch_details(monkeypatch):
    calls = _install_fake_playlists(monkeypatch, [])

    assert music_handler._match_existing_playlist("Coldplay") is None
    assert calls == {"list": 1, "get": []}


def test_existing_playlist_import_failure_fails_closed(monkeypatch):
    _block_import(monkeypatch, "vault_web.playlists")

    assert music_handler._match_existing_playlist("Coldplay") is None


def test_library_resolver_calls_v1_scanner_with_query(monkeypatch):
    playlist = {"id": "ephemeral-1", "name": "Playing: Shakira", "tracks": ["a"]}
    calls = _install_fake_library(monkeypatch, playlist)

    assert music_handler._ephemeral_from_library("Shakira") == playlist
    assert calls == ["Shakira"]


def test_library_resolver_import_failure_returns_none(monkeypatch):
    _block_import(monkeypatch, "jane_web.main")

    assert music_handler._ephemeral_from_library("anything") is None


def test_handle_falls_back_to_library_when_existing_playlist_misses(monkeypatch):
    calls = _install_fake_playlists(monkeypatch, [])
    library_calls = _install_fake_library(
        monkeypatch,
        {"id": "tmp1", "name": "Playing: Shakira", "tracks": ["song.mp3"]},
    )

    result = music_handler.handle(
        "play Shakira",
        params={"kind": "artist", "query": "Shakira"},
    )

    assert calls == {"list": 1, "get": []}
    assert library_calls == ["Shakira"]
    _assert_stage2_shape(result, playable=True)
    assert result["text"] == "Playing Playing: Shakira (1 tracks). [MUSIC_PLAY:tmp1]"


def test_no_library_match_returns_documented_failure_shape(monkeypatch):
    monkeypatch.setattr(music_handler, "_match_existing_playlist", lambda query: None)
    monkeypatch.setattr(music_handler, "_ephemeral_from_library", lambda query: None)

    result = music_handler.handle(
        "play a missing song",
        params={"kind": "song", "query": "missing song"},
    )

    assert result == {
        "text": "Unable to find the song in our list.",
        "playlist_id": None,
        "playlist_name": None,
    }
    _assert_stage2_shape(result, playable=False)


def test_very_long_query_is_stripped_and_passed_to_both_resolvers(monkeypatch):
    raw_query = "  " + ("lofi focus " * 2000) + "  "
    expected_query = raw_query.strip()
    seen: dict[str, str] = {}

    def fake_existing(query: str) -> None:
        seen["existing"] = query
        return None

    def fake_library(query: str) -> dict:
        seen["library"] = query
        return {"id": "long1", "name": "Long Query Mix", "tracks": ["a"]}

    monkeypatch.setattr(music_handler, "_match_existing_playlist", fake_existing)
    monkeypatch.setattr(music_handler, "_ephemeral_from_library", fake_library)

    result = music_handler.handle(
        "play a very long prompt",
        params={"kind": "mood", "query": raw_query},
    )

    assert seen == {"existing": expected_query, "library": expected_query}
    _assert_stage2_shape(result, playable=True)


@pytest.mark.parametrize(
    "bad_params",
    [
        [],
        object(),
        {"kind": object(), "query": "Coldplay"},
        {"kind": "song", "query": object()},
    ],
)
def test_malformed_params_cannot_trigger_playback(monkeypatch, bad_params):
    monkeypatch.setattr(
        music_handler,
        "_match_existing_playlist",
        lambda query: pytest.fail("malformed params should not search playlists"),
    )
    monkeypatch.setattr(
        music_handler,
        "_ephemeral_from_library",
        lambda query: pytest.fail("malformed params should not start playback"),
    )

    assert _call_safely("play something", bad_params) is None


def test_unknown_kind_fails_closed_before_playback(monkeypatch):
    monkeypatch.setattr(
        music_handler,
        "_match_existing_playlist",
        lambda query: pytest.fail("unknown kind should not search playlists"),
    )
    monkeypatch.setattr(
        music_handler,
        "_ephemeral_from_library",
        lambda query: pytest.fail("unknown kind should not start playback"),
    )

    assert (
        music_handler.handle(
            "play Coldplay",
            params={"kind": "not_in_schema", "query": "Coldplay"},
        )
        is None
    )


def test_param_schema_kind_enum_matches_documented_dispatch_contract():
    assert _schema_kind_values() == DOCUMENTED_KINDS


@pytest.mark.parametrize("kind", sorted(ACTIONABLE_KINDS))
def test_every_documented_action_kind_reaches_library_from_public_handle(
    monkeypatch, kind: str
):
    calls: list[str] = []
    monkeypatch.setattr(music_handler, "_match_existing_playlist", lambda query: None)

    def fake_library(query: str) -> dict:
        calls.append(query)
        return {
            "id": f"{kind}-playlist",
            "name": f"{kind.title()} Playlist",
            "tracks": ["a"],
        }

    monkeypatch.setattr(music_handler, "_ephemeral_from_library", fake_library)

    result = music_handler.handle(
        f"play {kind}",
        params={"kind": kind, "query": f"{kind} query"},
    )

    assert calls == [f"{kind} query"]
    _assert_stage2_shape(result, playable=True)
    assert result["playlist_id"] == f"{kind}-playlist"


def test_resume_is_the_only_schema_kind_that_escalates_by_design(monkeypatch):
    monkeypatch.setattr(
        music_handler,
        "_match_existing_playlist",
        lambda query: pytest.fail("resume should not search playlists"),
    )
    monkeypatch.setattr(
        music_handler,
        "_ephemeral_from_library",
        lambda query: pytest.fail("resume should not call scanner"),
    )

    assert music_handler.handle("resume", params={"kind": "resume", "query": None}) is None
    assert "resume" in _schema_kind_values()
    assert ACTIONABLE_KINDS == _schema_kind_values() - {"resume"}


def test_music_metadata_few_shots_do_not_map_high_confidence_to_fallback_class():
    for prompt, label in music_metadata.METADATA["few_shot"]:
        class_name, confidence = label.rsplit(":", 1)
        assert prompt.strip()
        assert class_name == music_metadata.METADATA["name"]
        assert confidence == "High"
        assert class_name not in {"others", "delegate opus", "unclear"}


def test_stage1_class_map_values_exist_in_class_registry_and_music_points_here():
    registry = class_registry.get_registry(refresh=True)

    assert stage1_classifier._CLASS_MAP["MUSIC_PLAY"] == "music play"
    assert set(stage1_classifier._CLASS_MAP.values()).issubset(registry.keys())
    assert registry["music play"]["pkg_name"] == "music_play"
    assert registry["music play"]["handler"] is music_handler.handle
    assert registry["music play"]["params_schema"] is music_metadata.PARAMS_SCHEMA


@pytest.mark.asyncio
async def test_stage2_dispatch_invokes_registered_music_handler_with_params(monkeypatch):
    monkeypatch.setattr(music_handler, "_match_existing_playlist", lambda query: None)
    monkeypatch.setattr(
        music_handler,
        "_ephemeral_from_library",
        lambda query: {
            "id": "dispatch1",
            "name": "Dispatch Mix",
            "tracks": ["a", "b"],
        },
    )

    result = await stage2_dispatcher.dispatch(
        "music play",
        "play dispatch mix",
        params={"kind": "song", "query": "dispatch mix"},
        min_dist=0.0,
    )

    _assert_stage2_shape(result, playable=True)
    assert result["playlist_id"] == "dispatch1"


@pytest.mark.asyncio
async def test_stage2_dispatch_escalates_registered_resume_request(monkeypatch):
    monkeypatch.setattr(
        music_handler,
        "_match_existing_playlist",
        lambda query: pytest.fail("resume should not search playlists"),
    )
    monkeypatch.setattr(
        music_handler,
        "_ephemeral_from_library",
        lambda query: pytest.fail("resume should not call scanner"),
    )

    result = await stage2_dispatcher.dispatch(
        "music play",
        "resume",
        params={"kind": "resume", "query": None},
        min_dist=0.0,
    )

    assert result is None


def test_registry_classes_have_handlers_or_documented_escalation_path():
    registry = class_registry.get_registry(refresh=True)
    classes_dir = REPO_ROOT / "jane_web" / "jane_v2" / "classes"

    for class_name, meta in registry.items():
        if meta.get("handler") is not None:
            continue

        metadata_path = classes_dir / meta["pkg_name"] / "metadata.py"
        metadata_source = metadata_path.read_text()
        description = meta.get("description")
        description_text = "" if callable(description) else str(description or "")
        combined = f"{metadata_source}\n{description_text}".lower()

        if class_name == "end conversation":
            pipeline_source = (
                REPO_ROOT / "jane_web" / "jane_v2" / "pipeline.py"
            ).read_text()
            assert "END_CONVERSATION short-circuit" in pipeline_source
            assert "conversation_end" in pipeline_source
            continue

        has_no_handler_note = "no handler" in combined
        has_escalation_note = "escalat" in combined or "short-circuit" in combined
        has_always_escalates_note = "always escalates to stage 3 by design" in combined

        assert has_escalation_note
        assert has_no_handler_note or has_always_escalates_note


def test_music_handler_has_no_destructive_operations(module_ast):
    calls = _call_names(module_ast)
    destructive_calls = {
        name
        for name in calls
        if name.rsplit(".", 1)[-1].lower() in DESTRUCTIVE_NAMES
    }

    assert destructive_calls == set()


def test_destructive_end_conversation_gate_has_phrase_guard_and_numeric_floor():
    source = inspect.getsource(stage1_classifier)

    assert stage1_classifier._end_conversation_phrase_ok("bye") is True
    assert stage1_classifier._end_conversation_phrase_ok("stop the music") is False
    assert stage1_classifier._end_conversation_phrase_ok(
        "I think the context window is not long enough"
    ) is False
    assert 'raw_cls == "END_CONVERSATION" and confidence < 0.80' in source


def test_music_handler_has_no_direct_llm_or_network_calls(module_ast):
    imported = _import_roots(module_ast)
    calls = _call_names(module_ast)
    forbidden_call_roots = {
        name.split(".", 1)[0]
        for name in calls
        if name.split(".", 1)[0] in {"httpx", "requests", "openai", "anthropic"}
    }

    assert imported.isdisjoint({root.split(".", 1)[0] for root in LLM_OR_NETWORK_ROOTS})
    assert forbidden_call_roots == set()


def test_every_literal_dict_return_in_music_handler_has_text_key(module_ast):
    for node in ast.walk(module_ast):
        if not isinstance(node, ast.Return):
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        keys = {
            key.value
            for key in node.value.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
        assert "text" in keys
