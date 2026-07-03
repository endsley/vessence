from dataclasses import dataclass

import pytest

from jane_web.chat_stream_dedupe import begin_turn_dedupe, finalize_turn_dedupe, iter_replay_ndjson


@dataclass
class Row:
    status: str
    response_json: str | None = None


class FakeDedupeStore:
    def __init__(self, *, lookup_rows=None, wait_result=None, begin_result=True):
        self.lookup_rows = list(lookup_rows or [])
        self.wait_result = wait_result
        self.begin_result = begin_result
        self.calls = []

    def lookup(self, turn_id):
        self.calls.append(("lookup", turn_id))
        if self.lookup_rows:
            return self.lookup_rows.pop(0)
        return None

    def wait_for_completion(self, turn_id):
        self.calls.append(("wait_for_completion", turn_id))
        return self.wait_result

    def try_begin(self, turn_id, session_id):
        self.calls.append(("try_begin", turn_id, session_id))
        return self.begin_result

    def mark_completed(self, turn_id, response_json):
        self.calls.append(("mark_completed", turn_id, response_json))

    def mark_failed(self, turn_id):
        self.calls.append(("mark_failed", turn_id))


@pytest.mark.asyncio
async def test_begin_turn_dedupe_replays_completed_response():
    store = FakeDedupeStore(lookup_rows=[Row("completed", "a\n")])

    decision = await begin_turn_dedupe(" turn-1 ", "session", store=store)

    assert decision.active_turn_id == ""
    assert decision.replay_response_json == "a\n"
    assert decision.replay_reason == "completed"
    assert store.calls == [("lookup", "turn-1")]


@pytest.mark.asyncio
async def test_begin_turn_dedupe_waits_for_pending_response():
    store = FakeDedupeStore(lookup_rows=[Row("pending")], wait_result="done\n")

    decision = await begin_turn_dedupe("turn-1", "session", store=store)

    assert decision.active_turn_id == ""
    assert decision.replay_response_json == "done\n"
    assert decision.replay_reason == "joined"
    assert decision.pending_join_waited is True
    assert store.calls == [
        ("lookup", "turn-1"),
        ("wait_for_completion", "turn-1"),
    ]


@pytest.mark.asyncio
async def test_begin_turn_dedupe_dispatches_new_turn_after_begin():
    store = FakeDedupeStore(lookup_rows=[None], begin_result=True)

    decision = await begin_turn_dedupe("turn-1", "session", store=store)

    assert decision.active_turn_id == "turn-1"
    assert decision.replay_response_json is None
    assert store.calls == [
        ("lookup", "turn-1"),
        ("try_begin", "turn-1", "session"),
    ]


@pytest.mark.asyncio
async def test_begin_turn_dedupe_replays_completed_race_after_failed_begin():
    store = FakeDedupeStore(
        lookup_rows=[None, Row("completed", "cached\n")],
        begin_result=False,
    )

    decision = await begin_turn_dedupe("turn-1", "session", store=store)

    assert decision.active_turn_id == ""
    assert decision.replay_response_json == "cached\n"
    assert decision.replay_reason == "race_completed"
    assert store.calls == [
        ("lookup", "turn-1"),
        ("try_begin", "turn-1", "session"),
        ("lookup", "turn-1"),
    ]


@pytest.mark.asyncio
async def test_begin_turn_dedupe_disables_dedupe_when_begin_race_has_no_cached_response():
    store = FakeDedupeStore(lookup_rows=[None, Row("pending")], begin_result=False)

    decision = await begin_turn_dedupe("turn-1", "session", store=store)

    assert decision.active_turn_id == ""
    assert decision.replay_response_json is None


@pytest.mark.asyncio
async def test_begin_turn_dedupe_preserves_pending_wait_signal_after_timeout():
    store = FakeDedupeStore(lookup_rows=[Row("pending"), Row("pending")], begin_result=False)

    decision = await begin_turn_dedupe("turn-1", "session", store=store)

    assert decision.active_turn_id == ""
    assert decision.replay_response_json is None
    assert decision.pending_join_waited is True


@pytest.mark.asyncio
async def test_iter_replay_ndjson_preserves_nonblank_lines_with_newlines():
    lines = [line async for line in iter_replay_ndjson("a\n\n  \nb\n")]

    assert lines == ["a\n", "b\n"]


def test_finalize_turn_dedupe_marks_completed_or_failed():
    store = FakeDedupeStore()

    finalize_turn_dedupe("turn-1", ["a", "\n"], had_error=False, store=store)
    finalize_turn_dedupe("turn-2", ["ignored"], had_error=True, store=store)
    finalize_turn_dedupe("", ["ignored"], had_error=False, store=store)

    assert store.calls == [
        ("mark_completed", "turn-1", "a\n"),
        ("mark_failed", "turn-2"),
    ]
