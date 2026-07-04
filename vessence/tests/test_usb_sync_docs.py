from startup_code import usb_sync


def _command_label(cmd: list[str]) -> str:
    return "|".join(cmd)


def test_build_restore_manifest_uses_command_runner_and_sync_state() -> None:
    sync_state = {"snapshots": ["2026-07-01"], "files_added": 3}

    manifest = usb_sync.build_restore_manifest(
        sync_state,
        generated_at="2026-07-04T12:00:00",
        command_runner=_command_label,
    )

    assert manifest["generated_at"] == "2026-07-04T12:00:00"
    assert manifest["system"] == {
        "os": "lsb_release|-ds",
        "kernel": "uname|-r",
        "python_adk_venv": f"{usb_sync.ADK_PYTHON}|--version",
    }
    assert manifest["claude_code"]["version"].endswith(".local/bin/claude|--version")
    assert manifest["ollama_models"] == "ollama|list"
    assert manifest["crontab"] == "crontab|-l"
    assert manifest["pip_freeze_adk_venv"] == f"{usb_sync.ADK_PIP}|freeze"
    assert manifest["sync_state"] == sync_state


def test_restore_docs_markdown_preserves_restore_steps_and_snapshots() -> None:
    sync_state = {"snapshots": ["2026-07-01", "2026-07-08"]}
    manifest = {"generated_at": "2026-07-04T12:00:00"}

    markdown = usb_sync.restore_docs_markdown(manifest, sync_state)

    assert markdown.startswith("# Project Ambient")
    assert "Generated: 2026-07-04T12:00:00" in markdown
    assert "rsync -av $USB/current/ambient/vessence/" in markdown
    assert "crontab $HOME/ambient/vessence/configs/crontab_backup.txt" in markdown
    assert "- 2026-07-01\n- 2026-07-08" in markdown
