"""In-memory server-to-Android command queue."""

from __future__ import annotations

import threading


class DeviceCommandQueue:
    def __init__(self):
        self.commands: list[dict] = []
        self.lock = threading.Lock()

    def queue(self, command: str, **kwargs) -> None:
        """Queue a command for the Android device to pick up on next poll."""
        with self.lock:
            self.commands.append({"command": command, **kwargs})

    def drain(self) -> list[dict]:
        """Return and clear all pending commands."""
        with self.lock:
            commands = list(self.commands)
            self.commands.clear()
        return commands
