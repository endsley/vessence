from jane_web.chat_stream_limits import mark_stream_closed, mark_stream_open, stream_limit_exceeded


def test_stream_limit_exceeded_skips_local_hosts():
    active = {"127.0.0.1": 99, "::1": 99, "localhost": 99}

    assert stream_limit_exceeded(active, "127.0.0.1", 3) is False
    assert stream_limit_exceeded(active, "::1", 3) is False
    assert stream_limit_exceeded(active, "localhost", 3) is False


def test_stream_limit_exceeded_uses_current_remote_count():
    assert stream_limit_exceeded({"1.2.3.4": 2}, "1.2.3.4", 3) is False
    assert stream_limit_exceeded({"1.2.3.4": 3}, "1.2.3.4", 3) is True
    assert stream_limit_exceeded({}, "1.2.3.4", 3) is False


def test_mark_stream_open_increments_and_returns_count():
    active = {}

    assert mark_stream_open(active, "1.2.3.4") == 1
    assert mark_stream_open(active, "1.2.3.4") == 2
    assert active == {"1.2.3.4": 2}


def test_mark_stream_closed_decrements_and_removes_zero_count():
    active = {"1.2.3.4": 2}

    assert mark_stream_closed(active, "1.2.3.4") == 1
    assert active == {"1.2.3.4": 1}
    assert mark_stream_closed(active, "1.2.3.4") == 0
    assert active == {}
    assert mark_stream_closed(active, "1.2.3.4") == 0
    assert active == {}
