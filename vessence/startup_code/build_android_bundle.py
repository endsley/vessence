#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED


REPO_ROOT = Path("/home/chieh/ambient/vessence")
ANDROID_ROOT = REPO_ROOT / "android"
APK_SOURCE = ANDROID_ROOT / "app/build/outputs/apk/debug/app-debug.apk"
DOWNLOADS_DIR = REPO_ROOT / "marketing_site" / "downloads"
APK_TARGET = DOWNLOADS_DIR / "vessences-android.apk"
VERSIONED_APK_TARGET = DOWNLOADS_DIR / "vessences-android-v0.1.1.apk"
PACKAGE_DIR = DOWNLOADS_DIR / "vessences-android-package"
PACKAGE_ZIP = DOWNLOADS_DIR / "vessences-android-package.zip"
README_TEXT = """Vessences Android

Contents:
- vessences-android-v0.1.1.apk

What it does:
- wraps the live Vessences web experience in a native Android shell
- provides bottom navigation for Project, Vault, Chat, and Settings
- combines Jane and Amber into one chat tab with an agent toggle
- supports the existing file upload and camera attach flows through Android's chooser

Install:
1. Move vessences-android-v0.1.1.apk to your Android phone.
2. Open it and allow install from this source if Android asks.
3. Launch Vessences and sign into Vault/Jane through the normal web login flow.
"""


def main() -> None:
    if not APK_SOURCE.exists():
        raise SystemExit(f"APK not found: {APK_SOURCE}")

    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)

    shutil.copy2(APK_SOURCE, APK_TARGET)
    shutil.copy2(APK_SOURCE, VERSIONED_APK_TARGET)
    shutil.copy2(APK_SOURCE, PACKAGE_DIR / "vessences-android-v0.1.1.apk")
    (PACKAGE_DIR / "README.txt").write_text(README_TEXT, encoding="utf-8")

    with ZipFile(PACKAGE_ZIP, "w", compression=ZIP_DEFLATED) as zf:
        zf.write(PACKAGE_DIR / "vessences-android-v0.1.1.apk", arcname="vessences-android-v0.1.1.apk")
        zf.write(PACKAGE_DIR / "README.txt", arcname="README.txt")

    print(APK_TARGET)
    print(VERSIONED_APK_TARGET)
    print(PACKAGE_ZIP)


if __name__ == "__main__":
    main()
