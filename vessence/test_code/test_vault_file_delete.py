import json
from contextlib import contextmanager

from vault_web import files as files_mod


class _FakeConn:
    def __init__(self, statements):
        self.statements = statements

    def execute(self, sql):
        self.statements.append(sql)


def test_delete_vault_file_removes_file_hash_index_and_logs_change(tmp_path, monkeypatch):
    vault_root = tmp_path
    target_dir = vault_root / "documents"
    target_dir.mkdir()
    target = target_dir / "note.txt"
    target.write_text("delete me")
    (vault_root / ".hash_index.json").write_text(json.dumps({
        "deleted_hash": {"path": "documents/note.txt"},
        "kept_hash": {"path": "documents/keep.txt"},
    }))

    statements = []
    index_deletes = []

    @contextmanager
    def fake_db():
        yield _FakeConn(statements)

    monkeypatch.setattr(files_mod, "get_db", fake_db)
    monkeypatch.setattr(
        files_mod,
        "delete_file_index_entry",
        lambda rel_path, user_id=None: index_deletes.append((rel_path, user_id)) or True,
    )

    result = files_mod.delete_vault_file(
        "documents/note.txt",
        root_dir=vault_root,
        user_id="test-user",
    )

    assert result == {"ok": True, "deleted": True, "path": "documents/note.txt"}
    assert not target.exists()
    assert json.loads((vault_root / ".hash_index.json").read_text()) == {
        "kept_hash": {"path": "documents/keep.txt"},
    }
    assert index_deletes == [("documents/note.txt", "test-user")]
    assert statements == ["INSERT INTO file_changes DEFAULT VALUES"]


def test_delete_vault_file_rejects_traversal(tmp_path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("keep me")

    result = files_mod.delete_vault_file("../outside.txt", root_dir=tmp_path)

    assert result == {"error": "Invalid path"}
    assert outside.exists()


def test_delete_vault_file_rejects_system_files(tmp_path):
    hidden = tmp_path / ".hash_index.json"
    hidden.write_text("{}")

    result = files_mod.delete_vault_file(".hash_index.json", root_dir=tmp_path)

    assert result == {"error": "Cannot delete system file"}
    assert hidden.exists()
