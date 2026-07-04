from jane_web.jane_v2 import stage3_protocols as protocols


def test_reason_to_class_normalizes_reason_and_rejects_unsafe_values():
    assert protocols.strip_escalation_reason_suffix("weather_fallback") == "weather"
    assert protocols.strip_escalation_reason_suffix("weather_declined") == "weather"
    assert protocols.strip_escalation_reason_suffix("weather_decline") == "weather"
    assert protocols.strip_escalation_reason_suffix("weather") == "weather"

    assert protocols.reason_to_class("send message:High") == "send_message"
    assert protocols.reason_to_class("weather_fallback:Low") == "weather"
    assert protocols.reason_to_class("weather_declined") == "weather"
    assert protocols.reason_to_class("others") is None
    assert protocols.reason_to_class("../../etc:High") is None


def test_load_protocol_extension_reads_and_caches_existing_file(tmp_path, monkeypatch):
    classes_dir = tmp_path / "classes"
    protocol_dir = classes_dir / "todo_list"
    protocol_dir.mkdir(parents=True)
    protocol_path = protocol_dir / "protocol.md"
    protocol_path.write_text(" first read ", encoding="utf-8")
    monkeypatch.setattr(protocols, "CLASSES_DIR", classes_dir.resolve())
    monkeypatch.setattr(protocols, "PROTOCOL_CACHE", {})

    assert protocols.load_protocol_extension("todo_list") == "first read"
    protocol_path.write_text(" second read ", encoding="utf-8")
    monkeypatch.setattr(
        protocols,
        "PROTOCOL_CACHE",
        {"todo_list": (protocol_path.stat().st_mtime_ns, "cached")},
    )

    assert protocols.load_protocol_extension("todo_list") == "cached"


def test_load_protocol_extension_rejects_bad_class_names(tmp_path, monkeypatch):
    monkeypatch.setattr(protocols, "CLASSES_DIR", tmp_path.resolve())
    monkeypatch.setattr(protocols, "PROTOCOL_CACHE", {})

    assert protocols.load_protocol_extension("../bad") is None
    assert protocols.load_protocol_extension("missing") is None


def test_load_class_protocol_combines_generated_and_extension(monkeypatch):
    monkeypatch.setattr(protocols, "synthesize_class_protocol", lambda _class_name: "generated")
    monkeypatch.setattr(protocols, "load_protocol_extension", lambda _class_name: "extension")

    assert protocols.load_class_protocol("todo_list") == "generated\n\nextension"


def test_synthesize_class_protocol_uses_registry_metadata():
    protocol = protocols.synthesize_class_protocol("todo_list")

    assert protocol is not None
    assert "AUTHORITATIVE class contract" in protocol
    assert "- Package: todo_list" in protocol
