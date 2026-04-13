#!/usr/bin/env python3
"""
show_transcript.py — read Jane conversation transcripts from adk/session.db

Usage:
    python show_transcript.py                        # list all sessions with preview
    python show_transcript.py --android              # list only jane_android_* sessions
    python show_transcript.py <session_id>           # print full transcript
    python show_transcript.py --latest               # print most recent session
    python show_transcript.py --latest-android       # print most recent Android session
    python show_transcript.py --search <keyword>     # find sessions containing keyword

Session DB: $AMBIENT_BASE/vessence-data/adk/session.db
Android sessions use IDs like: jane_android_xxxxxxxx

The --search flag is the main tool for picking the right session when there are
multiple: e.g. --search "login screen" or --search "tax" finds the right one fast.
"""

import json
import os
import sqlite3
import sys
from datetime import datetime

DB_PATH = os.path.expandvars(
    os.path.join(os.environ.get("AMBIENT_BASE", os.path.expanduser("~/ambient")),
                 "vessence-data/adk/session.db")
)


def get_conn():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)
    return sqlite3.connect(DB_PATH)


def _first_user_message(cur, session_id, max_len=70):
    """Return the first meaningful user message text from a session."""
    cur.execute("""
        SELECT event_data FROM events
        WHERE session_id = ?
        ORDER BY timestamp
        LIMIT 30
    """, (session_id,))
    for (event_data,) in cur.fetchall():
        try:
            data = json.loads(event_data)
        except json.JSONDecodeError:
            continue
        content = data.get("content", {})
        if content.get("role") != "user":
            continue
        parts = content.get("parts", [])
        text = " ".join(p.get("text", "") for p in parts if "text" in p).strip()
        # Skip pure system injections (they start with [WEB CHAT or [SYSTEM)
        if text.startswith("[WEB CHAT") or text.startswith("[SYSTEM") or text.startswith("[ANDROID"):
            # Try to find the real user text after the injection block
            bracket_end = text.find("]", text.find("["))
            remainder = text[bracket_end + 1:].strip() if bracket_end != -1 else ""
            if len(remainder) > 10:
                text = remainder
            else:
                continue
        if len(text) > max_len:
            text = text[:max_len] + "…"
        return text
    return "(no user messages)"


def list_sessions(android_only=False):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.id, s.app_name, s.update_time,
               COUNT(e.id) as msg_count
        FROM sessions s
        LEFT JOIN events e ON e.session_id = s.id
        GROUP BY s.id
        ORDER BY s.update_time DESC
    """)
    rows = cur.fetchall()

    if android_only:
        rows = [r for r in rows if r[0].startswith("jane_android_")]

    if not rows:
        print("No sessions found.")
        conn.close()
        return

    print(f"{'SESSION ID':<40} {'UPDATED':<17} {'EVT':>4}  FIRST MESSAGE")
    print("-" * 100)
    for sid, app, ts, count in rows:
        dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "?"
        preview = _first_user_message(cur, sid)
        marker = "[android] " if sid.startswith("jane_android_") else ""
        print(f"{sid:<40} {dt:<17} {count:>4}  {marker}{preview}")

    conn.close()


def print_transcript(session_id):
    conn = get_conn()
    cur = conn.cursor()

    # Verify session exists
    cur.execute("SELECT id, app_name, update_time FROM sessions WHERE id = ?", (session_id,))
    row = cur.fetchone()
    if not row:
        # Fuzzy match
        cur.execute("SELECT id FROM sessions WHERE id LIKE ?", (f"%{session_id}%",))
        matches = cur.fetchall()
        if not matches:
            print(f"Session not found: {session_id}", file=sys.stderr)
            sys.exit(1)
        if len(matches) == 1:
            session_id = matches[0][0]
            cur.execute("SELECT id, app_name, update_time FROM sessions WHERE id = ?", (session_id,))
            row = cur.fetchone()
        else:
            print(f"Ambiguous match for '{session_id}':", file=sys.stderr)
            for m in matches:
                print(f"  {m[0]}", file=sys.stderr)
            sys.exit(1)

    sid, app, ts = row
    dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "?"
    print(f"Session: {sid}  |  app={app}  |  updated={dt}")
    print("=" * 70)

    cur.execute("""
        SELECT event_data, timestamp FROM events
        WHERE session_id = ?
        ORDER BY timestamp
    """, (session_id,))
    events = cur.fetchall()
    conn.close()

    if not events:
        print("(no events)")
        return

    for event_data, ts in events:
        try:
            data = json.loads(event_data)
        except json.JSONDecodeError:
            continue

        content = data.get("content", {})
        role = content.get("role", "")
        parts = content.get("parts", [])

        if not role or not parts:
            continue

        text_parts = [p.get("text", "") for p in parts if "text" in p]
        text = "\n".join(text_parts).strip()
        if not text:
            continue

        # Skip system injection noise (long prefixes injected by Jane)
        if role == "user" and len(text) > 2000 and "[SYSTEM" in text[:500]:
            text = text[:300] + "\n...[system context truncated]..."

        dt_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S") if ts else ""
        label = "YOU" if role == "user" else "JANE"
        print(f"\n[{dt_str}] {label}:")
        print(text)

    print("\n" + "=" * 70)


def search_sessions(keyword, android_only=False):
    """Find sessions whose event content contains keyword. Shows matching snippets."""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT e.session_id, e.event_data, e.timestamp,
               s.update_time
        FROM events e
        JOIN sessions s ON s.id = e.session_id
        ORDER BY e.timestamp
    """)

    # Group hits by session
    hits = {}  # session_id -> [(timestamp, role, snippet), ...]
    kw_lower = keyword.lower()
    for session_id, event_data, ts, update_time in cur.fetchall():
        if android_only and not session_id.startswith("jane_android_"):
            continue
        try:
            data = json.loads(event_data)
        except json.JSONDecodeError:
            continue
        content = data.get("content", {})
        role = content.get("role", "")
        parts = content.get("parts", [])
        text = " ".join(p.get("text", "") for p in parts if "text" in p)
        if kw_lower not in text.lower():
            continue
        # Extract a snippet around the keyword
        idx = text.lower().find(kw_lower)
        start = max(0, idx - 40)
        end = min(len(text), idx + len(keyword) + 60)
        snippet = ("…" if start > 0 else "") + text[start:end].strip() + ("…" if end < len(text) else "")
        snippet = snippet.replace("\n", " ")
        if session_id not in hits:
            hits[session_id] = {"update_time": update_time, "matches": []}
        hits[session_id]["matches"].append((ts, role, snippet))

    conn.close()

    if not hits:
        print(f"No sessions found containing: {keyword!r}")
        return

    # Sort sessions by most recently updated
    sorted_sessions = sorted(hits.items(), key=lambda x: x[1]["update_time"], reverse=True)

    print(f"Found {len(hits)} session(s) containing {keyword!r}:\n")
    for sid, info in sorted_sessions:
        dt = datetime.fromtimestamp(info["update_time"]).strftime("%Y-%m-%d %H:%M")
        marker = "[android] " if sid.startswith("jane_android_") else ""
        print(f"  {marker}{sid}  (updated {dt})")
        for ts, role, snippet in info["matches"][:3]:  # show up to 3 hits per session
            ts_str = datetime.fromtimestamp(ts).strftime("%H:%M") if ts else ""
            label = "YOU" if role == "user" else "JANE"
            print(f"    [{ts_str}] {label}: {snippet}")
        if len(info["matches"]) > 3:
            print(f"    … and {len(info['matches']) - 3} more matches")
        print()

    print(f"To read a full transcript: python show_transcript.py <session_id>")


def get_latest_session(android_only=False):
    conn = get_conn()
    cur = conn.cursor()
    if android_only:
        cur.execute("""
            SELECT id FROM sessions
            WHERE id LIKE 'jane_android_%'
            ORDER BY update_time DESC LIMIT 1
        """)
    else:
        cur.execute("SELECT id FROM sessions ORDER BY update_time DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def main():
    args = sys.argv[1:]

    if not args:
        list_sessions()
    elif args[0] == "--android":
        list_sessions(android_only=True)
    elif args[0] == "--latest":
        sid = get_latest_session()
        if sid:
            print_transcript(sid)
        else:
            print("No sessions found.")
    elif args[0] == "--latest-android":
        sid = get_latest_session(android_only=True)
        if sid:
            print_transcript(sid)
        else:
            print("No Android sessions found. Android sessions use IDs like: jane_android_xxxxxxxx")
    elif args[0] == "--search":
        if len(args) < 2:
            print("Usage: show_transcript.py --search <keyword>", file=sys.stderr)
            sys.exit(1)
        keyword = " ".join(args[1:])
        search_sessions(keyword)
    elif args[0] == "--search-android":
        if len(args) < 2:
            print("Usage: show_transcript.py --search-android <keyword>", file=sys.stderr)
            sys.exit(1)
        keyword = " ".join(args[1:])
        search_sessions(keyword, android_only=True)
    else:
        print_transcript(args[0])


if __name__ == "__main__":
    main()
