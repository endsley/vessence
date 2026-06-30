from jane_web.jane_v2.awaiting_markers import (
    AwaitingDeltaStripper,
    extract_awaiting_marker,
)


def test_extract_awaiting_marker_only_accepts_trailing_marker():
    text = "I mentioned [[AWAITING:ignore_me]] earlier, then answered."

    assert extract_awaiting_marker(text) == (text, None)
    assert extract_awaiting_marker(text + " [[AWAITING:real topic]]") == (
        text,
        "real_topic",
    )


def test_extract_awaiting_marker_caps_topic_length():
    cleaned, topic = extract_awaiting_marker(f"done [[AWAITING:{'a' * 100}]]")

    assert cleaned == "done"
    assert topic == "a" * 60


def test_awaiting_delta_stripper_handles_split_marker():
    stripper = AwaitingDeltaStripper()
    chunks = ["Answer text", " before marker [[AWA", "ITING:choice]]"]

    visible = "".join(stripper.feed(chunk) for chunk in chunks)
    visible += stripper.flush()

    assert visible == "Answer text before marker "


def test_awaiting_delta_stripper_flushes_non_marker_tail():
    stripper = AwaitingDeltaStripper()
    visible = stripper.feed("short [[AWAI") + stripper.flush()

    assert visible == "short [[AWAI"
