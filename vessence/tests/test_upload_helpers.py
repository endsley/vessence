from pathlib import Path

from jane_web.upload_helpers import (
    duplicate_upload_result,
    hash_index_entry,
    next_available_path,
    parse_upload_descriptions,
    upload_description,
    upload_memory_fact_command,
    upload_memory_fact_text,
    upload_safe_name,
    upload_subdir,
    upload_success_result,
)


def test_parse_upload_descriptions_returns_only_lists():
    assert parse_upload_descriptions('["one", null, 3]') == ["one", None, 3]
    assert parse_upload_descriptions('{"not": "a list"}') == []
    assert parse_upload_descriptions("not json") == []
    assert parse_upload_descriptions(None) == []


def test_upload_description_strips_and_handles_missing_slots():
    descriptions = ["  first  ", None, 4]

    assert upload_description(descriptions, 0) == "first"
    assert upload_description(descriptions, 1) == ""
    assert upload_description(descriptions, 2) == "4"
    assert upload_description(descriptions, 3) == ""


def test_upload_subdir_preserves_existing_destination_rules():
    assert upload_subdir("docs/inbox/", "text/plain", lambda mime: f"routed/{mime}") == "docs/inbox"
    assert upload_subdir("/", "text/plain", lambda mime: f"routed/{mime}") == ""
    assert upload_subdir("", "image/png", lambda mime: f"routed/{mime}") == "routed/image/png"


def test_upload_safe_name_preserves_image_and_plain_file_rules():
    def descriptive(filename: str, description: str) -> str:
        return f"{Path(filename).stem}-{description}.png"

    assert upload_safe_name(
        "../photo.png",
        "cat",
        is_image_upload=True,
        destination="",
        descriptive_filename=descriptive,
    ) == "photo-cat.png"
    assert upload_safe_name(
        "../photo.png",
        "cat",
        is_image_upload=True,
        destination="images",
        descriptive_filename=descriptive,
    ) == "photo.png"
    assert upload_safe_name(
        "../notes.md",
        "",
        is_image_upload=False,
        destination="",
        descriptive_filename=descriptive,
    ) == "notes.md"


def test_next_available_path_suffixes_existing_files(tmp_path):
    (tmp_path / "notes.md").write_text("one")
    (tmp_path / "notes_1.md").write_text("two")

    assert next_available_path(tmp_path, "notes.md") == tmp_path / "notes_2.md"
    assert next_available_path(tmp_path, "new.md") == tmp_path / "new.md"


def test_upload_result_and_hash_index_shapes():
    dest_path = Path("/vault/docs/notes.md")

    assert duplicate_upload_result("notes.md", {"path": "docs/original.md"}) == {
        "name": "notes.md",
        "status": "duplicate",
        "existing_path": "docs/original.md",
    }
    assert duplicate_upload_result(None, {}) == {
        "name": None,
        "status": "duplicate",
        "existing_path": "",
    }
    assert hash_index_entry(dest_path, "docs/notes.md", "meeting notes") == {
        "filename": "notes.md",
        "path": "docs/notes.md",
        "description": "meeting notes",
    }
    assert upload_success_result(
        "source.md",
        dest_path,
        "docs/notes.md",
        "docs",
        "meeting notes",
    ) == {
        "name": "source.md",
        "saved_name": "notes.md",
        "status": "ok",
        "path": "docs/notes.md",
        "subdir": "docs",
        "description": "meeting notes",
    }


def test_upload_memory_fact_text_and_command_preserve_common_arguments():
    fact_text = upload_memory_fact_text("via web UI", "notes.md", "docs")

    assert fact_text == "File uploaded via web UI: notes.md saved to vault/docs/"
    assert upload_memory_fact_command(
        python_bin="/python",
        add_fact_script="/add_fact.py",
        fact_text=fact_text,
        user_id="child",
        memory_path="/memory",
    ) == [
        "/python",
        "/add_fact.py",
        fact_text,
        "--topic",
        "vault",
        "--subtopic",
        "upload",
        "--user-id",
        "child",
        "--memory-path",
        "/memory",
    ]
    assert upload_memory_fact_command(
        python_bin="/python",
        add_fact_script="/add_fact.py",
        fact_text=fact_text,
        user_id="child",
    ) == [
        "/python",
        "/add_fact.py",
        fact_text,
        "--topic",
        "vault",
        "--subtopic",
        "upload",
        "--user-id",
        "child",
    ]
