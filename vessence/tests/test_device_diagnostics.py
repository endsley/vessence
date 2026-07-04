import json

from jane_web.device_diagnostics import DeviceDiagnosticsLog


def test_append_writes_json_line_and_read_recent_returns_newest_first(tmp_path):
    path = tmp_path / "android_diagnostics.jsonl"
    log = DeviceDiagnosticsLog(path)

    log.append({"category": "wake", "message": "one"})
    log.append({"category": "chat_error", "message": "two"})

    assert path.read_text().splitlines() == [
        json.dumps({"category": "wake", "message": "one"}),
        json.dumps({"category": "chat_error", "message": "two"}),
    ]
    assert log.read_recent(2) == [
        {"category": "chat_error", "message": "two"},
        {"category": "wake", "message": "one"},
    ]


def test_read_recent_missing_file_and_malformed_lines(tmp_path):
    path = tmp_path / "android_diagnostics.jsonl"
    log = DeviceDiagnosticsLog(path)
    assert log.read_recent() == []

    path.write_text('{"ok": 1}\nnot json\n{"ok": 2}\n')

    assert log.read_recent(3) == [{"ok": 2}, {"ok": 1}]


def test_decode_recent_lines_returns_newest_valid_json_entries_first():
    assert DeviceDiagnosticsLog._decode_recent_lines(
        ['{"ok": 1}', "not json", '{"ok": 2}', '{"ok": 3}'],
        3,
    ) == [{"ok": 3}, {"ok": 2}]


def test_read_recent_preserves_existing_line_slice_behavior(tmp_path):
    path = tmp_path / "android_diagnostics.jsonl"
    path.write_text('{"i": 1}\n{"i": 2}\n{"i": 3}\n')

    assert DeviceDiagnosticsLog(path).read_recent(2) == [{"i": 3}, {"i": 2}]
