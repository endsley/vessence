from memory.v1 import janitor_memory


def test_stale_swap_does_not_block_when_swap_io_is_idle(monkeypatch):
    monkeypatch.setattr(janitor_memory, "JANITOR_MAX_SWAP_PERCENT", 10.0)
    monkeypatch.setattr(janitor_memory, "JANITOR_MAX_SWAP_IO_PAGES_PER_SEC", 20.0)

    reason = janitor_memory._swap_pressure_reason(
        swap_total_bytes=8 * 1024**3,
        swap_percent=47.0,
        available_gb=20.0,
        swap_io_rates=(0.1, 0.0),
    )

    assert reason is None


def test_active_swap_io_blocks_janitor(monkeypatch):
    monkeypatch.setattr(janitor_memory, "JANITOR_MAX_SWAP_PERCENT", 10.0)
    monkeypatch.setattr(janitor_memory, "JANITOR_MAX_SWAP_IO_PAGES_PER_SEC", 20.0)

    reason = janitor_memory._swap_pressure_reason(
        swap_total_bytes=8 * 1024**3,
        swap_percent=47.0,
        available_gb=20.0,
        swap_io_rates=(5.0, 123.0),
    )

    assert reason is not None
    assert "active swap I/O" in reason


def test_low_available_memory_with_swap_blocks_janitor(monkeypatch):
    monkeypatch.setattr(janitor_memory, "JANITOR_MAX_SWAP_PERCENT", 10.0)
    monkeypatch.setattr(janitor_memory, "JANITOR_MIN_AVAILABLE_GB", 4.0)

    reason = janitor_memory._swap_pressure_reason(
        swap_total_bytes=8 * 1024**3,
        swap_percent=47.0,
        available_gb=3.5,
        swap_io_rates=(0.0, 0.0),
    )

    assert reason is not None
    assert "available memory too low" in reason
