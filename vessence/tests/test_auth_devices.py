from jane_web.auth_devices import trusted_device_id_for_fingerprint


def test_trusted_device_id_registers_when_trust_check_fails():
    calls = []

    device_id = trusted_device_id_for_fingerprint(
        "fp",
        "user",
        register_trusted_device=lambda fp, user: calls.append(("register", fp, user)) or "new",
        get_trusted_device_by_fingerprint=lambda _fp: {"id": "old"},
        is_device_trusted=lambda _fp: False,
    )

    assert device_id == "new"
    assert calls == [("register", "fp", "user")]


def test_trusted_device_id_reuses_existing_row_when_trusted():
    calls = []

    device_id = trusted_device_id_for_fingerprint(
        "fp",
        "user",
        register_trusted_device=lambda fp, user: calls.append(("register", fp, user)) or "new",
        get_trusted_device_by_fingerprint=lambda _fp: {"id": "old"},
        is_device_trusted=lambda _fp: True,
    )

    assert device_id == "old"
    assert calls == []


def test_trusted_device_id_without_trust_check_matches_otp_route_behavior():
    calls = []

    device_id = trusted_device_id_for_fingerprint(
        "fp",
        "user",
        register_trusted_device=lambda fp, user: calls.append(("register", fp, user)) or "new",
        get_trusted_device_by_fingerprint=lambda _fp: None,
    )

    assert device_id == "new"
    assert calls == [("register", "fp", "user")]
