from jane_web.device_commands import DeviceCommandQueue


def test_device_command_queue_preserves_order_and_payloads():
    queue = DeviceCommandQueue()

    queue.queue("sync_sms")
    queue.queue("refresh_settings", user_id="u1", force=True)

    assert queue.drain() == [
        {"command": "sync_sms"},
        {"command": "refresh_settings", "user_id": "u1", "force": True},
    ]
    assert queue.drain() == []


def test_device_command_queue_drain_returns_copy_before_clearing():
    queue = DeviceCommandQueue()
    queue.queue("sync_sms")

    drained = queue.drain()
    drained.append({"command": "mutated"})

    assert queue.commands == []
    assert queue.drain() == []
