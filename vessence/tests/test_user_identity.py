from jane_web.user_identity import configured_admin_variants, default_user_id, identity_variants


def test_default_user_id_prefers_first_allowed_email_then_user_name_then_user():
    assert default_user_id({"ALLOWED_GOOGLE_EMAILS": " First@Example.com , second@example.com "}) == "First@Example.com"
    assert default_user_id({"USER_NAME": "Jane Doe"}) == "jane_doe"
    assert default_user_id({}) == "user"


def test_identity_variants_normalizes_email_and_includes_user_id_variant():
    variants = identity_variants(
        " User.Name@Example.COM ",
        user_id_from_email_fn=lambda email: f"uid:{email}",
    )

    assert variants == {
        "user.name@example.com",
        "user_name_at_example_com",
        "uid:user.name@example.com",
    }
    assert identity_variants(None) == set()


def test_configured_admin_variants_uses_explicit_admin_env_first():
    variants = configured_admin_variants(
        {
            "VESSENCE_ADMIN_USERS": "admin@example.com",
            "ADMIN_EMAILS": "other@example.com",
            "ALLOWED_GOOGLE_EMAILS": "allowed@example.com",
        },
        auth_default_user_id_fn=lambda: "default_admin",
        user_id_from_email_fn=lambda email: f"uid:{email}",
    )

    assert "admin@example.com" in variants
    assert "uid:admin@example.com" in variants
    assert "other@example.com" in variants
    assert "allowed@example.com" not in variants


def test_configured_admin_variants_falls_back_to_allowed_then_auth_default():
    allowed_variants = configured_admin_variants(
        {"ALLOWED_GOOGLE_EMAILS": "allowed@example.com, second@example.com"},
        auth_default_user_id_fn=lambda: "default_admin",
        user_id_from_email_fn=lambda email: f"uid:{email}",
    )
    assert "allowed@example.com" in allowed_variants
    assert "second@example.com" not in allowed_variants

    default_variants = configured_admin_variants(
        {},
        auth_default_user_id_fn=lambda: "default_admin",
        user_id_from_email_fn=lambda email: f"uid:{email}",
    )
    assert default_variants == {"default_admin"}
