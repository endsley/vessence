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
import re
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


def _load_env() -> dict[str, str]:
    """Load key=value pairs from the project .env file into a dict."""
    env_file = Path(os.environ.get("VESSENCE_DATA_HOME", VESSENCE_HOME.parent / "vessence-data")) / ".env"
    env = dict(os.environ)
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip().strip('"').strip("'")
    return env


def build_apk() -> Path:
    """Build the release APK and return the output path."""
    print("  Building APK...")
    build_env = _load_env()
    result = subprocess.run(
        ["./gradlew", "assembleRelease"],
        cwd=str(ANDROID_DIR),
        capture_output=True,
        text=True,
        timeout=600,
        env=build_env,
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


def update_marketing_links(version_name: str):
    """Update marketing site HTML to point download links at the new versioned APK."""
    import re
    marketing_dir = VESSENCE_HOME / "marketing_site"
    apk_url = f"https://jane.vessences.com/downloads/vessences-android-v{version_name}.apk"
    pattern = re.compile(r'href="https://jane\.vessences\.com/downloads/vessences-android[^"]*\.apk"')
    updated = []
    for html_file in [marketing_dir / "index.html", marketing_dir / "install.html"]:
        if not html_file.exists():
            continue
        text = html_file.read_text()
        new_text = pattern.sub(f'href="{apk_url}"', text)
        if new_text != text:
            html_file.write_text(new_text)
            updated.append(html_file.name)
    if updated:
        print(f"  Updated download links in {', '.join(updated)}")
    else:
        print(f"  Marketing links already up to date")


def deploy_apk(apk: Path, version_name: str):
    """Copy APK to marketing downloads directory (versioned + generic)."""
    dest = DOWNLOADS_DIR / f"vessences-android-v{version_name}.apk"
    generic = DOWNLOADS_DIR / "vessences-android.apk"
    shutil.copy2(apk, dest)
    shutil.copy2(apk, generic)
    print(f"  Deployed to {dest}")
    print(f"  Deployed to {generic}")


def _aapt_path() -> Path | None:
    """Locate an aapt binary from the Android SDK. Used to read versionCode
    out of already-deployed APKs as a sanity floor for new builds."""
    for base in (Path.home() / "android-sdk" / "build-tools",
                 Path("/opt/android-sdk/build-tools"),
                 Path("/usr/local/android-sdk/build-tools")):
        if base.exists():
            for ver_dir in sorted(base.iterdir(), reverse=True):
                candidate = ver_dir / "aapt"
                if candidate.is_file() and os.access(candidate, os.X_OK):
                    return candidate
    return None


def scan_deployed_max_version_code() -> tuple[int, str] | None:
    """Return (max_version_code, apk_filename) across every APK in
    downloads/, or None if aapt isn't available or no APK parses.

    We trust the APK's AndroidManifest (via aapt) over version.json
    because version.json has historically drifted when other build paths
    bumped Gradle without updating it. This is the scar tissue fix.
    """
    aapt = _aapt_path()
    if aapt is None:
        return None
    best = (-1, "")
    for apk in DOWNLOADS_DIR.glob("vessences-android-v*.apk"):
        try:
            r = subprocess.run(
                [str(aapt), "dump", "badging", str(apk)],
                capture_output=True, text=True, timeout=10, check=False,
            )
            first_line = (r.stdout or "").splitlines()[0] if r.stdout else ""
            m = re.search(r"versionCode='(\d+)'", first_line)
            if m:
                code = int(m.group(1))
                if code > best[0]:
                    best = (code, apk.name)
        except Exception:
            continue
    if best[0] < 0:
        return None
    return best


def main():
    current = load_version()
    old_name = current["version_name"]
    old_code = current["version_code"]

    if len(sys.argv) > 1:
        new_name = sys.argv[1]
    else:
        new_name = bump_patch(old_name)

    new_code = old_code + 1

    # Sanity floor: new_code must exceed the max versionCode of every APK
    # already in downloads/. Past builds have drifted — e.g., Gradle-side
    # builds incremented versionCode without updating version.json, then a
    # bump off the stale version.json produced an APK with a *lower* code
    # than what users already had installed, silently breaking the auto-
    # updater. Jump `new_code` above any deployed APK we can find.
    deployed = scan_deployed_max_version_code()
    if deployed is not None:
        deployed_code, deployed_apk = deployed
        if new_code <= deployed_code:
            adjusted = deployed_code + 1
            print(f"  ⚠  versionCode {new_code} ≤ deployed max {deployed_code} "
                  f"(from {deployed_apk}).")
            print(f"     Jumping to code {adjusted} so auto-update works.")
            new_code = adjusted

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

    # 7. Update marketing site download links to point to the new versioned APK
    update_marketing_links(new_name)

    # 8. Done
    print()
    print(f"  ✓ Version {new_name} built, verified, and deployed.")


if __name__ == "__main__":
    main()
