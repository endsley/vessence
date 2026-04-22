from fastapi.testclient import TestClient

from jane_web.main import app


def test_device_diagnostics_post_accepts_prelogin_reports():
    payload = {
        "category": "auth",
        "message": "auth[test]",
        "app_version": "test",
        "version_code": 0,
    }

    with TestClient(app) as client:
        response = client.post("/api/device-diagnostics", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "received"}


def test_device_diagnostics_get_still_requires_auth():
    with TestClient(app) as client:
        response = client.get("/api/device-diagnostics")

    assert response.status_code == 401
