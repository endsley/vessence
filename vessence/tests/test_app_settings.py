import json

from jane_web.app_settings import JsonSettingsStore


def test_load_missing_or_invalid_settings_returns_empty_dict(tmp_path):
    store = JsonSettingsStore(tmp_path / "missing" / "app_settings.json")
    assert store.load() == {}

    path = tmp_path / "bad.json"
    path.write_text("{not json")
    assert JsonSettingsStore(path).load() == {}


def test_save_creates_parent_directory_and_loads_json_object(tmp_path):
    path = tmp_path / "data" / "app_settings.json"
    store = JsonSettingsStore(path)
    settings = {"voice": "on", "volume": 0.8}

    store.save(settings)

    assert store.load() == settings
    assert json.loads(path.read_text()) == settings
