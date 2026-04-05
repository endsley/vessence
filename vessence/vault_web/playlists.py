"""playlists.py — Playlist CRUD."""
import secrets
from .database import get_db


def list_playlists() -> list:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT p.*, COUNT(t.id) as track_count "
            "FROM playlists p LEFT JOIN playlist_tracks t ON t.playlist_id=p.id "
            "GROUP BY p.id ORDER BY p.updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_playlist(playlist_id: str) -> dict | None:
    with get_db() as conn:
        p = conn.execute(
            "SELECT * FROM playlists WHERE id=?", (playlist_id,)
        ).fetchone()
        if not p:
            return None
        tracks = conn.execute(
            "SELECT * FROM playlist_tracks WHERE playlist_id=? ORDER BY position",
            (playlist_id,)
        ).fetchall()
        result = dict(p)
        result["tracks"] = [dict(t) for t in tracks]
        return result


def create_playlist(name: str, tracks: list[dict]) -> dict:
    """tracks: [{path, title}]"""
    pid = secrets.token_hex(8)
    with get_db() as conn:
        conn.execute(
            "INSERT INTO playlists (id, name) VALUES (?,?)", (pid, name)
        )
        for i, track in enumerate(tracks):
            tid = secrets.token_hex(8)
            conn.execute(
                "INSERT INTO playlist_tracks (id, playlist_id, path, position, title) VALUES (?,?,?,?,?)",
                (tid, pid, track["path"], i, track.get("title", track["path"].split("/")[-1]))
            )
    return get_playlist(pid)


def update_playlist(playlist_id: str, name: str = None, tracks: list[dict] = None) -> dict | None:
    with get_db() as conn:
        if name:
            conn.execute(
                "UPDATE playlists SET name=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (name, playlist_id)
            )
        if tracks is not None:
            conn.execute("DELETE FROM playlist_tracks WHERE playlist_id=?", (playlist_id,))
            for i, track in enumerate(tracks):
                tid = secrets.token_hex(8)
                conn.execute(
                    "INSERT INTO playlist_tracks (id, playlist_id, path, position, title) VALUES (?,?,?,?,?)",
                    (tid, playlist_id, track["path"], i, track.get("title", track["path"].split("/")[-1]))
                )
            conn.execute(
                "UPDATE playlists SET updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (playlist_id,)
            )
    return get_playlist(playlist_id)


def delete_playlist(playlist_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM playlists WHERE id=?", (playlist_id,))
