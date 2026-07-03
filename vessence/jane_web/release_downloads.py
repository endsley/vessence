"""Release download and Android version helpers for Jane web routes."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional


class ReleaseDownloads:
    """Resolve public release artifacts without baking APK paths at import time."""

    def __init__(self, code_root: Path) -> None:
        self.code_root = code_root
        self.marketing_dir = self.code_root / "marketing_site"
        self.downloads_dir = self.marketing_dir / "downloads"
        self.public_release_downloads = {
            # Raw compose file for advanced users
            "docker-compose.yml": self.marketing_dir / "docker-compose.yml",
            # Docker image tarball
            "vessence-docker-0.0.43.tar.gz": self.downloads_dir / "vessence-docker-0.0.43.tar.gz",
            # Universal Installer (bundled source + scripts)
            "vessence-installer-0.0.42.zip": self.downloads_dir / "vessence-installer-0.0.42.zip",
            # Android APK entries are resolved dynamically by resolve_android_apk_path().
            "vessences-android-package.zip": self.downloads_dir / "vessences-android-package.zip",
            # Legacy (keep for existing links)
            "vessence-installer-0.0.41.zip": self.downloads_dir / "vessence-installer-0.0.41.zip",
        }
        self.installer_globs = {
            "vessence-windows-installer.zip": "vessence-windows-installer-v*.zip",
            "vessence-windows-installer.exe": "vessence-windows-installer-v*.exe",
            "vessence-mac-installer.zip": "vessence-mac-installer-v*.zip",
            "vessence-linux-installer.zip": "vessence-linux-installer-v*.zip",
        }

    @property
    def version_path(self) -> Path:
        return self.code_root / "version.json"

    def read_android_version(self) -> tuple[str, int]:
        try:
            version_data = json.loads(self.version_path.read_text())
            return version_data["version_name"], version_data["version_code"]
        except FileNotFoundError:
            return "0.2.99", 330

    def log_startup_apk_status(self, logger: logging.Logger) -> None:
        android_version, _version_code = self.read_android_version()
        expected_apk = self.downloads_dir / f"vessences-android-v{android_version}.apk"
        if not expected_apk.exists():
            logger.critical(
                "APK MISSING: version.json says v%s but %s does not exist! "
                "Run startup_code/bump_android_version.py to build it.",
                android_version,
                expected_apk,
            )
        elif expected_apk.stat().st_size < 1_000_000:  # < 1MB = likely corrupt
            logger.critical(
                "APK CORRUPT: %s is only %d bytes - likely not a valid APK. "
                "Rebuild with bump_android_version.py.",
                expected_apk,
                expected_apk.stat().st_size,
            )

    def find_latest(self, pattern: str) -> Optional[Path]:
        """Return the newest file matching a glob pattern in downloads_dir, or None."""
        matches = sorted(self.downloads_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        return matches[0] if matches else None

    def resolve_android_apk_path(self, filename: str) -> Path | None:
        """Resolve versioned and unversioned Android APK download filenames."""
        if filename == "vessences-android.apk":
            try:
                version_data = json.loads(self.version_path.read_text())
                current_version = version_data.get("version_name")
                if current_version:
                    versioned = self.downloads_dir / f"vessences-android-v{current_version}.apk"
                    if versioned.exists():
                        return versioned
            except Exception:
                pass
            alias = self.downloads_dir / "vessences-android.apk"
            return alias if alias.exists() else None

        if filename.startswith("vessences-android-v") and filename.endswith(".apk"):
            path = self.downloads_dir / filename
            return path if path.exists() else None
        return None

    def resolve_download(self, filename: str) -> Path | None:
        target = self.public_release_downloads.get(filename)
        if not target or not target.exists() or not target.is_file():
            glob_pattern = self.installer_globs.get(filename)
            if glob_pattern:
                target = self.find_latest(glob_pattern)

        if not target or not target.exists() or not target.is_file():
            apk_target = self.resolve_android_apk_path(filename)
            if apk_target is not None:
                target = apk_target

        if (not target or not target.exists() or not target.is_file()) and filename.endswith(".apk"):
            candidate = self.downloads_dir / filename
            if candidate.exists() and candidate.is_file():
                target = candidate

        return target if target and target.exists() and target.is_file() else None

    @staticmethod
    def media_type(path: Path) -> str:
        return {
            ".apk": "application/vnd.android.package-archive",
            ".zip": "application/zip",
            ".yml": "application/octet-stream",
        }.get(path.suffix.lower(), "application/octet-stream")

    def latest_version_payload(self) -> dict:
        version_data = json.loads(self.version_path.read_text())
        version_name = version_data["version_name"]
        version_code = version_data["version_code"]
        apk_path = self.downloads_dir / f"vessences-android-v{version_name}.apk"
        if not apk_path.exists():
            existing = sorted(
                self.downloads_dir.glob("vessences-android-v*.apk"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if existing:
                version_name = existing[0].stem[len("vessences-android-v") :]
            else:
                return {
                    "version_code": version_code,
                    "version_name": version_name,
                    "download_url": None,
                    "changelog": "",
                }
        return {
            "version_code": version_code,
            "version_name": version_name,
            "download_url": f"/downloads/vessences-android-v{version_name}.apk",
            "changelog": "",
        }
