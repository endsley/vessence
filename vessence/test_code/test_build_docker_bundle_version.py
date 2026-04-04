from pathlib import Path

from startup_code import build_docker_bundle


def test_next_installer_version_increments_highest_existing(tmp_path, monkeypatch):
    monkeypatch.delenv("VESSENCE_INSTALLER_VERSION", raising=False)
    for name in (
        "vessence-windows-installer-v0.0.21.zip",
        "vessence-mac-installer-v0.0.21.zip",
        "vessence-linux-installer-v0.0.21.zip",
        "vessence-windows-installer-v0.0.22.zip",
    ):
        (tmp_path / name).write_text("x", encoding="utf-8")

    version = build_docker_bundle._next_installer_version(tmp_path)

    assert version == "0.0.23"


def test_next_installer_version_honors_override(tmp_path, monkeypatch):
    monkeypatch.setenv("VESSENCE_INSTALLER_VERSION", "9.9.9")

    version = build_docker_bundle._next_installer_version(tmp_path)

    assert version == "9.9.9"
