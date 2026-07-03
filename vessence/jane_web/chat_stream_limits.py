"""Active stream accounting helpers for Jane chat streaming."""
from __future__ import annotations

LOCAL_STREAM_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def stream_limit_exceeded(active_streams: dict[str, int], stream_ip: str, max_streams: int) -> bool:
    if stream_ip in LOCAL_STREAM_HOSTS:
        return False
    return active_streams.get(stream_ip, 0) >= max_streams


def mark_stream_open(active_streams: dict[str, int], stream_ip: str) -> int:
    count = active_streams.get(stream_ip, 0) + 1
    active_streams[stream_ip] = count
    return count


def mark_stream_closed(active_streams: dict[str, int], stream_ip: str) -> int:
    count = max(0, active_streams.get(stream_ip, 1) - 1)
    if count == 0:
        active_streams.pop(stream_ip, None)
    else:
        active_streams[stream_ip] = count
    return count
