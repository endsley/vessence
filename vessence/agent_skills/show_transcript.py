#!/usr/bin/env python3
"""
show_transcript.py — read Jane conversation transcripts from the ledger DB.

Every turn Jane completes is logged by `ConversationManager._log_to_ledger`
into a single SQLite file, regardless of which underlying brain (Claude CLI,
Gemini CLI, Codex, …) produced the response:

    $VAULT_HOME/conversation_history_ledger.db

Schema:
    turns(id INTEGER PRIMARY KEY, session_id TEXT, timestamp DATETIME,
          role TEXT, content TEXT, tokens INTEGER, latency_ms REAL)

Because it's plain SQLite, any external tool can read it directly:

    # Last 4 turns of the most recent Android session:
    sqlite3 $VAULT_HOME/conversation_history_ledger.db \\
      "SELECT role, content FROM turns
         WHERE session_id = (SELECT session_id FROM turns
                             WHERE session_id LIKE 'jane_android_%'
                             ORDER BY id DESC LIMIT 1)
         ORDER BY id DESC LIMIT 4"

This script is a convenience wrapper over the same queries.

Usage:
    python show_transcript.py                           # list recent sessions
    python show_transcript.py --latest                  # dump most recent session
    python show_transcript.py --latest-android          # dump most recent Android session
    python show_transcript.py --android                 # list only Android sessions
    python show_transcript.py --turns N <args>          # limit to last N turns
    python show_transcript.py <session_id>              # dump a specific session
    python show_transcript.py --search <keyword>        # grep across transcripts
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

AMBIENT_BASE = os.environ.get("AMBIENT_BASE", os.path.expanduser("~/ambient"))
VAULT_HOME = os.environ.get("VAULT_HOME", os.path.join(AMBIENT_BASE, "vault"))
LEDGER_DB = Path(VAULT_HOME) / "conversation_history_ledger.db"


def _connect() -> sqlite3.Connection:
    if not LEDGER_DB.exists():
        print(f"ERROR: ledger DB not found at {LEDGER_DB}", file=sys.stderr)
        sys.exit(1)
    con = sqlite3.connect(f"file:{LEDGER_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _latest_session(con: sqlite3.Connection, android_only: bool = False) -> str | None:
    q = (
        "SELECT session_id FROM turns "
        + ("WHERE session_id LIKE 'jane_android_%' " if android_only else "")
        + "ORDER BY id DESC LIMIT 1"
    )
    row = con.execute(q).fetchone()
    return row["session_id"] if row else None


def _print_session(con: sqlite3.Connection, session_id: str, max_turns: int | None) -> None:
    if max_turns and max_turns > 0:
        rows = list(con.execute(
            "SELECT timestamp, role, content FROM turns "
            "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, max_turns * 2),
        ))
        rows.reverse()
    else:
        rows = list(con.execute(
            "SELECT timestamp, role, content FROM turns "
            "WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ))
    meta = con.execute(
        "SELECT COUNT(*) AS c, MIN(timestamp) AS s, MAX(timestamp) AS e "
        "FROM turns WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    print(f"Session: {session_id}")
    print(f"Range  : {meta['s']} → {meta['e']}  |  total turns: {meta['c']}  |  shown: {len(rows)}")
    print("=" * 72)
    for r in rows:
        label = "YOU" if r["role"] == "user" else "JANE"
        print(f"\n[{r['timestamp']}] {label}:")
        print(r["content"])
    print("\n" + "=" * 72)


def list_sessions(con: sqlite3.Connection, android_only: bool = False, limit: int = 25) -> None:
    q = """
        SELECT session_id,
               COUNT(*) AS turns,
               MAX(timestamp) AS last_ts,
               MIN(timestamp) AS first_ts
        FROM turns
        {where}
        GROUP BY session_id
        ORDER BY last_ts DESC
        LIMIT ?
    """.format(where="WHERE session_id LIKE 'jane_android_%'" if android_only else "")
    rows = list(con.execute(q, (limit,)))
    if not rows:
        print("No sessions found.")
        return
    print(f"{'LAST UPDATE':<20} {'TURNS':>6}  {'SESSION ID':<30}  FIRST USER MESSAGE")
    print("-" * 120)
    for r in rows:
        preview = _first_user_preview(con, r["session_id"])
        print(f"{r['last_ts']:<20} {r['turns']:>6}  {r['session_id']:<30}  {preview}")


def _first_user_preview(con: sqlite3.Connection, session_id: str, max_len: int = 80) -> str:
    row = con.execute(
        "SELECT content FROM turns WHERE session_id = ? AND role = 'user' "
        "ORDER BY id ASC LIMIT 1",
        (session_id,),
    ).fetchone()
    if not row:
        return "(no user turns)"
    text = " ".join(str(row["content"]).split())
    for prefix in ("[CURRENT CONVERSATION STATE]", "[Recent exchanges]",
                   "[WEB CHAT", "[ANDROID"):
        if text.startswith(prefix):
            tail = text.find("]")
            if tail != -1 and len(text) > tail + 2:
                text = text[tail + 1:].strip()
            break
    return (text[:max_len] + "…") if len(text) > max_len else text


def search_sessions(con: sqlite3.Connection, keyword: str, android_only: bool = False,
                    limit: int = 20) -> None:
    q = """
        SELECT session_id, MAX(timestamp) AS last_ts, COUNT(*) AS hits
        FROM turns
        WHERE content LIKE ?
        {android}
        GROUP BY session_id
        ORDER BY last_ts DESC
        LIMIT ?
    """.format(android="AND session_id LIKE 'jane_android_%'" if android_only else "")
    rows = list(con.execute(q, (f"%{keyword}%", limit)))
    if not rows:
        print(f"No sessions found containing: {keyword!r}")
        return
    print(f"Found {len(rows)} session(s) containing {keyword!r}:\n")
    for r in rows:
        print(f"  {r['last_ts']}  {r['session_id']:<30} ({r['hits']} hit(s))")


def _parse_turns_flag(args: list[str]) -> tuple[int | None, list[str]]:
    if "--turns" not in args:
        return None, args
    i = args.index("--turns")
    if i + 1 >= len(args):
        print("--turns requires a number", file=sys.stderr)
        sys.exit(1)
    try:
        n = int(args[i + 1])
    except ValueError:
        print(f"--turns: not an integer: {args[i + 1]}", file=sys.stderr)
        sys.exit(1)
    return n, args[:i] + args[i + 2:]


def _resolve_session(con: sqlite3.Connection, name: str) -> str | None:
    row = con.execute("SELECT 1 FROM turns WHERE session_id = ? LIMIT 1", (name,)).fetchone()
    if row:
        return name
    rows = list(con.execute(
        "SELECT DISTINCT session_id FROM turns WHERE session_id LIKE ? ORDER BY session_id",
        (f"%{name}%",),
    ))
    if len(rows) == 1:
        return rows[0]["session_id"]
    if len(rows) > 1:
        print(f"Ambiguous match for {name!r}:", file=sys.stderr)
        for r in rows[:10]:
            print(f"  {r['session_id']}", file=sys.stderr)
        sys.exit(1)
    return None


def main():
    args = sys.argv[1:]
    max_turns, args = _parse_turns_flag(args)
    con = _connect()
    try:
        if not args:
            list_sessions(con)
            return
        head = args[0]
        if head == "--android":
            list_sessions(con, android_only=True)
        elif head == "--latest":
            sid = _latest_session(con)
            if sid:
                _print_session(con, sid, max_turns)
            else:
                print("No sessions found.")
        elif head == "--latest-android":
            sid = _latest_session(con, android_only=True)
            if sid:
                _print_session(con, sid, max_turns)
            else:
                print("No Android sessions found.")
        elif head == "--search":
            if len(args) < 2:
                print("Usage: show_transcript.py --search <keyword>", file=sys.stderr)
                sys.exit(1)
            search_sessions(con, " ".join(args[1:]))
        elif head == "--search-android":
            if len(args) < 2:
                print("Usage: show_transcript.py --search-android <keyword>", file=sys.stderr)
                sys.exit(1)
            search_sessions(con, " ".join(args[1:]), android_only=True)
        else:
            sid = _resolve_session(con, head)
            if sid is None:
                print(f"Session not found: {head}", file=sys.stderr)
                sys.exit(1)
            _print_session(con, sid, max_turns)
    finally:
        con.close()


if __name__ == "__main__":
    main()
