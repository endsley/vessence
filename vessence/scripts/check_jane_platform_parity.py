#!/usr/bin/env python3
"""Guardrail for Jane web/Android parity-sensitive changes.

If staged files touch Jane web or Android chat code without touching the other
platform, prompt for an explicit acknowledgment before allowing commit.
"""
from __future__ import annotations

import os
import sys
WEB_PREFIXES = (
    "jane_web/",
    "vault_web/templates/jane.html",
    "vault_web/static/",
    "vessence/jane_web/",
    "vessence/vault_web/templates/jane.html",
    "vessence/vault_web/static/",
)

ANDROID_PREFIXES = (
    "android/app/src/main/java/com/vessences/android/ui/chat/",
    "android/app/src/main/java/com/vessences/android/ui/components/MessageBubble.kt",
    "vessence/android/app/src/main/java/com/vessences/android/ui/chat/",
    "vessence/android/app/src/main/java/com/vessences/android/ui/components/MessageBubble.kt",
)


def _normalize(path: str) -> str:
    return path.strip().replace("\\", "/")


def classify_paths(paths: list[str]) -> tuple[bool, bool]:
    web_changed = False
    android_changed = False
    for raw in paths:
        path = _normalize(raw)
        if not path:
            continue
        if any(path.startswith(prefix) for prefix in WEB_PREFIXES):
            web_changed = True
        if any(path.startswith(prefix) for prefix in ANDROID_PREFIXES):
            android_changed = True
    return web_changed, android_changed


def parity_message(web_changed: bool, android_changed: bool) -> str | None:
    if web_changed and not android_changed:
        return (
            "Jane parity check: staged changes touch web Jane but not Android Jane.\n\n"
            "Before committing, decide whether the same display/logic change should also be made in Android."
        )
    if android_changed and not web_changed:
        return (
            "Jane parity check: staged changes touch Android Jane but not web Jane.\n\n"
            "Before committing, decide whether the same display/logic change should also be made in web Jane."
        )
    return None


def main(argv: list[str]) -> int:
    if os.environ.get("JANE_PLATFORM_PARITY_ACK") == "1":
        return 0

    paths = argv[1:]
    web_changed, android_changed = classify_paths(paths)
    message = parity_message(web_changed, android_changed)
    if not message:
        return 0

    if not sys.stdin.isatty():
        print(message)
        print("\nBlocked commit: no TTY available to confirm Jane platform parity.")
        print("Set JANE_PLATFORM_PARITY_ACK=1 to bypass intentionally.")
        return 1

    print(message)
    reply = input("\nHave you already reviewed the matching platform impact? [y/N]: ").strip().lower()
    if reply in ("y", "yes"):
        return 0

    print("\nBlocked commit: review or implement the matching Jane platform change first.")
    print("If this is intentionally one-platform-only, re-run with JANE_PLATFORM_PARITY_ACK=1.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
