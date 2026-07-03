from pathlib import Path

from agent_skills import update_idle_state
from agent_skills.idle_state_helpers import (
    atomic_tmp_path,
    claude_code_activity_path,
    idle_state_payload,
)


def test_update_idle_state_uses_extracted_helpers():
    assert update_idle_state._atomic_tmp_path is atomic_tmp_path
    assert update_idle_state._claude_code_activity_path is claude_code_activity_path
    assert update_idle_state._idle_state_payload is idle_state_payload


def test_idle_state_payload_uses_utc_timestamp_format():
    assert idle_state_payload(0) == {
        "last_active_ts": 0,
        "last_active_iso": "1970-01-01T00:00:00Z",
    }


def test_atomic_tmp_path_preserves_suffix_append_behavior():
    assert atomic_tmp_path(Path("/tmp/idle_state.json")) == Path("/tmp/idle_state.json.tmp")
    assert atomic_tmp_path(Path("/tmp/no_suffix")) == Path("/tmp/no_suffix.tmp")


def test_claude_code_activity_path_sits_next_to_idle_state_file():
    assert claude_code_activity_path("/tmp/state/idle_state.json") == Path(
        "/tmp/state/claude_code_activity.json"
    )
