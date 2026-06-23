import ast
import contextlib
import importlib
import inspect
import sqlite3
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent_skills.sms_helpers as sms_helpers


@pytest.fixture
def isolated_sms_db(tmp_path, monkeypatch):
    """Provide a fresh DB module matching sms_helpers' vault_web contract."""
    db_path = tmp_path / "sms_helpers.sqlite3"

    def open_conn():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT NOT NULL,
                phone_number TEXT,
                email TEXT,
                is_primary BOOLEAN DEFAULT 0,
                contact_id TEXT,
                synced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(display_name, phone_number, email)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS contact_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alias TEXT NOT NULL,
                phone_number TEXT NOT NULL,
                display_name TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(alias)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sms_drafts (
                draft_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                phone_number TEXT NOT NULL,
                display_name TEXT,
                body TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
        return conn

    @contextlib.contextmanager
    def get_db():
        conn = open_conn()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    database_module = types.ModuleType("database")
    database_module.get_db = get_db
    monkeypatch.setitem(sys.modules, "database", database_module)

    with get_db() as conn:
        yield conn, db_path


def insert_contact(
    conn,
    display_name,
    phone_number,
    *,
    email=None,
    is_primary=0,
    contact_id=None,
):
    conn.execute(
        """
        INSERT INTO contacts
            (display_name, phone_number, email, is_primary, contact_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (display_name, phone_number, email, is_primary, contact_id),
    )
    conn.commit()


def insert_alias(conn, alias, phone_number, display_name=None):
    conn.execute(
        """
        INSERT INTO contact_aliases (alias, phone_number, display_name)
        VALUES (?, ?, ?)
        """,
        (alias, phone_number, display_name),
    )
    conn.commit()


def insert_draft(
    conn,
    draft_id,
    session_id,
    phone_number,
    body,
    *,
    display_name=None,
    created_at=None,
):
    conn.execute(
        """
        INSERT INTO sms_drafts
            (draft_id, session_id, phone_number, display_name, body, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            draft_id,
            session_id,
            phone_number,
            display_name,
            body,
            created_at or "2026-05-22 12:00:00",
        ),
    )
    conn.commit()


def _sms_helper_references_elsewhere() -> set[str]:
    """Return sms_helpers symbols imported or referenced by other repo files."""
    references: set[str] = set()
    first_party_roots = [
        ROOT / "agent_skills",
        ROOT / "intent_classifier",
        ROOT / "jane_web",
        ROOT / "startup_code",
        ROOT / "test_code",
        ROOT / "vault_web",
    ]
    for first_party_root in first_party_roots:
        if not first_party_root.exists():
            continue
        for path in first_party_root.rglob("*.py"):
            if path == Path(sms_helpers.__file__).resolve() or path == Path(__file__).resolve():
                continue
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text())
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue

            aliases: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module == "agent_skills.sms_helpers":
                    for alias in node.names:
                        if alias.name != "*":
                            references.add(alias.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "agent_skills.sms_helpers":
                            aliases.add(alias.asname or "sms_helpers")

            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                    if node.value.id in aliases:
                        references.add(node.attr)
    return references


def _has_numeric_confidence_threshold(tree: ast.Module) -> bool:
    """Detect a strict confidence gate such as confidence >= 0.80."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(op, ast.GtE) for op in node.ops):
            continue

        names = {
            child.id
            for child in ast.walk(node)
            if isinstance(child, ast.Name) and "confidence" in child.id.lower()
        }
        names.update(
            child.attr
            for child in ast.walk(node)
            if isinstance(child, ast.Attribute) and "confidence" in child.attr.lower()
        )
        if not names:
            continue

        numeric_constants = [
            child.value
            for child in ast.walk(node)
            if isinstance(child, ast.Constant) and isinstance(child.value, (int, float))
        ]
        if any(value >= 0.80 for value in numeric_constants):
            return True
    return False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("wife", "wife"),
        (" my wife ", "wife"),
        ("the wife", "wife"),
        ("to Kathia", "kathia"),
        ("for   Mom", "mom"),
        ("My   Wife", "wife"),
        ("", ""),
        ("   ", ""),
        (None, ""),
    ],
)
def test_normalize_name_strips_documented_prefixes_and_whitespace(raw, expected):
    assert sms_helpers._normalize_name(raw) == expected


def test_normalize_name_handles_very_long_input_without_truncation():
    raw = "my " + ("Very   Long   Name " * 1000)
    normalized = sms_helpers._normalize_name(raw)

    assert normalized.startswith("very long name")
    assert "  " not in normalized
    assert normalized.count("very long name") == 1000


@pytest.mark.parametrize("prefix", sms_helpers._STOP_PREFIXES)
def test_stop_prefix_table_values_are_reachable_from_recipient_input(prefix):
    raw = f"{prefix}Target   Contact"

    assert sms_helpers._normalize_name(raw) == "target contact"


def test_resolve_recipient_prefers_alias_over_contacts(isolated_sms_db):
    conn, _ = isolated_sms_db
    insert_alias(conn, "wife", "+15550000001", "Kathia")
    insert_contact(conn, "Wife Work", "+15550000002", is_primary=1)

    result = sms_helpers.resolve_recipient("my wife")

    assert result == {
        "phone_number": "+15550000001",
        "display_name": "Kathia",
        "source": "alias",
    }


def test_resolve_recipient_alias_falls_back_to_normalized_alias_when_display_missing(
    isolated_sms_db,
):
    conn, _ = isolated_sms_db
    insert_alias(conn, "wife", "+15550000001", None)

    result = sms_helpers.resolve_recipient("the wife")

    assert result == {
        "phone_number": "+15550000001",
        "display_name": "wife",
        "source": "alias",
    }


def test_resolve_recipient_ignores_alias_rows_without_phone_and_uses_contacts(
    isolated_sms_db,
):
    conn, _ = isolated_sms_db
    conn.execute(
        "INSERT INTO contact_aliases (alias, phone_number, display_name) VALUES (?, ?, ?)",
        ("lee", "", "Broken Alias"),
    )
    insert_contact(conn, "Lee Primary", "+15550000003", is_primary=1)

    result = sms_helpers.resolve_recipient("Lee Primary")

    assert result == {
        "phone_number": "+15550000003",
        "display_name": "Lee Primary",
        "source": "contacts",
    }


def test_resolve_recipient_returns_single_unambiguous_contact(isolated_sms_db):
    conn, _ = isolated_sms_db
    insert_contact(conn, "Romeo Santos", "+15550000004", is_primary=1)

    result = sms_helpers.resolve_recipient("romeo")

    assert result == {
        "phone_number": "+15550000004",
        "display_name": "Romeo Santos",
        "source": "contacts",
    }


def test_resolve_recipient_collapses_duplicate_contact_rows_by_display_name(
    isolated_sms_db,
):
    conn, _ = isolated_sms_db
    insert_contact(conn, "Alex Chen", "+15550000005", is_primary=1, contact_id="alex")
    insert_contact(conn, "Alex Chen", "+15550000006", is_primary=0, contact_id="alex")

    result = sms_helpers.resolve_recipient("alex")

    assert result == {
        "phone_number": "+15550000005",
        "display_name": "Alex Chen",
        "source": "contacts",
    }


def test_resolve_recipient_rejects_ambiguous_contact_matches(isolated_sms_db):
    conn, _ = isolated_sms_db
    insert_contact(conn, "John Adams", "+15550000007", is_primary=1)
    insert_contact(conn, "John Baker", "+15550000008", is_primary=1)

    assert sms_helpers.resolve_recipient("john") is None


def test_resolve_recipient_ignores_email_only_contacts(isolated_sms_db):
    conn, _ = isolated_sms_db
    insert_contact(conn, "Email Only", None, email="email-only@example.com")
    insert_contact(conn, "Blank Phone", "", email="blank@example.com")

    assert sms_helpers.resolve_recipient("email") is None
    assert sms_helpers.resolve_recipient("blank") is None


def test_resolve_recipient_malformed_sql_like_input_is_parameterized(
    isolated_sms_db,
):
    conn, _ = isolated_sms_db
    insert_contact(conn, "Robert Tables", "+15550000030", is_primary=1)
    malformed = "Robert'); DROP TABLE contacts;--"

    assert sms_helpers.resolve_recipient(malformed) is None
    assert conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] == 1


def test_resolve_recipient_wildcard_only_input_cannot_force_unambiguous_send(
    isolated_sms_db,
):
    conn, _ = isolated_sms_db
    insert_contact(conn, "Alice Example", "+15550000031", is_primary=1)
    insert_contact(conn, "Bob Example", "+15550000032", is_primary=1)

    assert sms_helpers.resolve_recipient("%") is None
    assert sms_helpers.resolve_recipient("_") is None


@pytest.mark.parametrize("wildcard_name", ["%", "_", "%%", "__", "%_%"])
def test_resolve_recipient_sql_wildcards_are_not_literal_contact_names(
    isolated_sms_db,
    wildcard_name,
):
    conn, _ = isolated_sms_db
    insert_contact(conn, "Single Contact", "+15550000035", is_primary=1)

    assert sms_helpers.resolve_recipient(wildcard_name) is None


@pytest.mark.parametrize("bad_name", ["", "   ", None])
def test_resolve_recipient_empty_input_returns_none_without_db_query(
    bad_name,
    monkeypatch,
):
    def fail_get_db():
        raise AssertionError("empty input should not import or query database")

    database_module = types.ModuleType("database")
    database_module.get_db = fail_get_db
    monkeypatch.setitem(sys.modules, "database", database_module)

    assert sms_helpers.resolve_recipient(bad_name) is None


def test_resolve_recipient_returns_none_when_database_import_fails(monkeypatch):
    monkeypatch.setitem(sys.modules, "database", types.ModuleType("database"))

    assert sms_helpers.resolve_recipient("wife") is None


def test_resolve_recipient_returns_none_when_database_query_fails(monkeypatch):
    @contextlib.contextmanager
    def broken_get_db():
        raise sqlite3.OperationalError("boom")
        yield

    database_module = types.ModuleType("database")
    database_module.get_db = broken_get_db
    monkeypatch.setitem(sys.modules, "database", database_module)

    assert sms_helpers.resolve_recipient("wife") is None


def test_add_alias_normalizes_and_replaces_existing_alias(isolated_sms_db):
    conn, _ = isolated_sms_db
    assert sms_helpers.add_alias(" my Wife ", " +15550000009 ", " Kathia ") is True
    assert sms_helpers.add_alias("wife", "+15550000010", "") is True

    rows = conn.execute(
        "SELECT alias, phone_number, display_name FROM contact_aliases"
    ).fetchall()

    assert len(rows) == 1
    assert dict(rows[0]) == {
        "alias": "wife",
        "phone_number": "+15550000010",
        "display_name": None,
    }


@pytest.mark.parametrize(
    ("alias", "phone_number"),
    [
        ("", "+15550000011"),
        ("   ", "+15550000011"),
        (None, "+15550000011"),
        ("wife", ""),
        ("wife", None),
    ],
)
def test_add_alias_rejects_empty_or_malformed_required_fields(
    isolated_sms_db,
    alias,
    phone_number,
):
    conn, _ = isolated_sms_db

    assert sms_helpers.add_alias(alias, phone_number) is False
    assert conn.execute("SELECT COUNT(*) FROM contact_aliases").fetchone()[0] == 0


def test_add_alias_accepts_very_long_alias_and_phone(isolated_sms_db):
    conn, _ = isolated_sms_db
    alias = "my " + ("Long Name " * 200)
    phone = "+" + ("1" * 500)

    assert sms_helpers.add_alias(alias, phone, "Long Contact") is True

    row = conn.execute(
        "SELECT alias, phone_number, display_name FROM contact_aliases"
    ).fetchone()
    assert row["alias"] == ("long name " * 200).strip()
    assert row["phone_number"] == phone
    assert row["display_name"] == "Long Contact"


def test_add_alias_malformed_sql_string_is_stored_as_data(isolated_sms_db):
    conn, _ = isolated_sms_db
    alias = "wife'); DROP TABLE sms_drafts;--"

    assert sms_helpers.add_alias(alias, "+15550000033", "SQL Alias") is True
    row = conn.execute(
        "SELECT alias, phone_number, display_name FROM contact_aliases"
    ).fetchone()
    assert dict(row) == {
        "alias": alias.lower(),
        "phone_number": "+15550000033",
        "display_name": "SQL Alias",
    }
    conn.execute("SELECT COUNT(*) FROM sms_drafts").fetchone()


def test_add_alias_returns_false_when_database_import_fails(monkeypatch):
    monkeypatch.setitem(sys.modules, "database", types.ModuleType("database"))

    assert sms_helpers.add_alias("wife", "+15550000012") is False


def test_create_draft_persists_pending_sms_draft(isolated_sms_db):
    conn, _ = isolated_sms_db

    draft_id = sms_helpers.create_draft(
        "session-1",
        "+15550000013",
        "I am on my way",
        display_name="Mom",
    )

    assert isinstance(draft_id, str)
    assert len(draft_id) == 12
    int(draft_id, 16)
    row = conn.execute(
        """
        SELECT draft_id, session_id, phone_number, display_name, body
        FROM sms_drafts
        """
    ).fetchone()
    assert dict(row) == {
        "draft_id": draft_id,
        "session_id": "session-1",
        "phone_number": "+15550000013",
        "display_name": "Mom",
        "body": "I am on my way",
    }


@pytest.mark.parametrize(
    ("session_id", "phone_number", "body"),
    [
        ("", "+15550000014", "body"),
        (None, "+15550000014", "body"),
        ("session-1", "", "body"),
        ("session-1", None, "body"),
        ("session-1", "+15550000014", ""),
        ("session-1", "+15550000014", None),
    ],
)
def test_create_draft_rejects_empty_required_fields(
    isolated_sms_db,
    session_id,
    phone_number,
    body,
):
    conn, _ = isolated_sms_db

    assert sms_helpers.create_draft(session_id, phone_number, body) is None
    assert conn.execute("SELECT COUNT(*) FROM sms_drafts").fetchone()[0] == 0


def test_create_draft_accepts_very_long_body(isolated_sms_db):
    conn, _ = isolated_sms_db
    body = "x" * 100_000

    draft_id = sms_helpers.create_draft("session-long", "+15550000015", body)

    assert draft_id is not None
    stored = conn.execute("SELECT body FROM sms_drafts WHERE draft_id = ?", (draft_id,))
    assert stored.fetchone()["body"] == body


def test_create_draft_malformed_body_and_phone_are_parameterized_data(
    isolated_sms_db,
):
    conn, _ = isolated_sms_db
    body = "hello'); DELETE FROM sms_drafts;--"
    phone = "+15550000034'); DROP TABLE contacts;--"

    draft_id = sms_helpers.create_draft("session-sql", phone, body, "Mal Formed")

    assert draft_id is not None
    row = conn.execute(
        "SELECT phone_number, body FROM sms_drafts WHERE draft_id = ?",
        (draft_id,),
    ).fetchone()
    assert row["phone_number"] == phone
    assert row["body"] == body
    conn.execute("SELECT COUNT(*) FROM contacts").fetchone()


def test_create_draft_returns_none_when_database_write_fails(monkeypatch):
    @contextlib.contextmanager
    def broken_get_db():
        raise sqlite3.OperationalError("insert failed")
        yield

    database_module = types.ModuleType("database")
    database_module.get_db = broken_get_db
    monkeypatch.setitem(sys.modules, "database", database_module)

    assert sms_helpers.create_draft("session-1", "+15550000016", "body") is None


def test_get_latest_draft_returns_most_recent_non_expired_draft(
    isolated_sms_db,
    monkeypatch,
):
    conn, _ = isolated_sms_db
    now = datetime(2026, 5, 22, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(sms_helpers.time, "time", lambda: now.timestamp())
    insert_draft(
        conn,
        "old",
        "session-1",
        "+15550000017",
        "old body",
        display_name="Old",
        created_at="2026-05-22 11:58:00",
    )
    insert_draft(
        conn,
        "new",
        "session-1",
        "+15550000018",
        "new body",
        display_name="New",
        created_at="2026-05-22 11:59:00",
    )
    insert_draft(
        conn,
        "other-session",
        "session-2",
        "+15550000019",
        "other body",
        display_name="Other",
        created_at="2026-05-22 12:00:00",
    )

    assert sms_helpers.get_latest_draft("session-1") == {
        "draft_id": "new",
        "phone_number": "+15550000018",
        "display_name": "New",
        "body": "new body",
    }


def test_get_latest_draft_deletes_expired_latest_draft_and_returns_none(
    isolated_sms_db,
    monkeypatch,
):
    conn, _ = isolated_sms_db
    now = datetime(2026, 5, 22, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(sms_helpers.time, "time", lambda: now.timestamp())
    insert_draft(
        conn,
        "expired",
        "session-1",
        "+15550000020",
        "stale body",
        created_at="2026-05-22 11:54:59",
    )

    assert sms_helpers.get_latest_draft("session-1") is None
    assert (
        conn.execute("SELECT COUNT(*) FROM sms_drafts WHERE draft_id = 'expired'")
        .fetchone()[0]
        == 0
    )


@pytest.mark.parametrize("session_id", ["", None])
def test_get_latest_draft_rejects_empty_session_without_db_query(
    session_id,
    monkeypatch,
):
    def fail_get_db():
        raise AssertionError("empty session should not query database")

    database_module = types.ModuleType("database")
    database_module.get_db = fail_get_db
    monkeypatch.setitem(sys.modules, "database", database_module)

    assert sms_helpers.get_latest_draft(session_id) is None


def test_get_latest_draft_returns_none_when_database_read_fails(monkeypatch):
    @contextlib.contextmanager
    def broken_get_db():
        raise sqlite3.OperationalError("select failed")
        yield

    database_module = types.ModuleType("database")
    database_module.get_db = broken_get_db
    monkeypatch.setitem(sys.modules, "database", database_module)

    assert sms_helpers.get_latest_draft("session-1") is None


def test_delete_draft_deletes_only_exact_draft_id(isolated_sms_db):
    conn, _ = isolated_sms_db
    insert_draft(conn, "target", "session-1", "+15550000021", "delete me")
    insert_draft(conn, "target-extra", "session-1", "+15550000022", "keep me")

    assert sms_helpers.delete_draft("target") is True

    remaining = conn.execute("SELECT draft_id FROM sms_drafts ORDER BY draft_id")
    assert [row["draft_id"] for row in remaining.fetchall()] == ["target-extra"]


@pytest.mark.parametrize("draft_id", ["", None])
def test_delete_draft_rejects_empty_draft_id_without_db_query(draft_id, monkeypatch):
    def fail_get_db():
        raise AssertionError("empty draft_id should not query database")

    database_module = types.ModuleType("database")
    database_module.get_db = fail_get_db
    monkeypatch.setitem(sys.modules, "database", database_module)

    assert sms_helpers.delete_draft(draft_id) is False


def test_delete_draft_returns_true_for_missing_non_empty_draft_id(isolated_sms_db):
    conn, _ = isolated_sms_db

    assert sms_helpers.delete_draft("missing") is True
    assert conn.execute("SELECT COUNT(*) FROM sms_drafts").fetchone()[0] == 0


def test_delete_draft_returns_false_when_database_delete_fails(monkeypatch):
    @contextlib.contextmanager
    def broken_get_db():
        raise sqlite3.OperationalError("delete failed")
        yield

    database_module = types.ModuleType("database")
    database_module.get_db = broken_get_db
    monkeypatch.setitem(sys.modules, "database", database_module)

    assert sms_helpers.delete_draft("draft-1") is False


def test_cleanup_expired_drafts_deletes_only_rows_older_than_ttl(
    isolated_sms_db,
    monkeypatch,
):
    conn, _ = isolated_sms_db
    now = datetime(2026, 5, 22, 12, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(sms_helpers.time, "time", lambda: now.timestamp())
    expired_time = now - timedelta(seconds=sms_helpers.DRAFT_TTL_SECONDS + 1)
    boundary_time = now - timedelta(seconds=sms_helpers.DRAFT_TTL_SECONDS)
    fresh_time = now - timedelta(seconds=10)
    insert_draft(
        conn,
        "expired",
        "session-1",
        "+15550000023",
        "old",
        created_at=expired_time.strftime("%Y-%m-%d %H:%M:%S"),
    )
    insert_draft(
        conn,
        "boundary",
        "session-1",
        "+15550000024",
        "boundary",
        created_at=boundary_time.strftime("%Y-%m-%d %H:%M:%S"),
    )
    insert_draft(
        conn,
        "fresh",
        "session-1",
        "+15550000025",
        "fresh",
        created_at=fresh_time.strftime("%Y-%m-%d %H:%M:%S"),
    )

    assert sms_helpers.cleanup_expired_drafts() == 1
    remaining = conn.execute("SELECT draft_id FROM sms_drafts ORDER BY draft_id")
    assert [row["draft_id"] for row in remaining.fetchall()] == [
        "boundary",
        "fresh",
    ]


def test_cleanup_expired_drafts_returns_zero_when_database_delete_fails(monkeypatch):
    @contextlib.contextmanager
    def broken_get_db():
        raise sqlite3.OperationalError("cleanup failed")
        yield

    database_module = types.ModuleType("database")
    database_module.get_db = broken_get_db
    monkeypatch.setitem(sys.modules, "database", database_module)

    assert sms_helpers.cleanup_expired_drafts() == 0


def test_database_integration_uses_documented_query_order_and_tables():
    source = inspect.getsource(sms_helpers.resolve_recipient)

    alias_pos = source.index("FROM contact_aliases")
    contacts_pos = source.index("FROM contacts")
    assert alias_pos < contacts_pos
    assert "WHERE LOWER(alias) = ?" in source
    assert "display_name LIKE ?" in source
    assert "phone_number IS NOT NULL" in source
    assert "phone_number != ''" in source
    assert "LIMIT 5" in source


def test_draft_storage_integration_uses_session_scoped_latest_lookup_and_exact_delete():
    latest_source = inspect.getsource(sms_helpers.get_latest_draft)
    delete_source = inspect.getsource(sms_helpers.delete_draft)
    cleanup_source = inspect.getsource(sms_helpers.cleanup_expired_drafts)

    assert "FROM sms_drafts WHERE session_id = ?" in latest_source
    assert "ORDER BY created_at DESC LIMIT 1" in latest_source
    assert "DELETE FROM sms_drafts WHERE draft_id = ?" in latest_source
    assert "DELETE FROM sms_drafts WHERE draft_id = ?" in delete_source
    assert "DELETE FROM sms_drafts WHERE strftime('%s', created_at) < ?" in cleanup_source


def test_module_has_no_llm_or_network_integration_points():
    source = inspect.getsource(sms_helpers)
    forbidden_tokens = [
        "httpx",
        "AsyncClient",
        "openai",
        "anthropic",
        "ollama",
        "generate_content",
        "chat.completions",
        "send_message_stream",
    ]

    assert all(token not in source for token in forbidden_tokens)


def test_structural_invariant_no_module_level_mapping_or_lookup_registry():
    tree = ast.parse(inspect.getsource(sms_helpers))
    module_dict_assignments = []
    registry_like_names = []

    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if isinstance(value, ast.Dict):
                module_dict_assignments.extend(
                    target.id for target in targets if isinstance(target, ast.Name)
                )
            for target in targets:
                if isinstance(target, ast.Name) and any(
                    marker in target.id.lower()
                    for marker in ("map", "lookup", "registry", "handlers")
                ):
                    registry_like_names.append(target.id)

    assert module_dict_assignments == []
    assert registry_like_names == []


def test_structural_invariant_no_classifier_confidence_table_to_contradict():
    tree = ast.parse(inspect.getsource(sms_helpers))
    constants = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]

    assert "High" not in constants
    assert "Low" not in constants
    assert "others" not in constants


def test_structural_invariant_referenced_public_symbols_exist():
    references = _sms_helper_references_elsewhere()
    missing = sorted(name for name in references if not hasattr(sms_helpers, name))

    assert missing == []


def test_structural_invariant_destructive_helpers_are_draft_scoped_not_sms_senders():
    tree = ast.parse(inspect.getsource(sms_helpers))
    source = inspect.getsource(sms_helpers)
    function_names = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }

    assert "send_message" not in function_names
    assert "sms_send_direct" not in source
    assert "contacts.sms_send_direct" not in source
    assert "end_conversation" not in function_names
    assert "delete_draft" in function_names
    assert "cleanup_expired_drafts" in function_names


def test_structural_invariant_direct_sms_sender_requires_numeric_confidence_gate():
    source = inspect.getsource(sms_helpers)
    tree = ast.parse(source)
    direct_sender_present = any(
        token in source
        for token in (
            "contacts.sms_send_direct",
            "sms_send_direct(",
            "[[CLIENT_TOOL:contacts.sms_send",
        )
    )

    assert (not direct_sender_present) or _has_numeric_confidence_threshold(tree)


def test_structural_invariant_draft_deletion_rejects_borderline_empty_inputs(
    monkeypatch,
):
    calls = []

    def fail_get_db():
        calls.append("queried")
        raise AssertionError("borderline empty draft identifiers must not query")

    database_module = types.ModuleType("database")
    database_module.get_db = fail_get_db
    monkeypatch.setitem(sys.modules, "database", database_module)

    assert sms_helpers.delete_draft("") is False
    assert sms_helpers.delete_draft(None) is False
    assert calls == []


def test_structural_invariant_no_handler_dispatch_registry():
    tree = ast.parse(inspect.getsource(sms_helpers))
    suspicious_names = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and any(
            marker in node.id.lower()
            for marker in ("handler", "dispatch", "registry", "class_registry")
        ):
            suspicious_names.add(node.id)

    assert suspicious_names == set()


def test_public_functions_return_documented_shapes(isolated_sms_db):
    conn, _ = isolated_sms_db
    insert_alias(conn, "wife", "+15550000026", "Kathia")

    resolved = sms_helpers.resolve_recipient("wife")
    assert set(resolved) == {"phone_number", "display_name", "source"}
    assert isinstance(resolved["phone_number"], str)
    assert isinstance(resolved["display_name"], str)
    assert resolved["source"] in {"alias", "contacts"}

    draft_id = sms_helpers.create_draft("session-shape", "+15550000026", "hello")
    draft = sms_helpers.get_latest_draft("session-shape")
    assert set(draft) == {"draft_id", "phone_number", "display_name", "body"}
    assert draft["draft_id"] == draft_id
    assert isinstance(sms_helpers.delete_draft(draft_id), bool)
    assert isinstance(sms_helpers.cleanup_expired_drafts(), int)


def test_module_can_be_reloaded_without_losing_vault_web_path_contract():
    reloaded = importlib.reload(sms_helpers)

    assert str(reloaded._VAULT_WEB_DIR).endswith("/vault_web")
    assert str(reloaded._VAULT_WEB_DIR) in sys.path
