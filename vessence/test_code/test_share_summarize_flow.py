"""End-to-end test for the article share → summarize_now → TTS flow.

Tests three layers:

1. **Server endpoint**: POST /api/briefing/articles/summarize_now with a real URL
   returns {title, summary} that's not empty and looks like English prose.

2. **Android wiring (static check)**: confirms the Kotlin broadcast/receiver
   plumbing is intact:
     - ShareReceiverActivity dispatches to MainActivity with intent extras
     - MainActivity's handleSharedSummaryIntent() sends a broadcast
     - ChatViewModel's sharedSummaryReceiver listens and calls tts.speak()

3. **Self-correction**: if any step fails, prints actionable diagnostics
   identifying which layer broke.

Run:
    python test_code/test_share_summarize_flow.py [URL]
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import httpx

SERVER = "http://localhost:8080"
DEFAULT_URL = "https://en.wikipedia.org/wiki/Pickleball"
ANDROID_ROOT = Path("/home/chieh/ambient/vessence/android/app/src/main/java/com/vessences/android")

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def passed(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def failed(msg: str) -> None:
    print(f"  {RED}✗{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}!{RESET} {msg}")


# ── Test 1: Server endpoint ──────────────────────────────────────────────────


def test_summarize_endpoint(url: str) -> dict | None:
    """POST the URL to summarize_now, validate the response shape."""
    print(f"\n[1] Server endpoint: POST {SERVER}/api/briefing/articles/summarize_now")
    print(f"    URL: {url}")

    started = time.time()
    try:
        r = httpx.post(
            f"{SERVER}/api/briefing/articles/summarize_now",
            json={"url": url},
            timeout=120.0,
        )
    except Exception as e:
        failed(f"HTTP request failed: {e}")
        return None

    elapsed = time.time() - started
    print(f"    Status: HTTP {r.status_code} in {elapsed:.1f}s")

    if r.status_code != 200:
        failed(f"Expected 200, got {r.status_code}: {r.text[:200]}")
        return None
    passed("HTTP 200")

    try:
        data = r.json()
    except Exception as e:
        failed(f"Response is not JSON: {e}")
        return None
    passed("Response is JSON")

    title = data.get("title", "")
    summary = data.get("summary", "")
    if not title:
        warn("Response has no 'title' field (not blocking)")
    else:
        passed(f"Title: {title[:80]}")

    if not summary:
        failed("Response has no 'summary' field — Android would show 'Could not summarize'")
        return None
    if len(summary) < 30:
        warn(f"Summary is suspiciously short ({len(summary)} chars): {summary!r}")
    else:
        passed(f"Summary: {len(summary)} chars — \"{summary[:120]}…\"")

    # Sanity check: summary should be English-ish prose
    if not re.search(r"[a-zA-Z]{4,}\s+[a-zA-Z]{3,}", summary):
        warn("Summary doesn't look like English prose — TTS may sound bad")
    else:
        passed("Summary looks like coherent prose")

    return data


# ── Test 2: Android wiring ───────────────────────────────────────────────────


def test_android_wiring() -> bool:
    """Static-check the Kotlin code path from share → MainActivity → ChatViewModel TTS."""
    print(f"\n[2] Android Kotlin wiring (static check)")

    checks = [
        # ShareReceiverActivity must launch MainActivity with summary extras
        (
            ANDROID_ROOT / "ShareReceiverActivity.kt",
            r'putExtra\("shared_summary_text"',
            "ShareReceiverActivity passes summary text to MainActivity",
        ),
        (
            ANDROID_ROOT / "ShareReceiverActivity.kt",
            r'startActivity\(mainIntent\)',
            "ShareReceiverActivity launches MainActivity",
        ),
        # MainActivity must read the extra and broadcast it
        (
            ANDROID_ROOT / "MainActivity.kt",
            r'handleSharedSummaryIntent',
            "MainActivity defines handleSharedSummaryIntent",
        ),
        (
            ANDROID_ROOT / "MainActivity.kt",
            r'"com\.vessences\.android\.SHARED_SUMMARY_READY"',
            "MainActivity broadcasts SHARED_SUMMARY_READY",
        ),
        (
            ANDROID_ROOT / "MainActivity.kt",
            r'handleSharedSummaryIntent\(intent\)',
            "MainActivity.onNewIntent calls handleSharedSummaryIntent",
        ),
        # ChatViewModel must register a receiver and call tts.speak
        (
            ANDROID_ROOT / "ui/chat/ChatViewModel.kt",
            r'sharedSummaryReceiver',
            "ChatViewModel defines sharedSummaryReceiver",
        ),
        (
            ANDROID_ROOT / "ui/chat/ChatViewModel.kt",
            r'"com\.vessences\.android\.SHARED_SUMMARY_READY"',
            "ChatViewModel registers receiver for SHARED_SUMMARY_READY",
        ),
        (
            ANDROID_ROOT / "ui/chat/ChatViewModel.kt",
            r'tts\.speak\(text\)',
            "ChatViewModel calls tts.speak(text) on receive",
        ),
    ]

    all_pass = True
    for path, pattern, desc in checks:
        if not path.exists():
            failed(f"Missing file: {path}")
            all_pass = False
            continue
        if re.search(pattern, path.read_text()):
            passed(desc)
        else:
            failed(f"NOT FOUND: {desc} (pattern: {pattern})")
            all_pass = False
    return all_pass


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    print("=" * 70)
    print("Share → Summarize → TTS End-to-End Test")
    print("=" * 70)

    server_data = test_summarize_endpoint(url)
    server_ok = server_data is not None

    android_ok = test_android_wiring()

    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    if server_ok:
        passed("Server side: summarize_now endpoint returns valid summary")
    else:
        failed("Server side: summarize_now endpoint broken — Android will get nothing to speak")

    if android_ok:
        passed("Android wiring: share → broadcast → receiver → tts.speak() all connected")
    else:
        failed("Android wiring: at least one link in the chain is broken")

    if server_ok and android_ok:
        print(f"\n{GREEN}✅ End-to-end flow is functionally complete.{RESET}")
        print("   Real-device verification:")
        print("   1. Update phone to v0.2.x with these changes")
        print("   2. Open Chrome, share any article URL → Vessence")
        print("   3. Pick 'Summarize Now'")
        print("   4. Expected: Vessence app comes to focus, summary appears")
        print("      in chat as Jane message, TTS reads it aloud")
        return 0
    else:
        print(f"\n{RED}❌ At least one layer is broken — see ✗ markers above.{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
