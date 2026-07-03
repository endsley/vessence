import json

from context_builder.v1 import essence_context as essence


def test_active_essence_names_reads_current_and_legacy_formats(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    active_file = data_dir / "active_essence.json"

    active_file.write_text('{"active": ["tax", "work"]}', encoding="utf-8")
    assert essence.active_essence_names(str(tmp_path)) == ["tax", "work"]
    active_file.write_text('{"active_essence": "legacy"}', encoding="utf-8")
    assert essence.active_essence_names(str(tmp_path)) == ["legacy"]
    active_file.write_text("{bad", encoding="utf-8")
    assert essence.active_essence_names(str(tmp_path)) == []


def test_get_active_essence_personality_checks_tools_then_essences(tmp_path, monkeypatch):
    data_dir = tmp_path / "data_home" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "active_essence.json").write_text('{"active": ["tax", "doctor"]}', encoding="utf-8")
    ambient = tmp_path / "ambient"
    tools_personality = ambient / "skills" / "tax" / "personality.md"
    essence_personality = ambient / "essences" / "doctor" / "personality.md"
    tools_personality.parent.mkdir(parents=True)
    essence_personality.parent.mkdir(parents=True)
    tools_personality.write_text("Tax helper", encoding="utf-8")
    essence_personality.write_text("Doctor helper", encoding="utf-8")
    monkeypatch.setenv("VESSENCE_DATA_HOME", str(tmp_path / "data_home"))
    monkeypatch.setenv("AMBIENT_BASE", str(ambient))
    monkeypatch.delenv("TOOLS_DIR", raising=False)

    personality = essence.get_active_essence_personality()

    assert "### Active Essence: tax\nTax helper" in personality
    assert "### Active Essence: doctor\nDoctor helper" in personality


def test_get_active_essence_chromadb_path_uses_first_existing_path(tmp_path, monkeypatch):
    data_dir = tmp_path / "data_home" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "active_essence.json").write_text('{"active": ["missing", "tax"]}', encoding="utf-8")
    ambient = tmp_path / "ambient"
    chroma = ambient / "skills" / "tax" / "knowledge" / "chromadb"
    chroma.mkdir(parents=True)
    monkeypatch.setenv("VESSENCE_DATA_HOME", str(tmp_path / "data_home"))
    monkeypatch.setenv("AMBIENT_BASE", str(ambient))
    monkeypatch.delenv("TOOLS_DIR", raising=False)

    assert essence.get_active_essence_chromadb_path() == str(chroma)


def test_extract_tool_signatures_skips_private_and_preserves_public_signatures(tmp_path):
    tools = tmp_path / "custom_tools.py"
    tools.write_text(
        "def public(a, b) -> dict:\n"
        "def simple(x):\n"
        "def _private():\n",
        encoding="utf-8",
    )

    assert essence.extract_tool_signatures(str(tools)) == ["public(a, b)", "simple(x)"]


def test_get_essence_tools_description_lists_tools_and_agent_essences(tmp_path, monkeypatch):
    ambient = tmp_path / "ambient"
    tool_dir = ambient / "skills" / "timer" / "functions"
    agent_dir = ambient / "essences" / "doctor" / "functions"
    tool_dir.mkdir(parents=True)
    agent_dir.mkdir(parents=True)
    (tool_dir.parent / "manifest.json").write_text(
        json.dumps({"essence_name": "Timer", "type": "tool"}),
        encoding="utf-8",
    )
    (tool_dir / "custom_tools.py").write_text("def set_timer(minutes):\n", encoding="utf-8")
    (agent_dir.parent / "manifest.json").write_text(
        json.dumps({"essence_name": "Doctor", "type": "essence", "description": "Medical helper"}),
        encoding="utf-8",
    )
    (agent_dir / "custom_tools.py").write_text("def lookup(name):\n", encoding="utf-8")
    monkeypatch.setenv("AMBIENT_BASE", str(ambient))
    monkeypatch.delenv("TOOLS_DIR", raising=False)

    description = essence.get_essence_tools_description()

    assert "## Tools" in description
    assert "### Timer (Tool)" in description
    assert "`set_timer(minutes)`" in description
    assert "## Essences (AI Agents)" in description
    assert "### Doctor (Essence" in description
    assert "`lookup(name)`" in description
