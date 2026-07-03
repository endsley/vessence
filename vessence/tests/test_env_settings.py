from jane_web.env_settings import EnvFileSettings


def test_write_var_replaces_active_key_preserves_comments_and_updates_environ(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("# TOKEN=old\nTOKEN=old\nOTHER=value\n", encoding="utf-8")
    environ = {}
    settings = EnvFileSettings(env_path, environ=environ)

    settings.write_var("TOKEN", "new")

    assert env_path.read_text(encoding="utf-8").splitlines() == [
        "# TOKEN=old",
        "TOKEN=new",
        "OTHER=value",
    ]
    assert environ["TOKEN"] == "new"


def test_write_var_appends_missing_key_and_creates_parent(tmp_path):
    env_path = tmp_path / "nested" / ".env"
    environ = {}
    settings = EnvFileSettings(env_path, environ=environ)

    settings.write_var("TOKEN", "new")

    assert env_path.read_text(encoding="utf-8") == "TOKEN=new\n"
    assert environ["TOKEN"] == "new"


def test_add_allowed_google_email_normalizes_and_ignores_duplicates(tmp_path):
    env_path = tmp_path / ".env"
    environ = {"ALLOWED_GOOGLE_EMAILS": "first@example.com"}
    settings = EnvFileSettings(env_path, environ=environ)

    assert settings.add_allowed_google_email(" Second@Example.COM ") is True
    assert environ["ALLOWED_GOOGLE_EMAILS"] == "first@example.com,second@example.com"
    assert env_path.read_text(encoding="utf-8") == "ALLOWED_GOOGLE_EMAILS=first@example.com,second@example.com\n"
    assert settings.add_allowed_google_email("second@example.com") is False


def test_remove_allowed_google_email_normalizes_and_updates_env_file(tmp_path):
    env_path = tmp_path / ".env"
    environ = {"ALLOWED_GOOGLE_EMAILS": "first@example.com,second@example.com"}
    settings = EnvFileSettings(env_path, environ=environ)

    assert settings.remove_allowed_google_email(" FIRST@Example.com ") is True
    assert environ["ALLOWED_GOOGLE_EMAILS"] == "second@example.com"
    assert env_path.read_text(encoding="utf-8") == "ALLOWED_GOOGLE_EMAILS=second@example.com\n"
    assert settings.remove_allowed_google_email("missing@example.com") is False
