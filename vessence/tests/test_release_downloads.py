import json
import os

from jane_web.release_downloads import ReleaseDownloads


def _write_version(root, version_name="1.2.3", version_code=123):
    (root / "version.json").write_text(
        json.dumps({"version_name": version_name, "version_code": version_code})
    )


def _touch(path, *, mtime=100, size=8):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    os.utime(path, (mtime, mtime))
    return path


def test_unversioned_android_apk_resolves_current_version_from_version_json(tmp_path):
    _write_version(tmp_path, version_name="1.2.3", version_code=123)
    downloads = tmp_path / "marketing_site" / "downloads"
    current = _touch(downloads / "vessences-android-v1.2.3.apk")
    _touch(downloads / "vessences-android.apk")

    release = ReleaseDownloads(tmp_path)

    assert release.resolve_android_apk_path("vessences-android.apk") == current
    assert release.resolve_android_apk_path("vessences-android-v1.2.3.apk") == current
    assert release.resolve_android_apk_path("not-android.apk") is None


def test_unversioned_android_apk_falls_back_to_alias_when_version_read_fails(tmp_path):
    downloads = tmp_path / "marketing_site" / "downloads"
    alias = _touch(downloads / "vessences-android.apk")
    (tmp_path / "version.json").write_text("{not json")

    release = ReleaseDownloads(tmp_path)

    assert release.resolve_android_apk_path("vessences-android.apk") == alias


def test_resolve_download_uses_newest_installer_alias_and_generic_apk_fallback(tmp_path):
    downloads = tmp_path / "marketing_site" / "downloads"
    older = _touch(downloads / "vessence-windows-installer-v1.zip", mtime=100)
    newer = _touch(downloads / "vessence-windows-installer-v2.zip", mtime=200)
    generic = _touch(downloads / "custom-release.apk")

    release = ReleaseDownloads(tmp_path)

    assert release.resolve_download("vessence-windows-installer.zip") == newer
    assert release.resolve_download("custom-release.apk") == generic
    assert release.resolve_download("missing.zip") is None
    assert older.exists()


def test_latest_version_payload_falls_back_to_newest_existing_apk(tmp_path):
    _write_version(tmp_path, version_name="2.0.0", version_code=200)
    downloads = tmp_path / "marketing_site" / "downloads"
    _touch(downloads / "vessences-android-v1.5.0.apk", mtime=100)
    _touch(downloads / "vessences-android-v1.6.0.apk", mtime=200)

    payload = ReleaseDownloads(tmp_path).latest_version_payload()

    assert payload == {
        "version_code": 200,
        "version_name": "1.6.0",
        "download_url": "/downloads/vessences-android-v1.6.0.apk",
        "changelog": "",
    }


def test_latest_version_payload_reports_no_download_when_no_apk_exists(tmp_path):
    _write_version(tmp_path, version_name="2.0.0", version_code=200)

    payload = ReleaseDownloads(tmp_path).latest_version_payload()

    assert payload == {
        "version_code": 200,
        "version_name": "2.0.0",
        "download_url": None,
        "changelog": "",
    }


def test_media_type_matches_download_route_contract(tmp_path):
    release = ReleaseDownloads(tmp_path)

    assert release.media_type(tmp_path / "app.apk") == "application/vnd.android.package-archive"
    assert release.media_type(tmp_path / "bundle.zip") == "application/zip"
    assert release.media_type(tmp_path / "docker-compose.yml") == "application/octet-stream"
    assert release.media_type(tmp_path / "readme.txt") == "application/octet-stream"
