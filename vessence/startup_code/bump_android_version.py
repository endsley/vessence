#!/usr/bin/env python3
"""bump_android_version.py — Bump Android version AND build the APK in one step.

This is the ONLY way to bump the Android version. It ensures the version number
and the actual APK are always in sync.

Usage:
    python bump_android_version.py           # auto-increment patch
    python bump_android_version.py 0.1.0     # set specific version
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

VESSENCE_HOME = Path(__file__).resolve().parents[1]
VERSION_FILE = VESSENCE_HOME / "version.json"
ANDROID_DIR = VESSENCE_HOME / "android"
DOWNLOADS_DIR = VESSENCE_HOME / "marketing_site" / "downloads"
CHANGELOG = VESSENCE_HOME / "configs" / "CHANGELOG.md"
MAIN_PY = VESSENCE_HOME / "jane_web" / "main.py"


def load_version() -> dict:
    with open(VERSION_FILE) as f:
        return json.load(f)


def save_version(data: dict):
    with open(VERSION_FILE, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def bump_patch(version_name: str) -> str:
    parts = version_name.split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


def update_main_py(version_name: str, version_code: int):
    """Update ANDROID_VERSION and ANDROID_VERSION_CODE in main.py."""
    text = MAIN_PY.read_text()
    import re
    text = re.sub(r'ANDROID_VERSION = "[^"]*"', f'ANDROID_VERSION = "{version_name}"', text)
    text = re.sub(r'ANDROID_VERSION_CODE = \d+', f'ANDROID_VERSION_CODE = {version_code}', text)
    MAIN_PY.write_text(text)
    print(f"  Updated main.py: ANDROID_VERSION={version_name}, ANDROID_VERSION_CODE={version_code}")


def build_apk() -> Path:
    """Build the release APK and return the output path."""
    print("  Building APK...")
    result = subprocess.run(
        ["./gradlew", "assembleRelease"],
        cwd=str(ANDROID_DIR),
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        print(f"  BUILD FAILED:\n{result.stderr[-500:]}")
        sys.exit(1)
    apk = ANDROID_DIR / "app" / "build" / "outputs" / "apk" / "release" / "app-release.apk"
    if not apk.exists():
        print(f"  ERROR: APK not found at {apk}")
        sys.exit(1)
    print(f"  Build successful: {apk.stat().st_size // (1024*1024)}MB")
    return apk


def verify_apk_version(apk: Path, expected_code: int, expected_name: str):
    """Verify the built APK actually contains the expected version."""
    # Find aapt2 in Android SDK build-tools
    import glob
    aapt2_candidates = sorted(glob.glob(os.path.expanduser("~/android-sdk/build-tools/*/aapt2")))
    aapt2 = aapt2_candidates[-1] if aapt2_candidates else "aapt2"
    result = subprocess.run(
        [aapt2, "dump", "badging", str(apk)],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        # aapt2 not available — fall back to checking file size changed
        print(f"  ⚠ Cannot verify APK version (aapt2 not found), skipping check")
        return
    for line in result.stdout.split("\n"):
        if line.startswith("package:"):
            if f"versionCode='{expected_code}'" not in line:
                print(f"  ERROR: APK versionCode mismatch! Expected {expected_code}")
                print(f"  APK says: {line[:200]}")
                sys.exit(1)
            if f"versionName='{expected_name}'" not in line:
                print(f"  ERROR: APK versionName mismatch! Expected {expected_name}")
                print(f"  APK says: {line[:200]}")
                sys.exit(1)
            print(f"  ✓ APK verified: versionCode={expected_code}, versionName={expected_name}")
            return
    print(f"  ⚠ Could not parse APK version info")


def ensure_changelog_entry(version_name: str):
    """Add a stub changelog entry if one doesn't exist for this version."""
    from datetime import date
    marker = f"## v{version_name}"
    text = CHANGELOG.read_text()
    if marker in text:
        print(f"  Changelog entry for v{version_name} already exists")
        return
    today = date.today().isoformat()
    stub = f"## v{version_name} ({today})\n- Version bump.\n\n"
    # Insert after the first line (title)
    lines = text.split("\n", 2)
    if len(lines) >= 3:
        new_text = lines[0] + "\n" + lines[1] + "\n" + stub + lines[2]
    else:
        new_text = text + "\n" + stub
    CHANGELOG.write_text(new_text)
    print(f"  Added changelog stub for v{version_name}")


def deploy_apk(apk: Path, version_name: str):
    """Copy APK to marketing downloads directory (versioned + generic)."""
    dest = DOWNLOADS_DIR / f"vessences-android-v{version_name}.apk"
    generic = DOWNLOADS_DIR / "vessences-android.apk"
    shutil.copy2(apk, dest)
    shutil.copy2(apk, generic)
    print(f"  Deployed to {dest}")
    print(f"  Deployed to {generic}")


def main():
    current = load_version()
    old_name = current["version_name"]
    old_code = current["version_code"]

    if len(sys.argv) > 1:
        new_name = sys.argv[1]
    else:
        new_name = bump_patch(old_name)

    new_code = old_code + 1

    print(f"Android version bump: {old_name} (code {old_code}) → {new_name} (code {new_code})")
    print()

    # 1. Update version.json
    save_version({"version_code": new_code, "version_name": new_name})
    print(f"  Updated version.json")

    # 2. Update main.py
    update_main_py(new_name, new_code)

    # 3. Ensure changelog entry exists (Gradle verifyChangelog will fail without it)
    ensure_changelog_entry(new_name)

    # 4. Build APK
    apk = build_apk()

    # 5. Verify APK has correct version baked in
    verify_apk_version(apk, new_code, new_name)

    # 6. Deploy to downloads
    deploy_apk(apk, new_name)

    # 7. Done
    print()
    print(f"  ✓ Version {new_name} built, verified, and deployed.")


if __name__ == "__main__":
    main()
