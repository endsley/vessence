from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from startup_code import build_docker_bundle
from startup_code.installer_simulation import simulate_installer_package


@pytest.mark.parametrize("platform", ["linux", "mac", "windows"])
def test_platform_installer_package_simulation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str) -> None:
    downloads_dir = tmp_path / "downloads"
    downloads_dir.mkdir()
    monkeypatch.setattr(build_docker_bundle, "DOWNLOADS_DIR", downloads_dir)

    zip_path = build_docker_bundle.build_platform_package(platform)
    extract_dir = tmp_path / f"extract-{platform}"
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    simulate_installer_package(platform, extract_dir / "vessence")
