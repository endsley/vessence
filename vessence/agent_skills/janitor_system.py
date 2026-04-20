#!/usr/bin/env python3
import os
import time
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jane.config import LOGS_DIR, VAULT_DIR, VESSENCE_DATA_HOME

# Paths to clean
TEMP_FILES = [
    "/tmp/current_screen.png",
    os.path.join(VAULT_DIR, 'tmp_screenshot.png'),
    os.path.join(VESSENCE_DATA_HOME, 'test_kokoro.wav'),
]
MAX_LOG_SIZE_MB = 50
LOG_RETENTION_DAYS = 2
LOG_PATTERNS = ("*.log", "*.jsonl")

TRANSCRIPT_RETENTION_DAYS = 7
CLAUDE_TRANSCRIPT_DIR = os.path.expanduser(
    "~/.claude/projects/-home-chieh-ambient-vessence"
)
SESSION_SUMMARY_DIR = os.path.join(
    VESSENCE_DATA_HOME, "data", "jane_session_summaries"
)

def clean_temp_files():
    for f in TEMP_FILES:
        if os.path.exists(f):
            try:
                os.remove(f)
                print(f"Removed temp file: {f}")
            except Exception as e:
                print(f"Failed to remove {f}: {e}")

def rotate_logs():
    log_files = []
    for pattern in LOG_PATTERNS:
        log_files.extend(glob.glob(os.path.join(LOGS_DIR, "**", pattern), recursive=True))
    for log_f in log_files:
        if os.path.getsize(log_f) > (MAX_LOG_SIZE_MB * 1024 * 1024):
            try:
                # Simple rotation: just clear if too big, or could implement proper rotation
                with open(log_f, 'w') as f:
                    f.write(f"--- Log rotated at {time.ctime()} ---\n")
                print(f"Rotated large log: {log_f}")
            except Exception as e:
                print(f"Failed to rotate {log_f}: {e}")

def prune_old_logs():
    cutoff_ts = time.time() - (LOG_RETENTION_DAYS * 24 * 60 * 60)
    removed = 0
    truncated = 0
    for pattern in LOG_PATTERNS:
        for path in Path(LOGS_DIR).rglob(pattern):
            if not path.is_file():
                continue
            try:
                if path.stat().st_mtime < cutoff_ts:
                    # Stale file — delete entirely
                    path.unlink()
                    removed += 1
                    print(f"Removed old log: {path}")
                elif path.stat().st_size > 1024 * 1024:
                    # Active but large (>1MB) — keep only last 200KB
                    _truncate_log_tail(path, keep_bytes=200 * 1024)
                    truncated += 1
            except Exception as e:
                print(f"Failed to process log {path}: {e}")
    print(f"Log cleanup: removed {removed} stale, truncated {truncated} large (retention={LOG_RETENTION_DAYS}d).")


def _truncate_log_tail(path: Path, keep_bytes: int = 200 * 1024):
    """Keep only the last N bytes of a log file."""
    try:
        size = path.stat().st_size
        if size <= keep_bytes:
            return
        with open(path, 'rb') as f:
            f.seek(size - keep_bytes)
            tail = f.read()
        # Find first newline to avoid partial line
        nl = tail.find(b'\n')
        if nl != -1:
            tail = tail[nl + 1:]
        with open(path, 'wb') as f:
            f.write(f"--- Truncated at {time.ctime()} (kept last {keep_bytes // 1024}KB) ---\n".encode())
            f.write(tail)
        print(f"Truncated active log: {path} ({size // 1024}KB → {len(tail) // 1024}KB)")
    except Exception as e:
        print(f"Failed to truncate {path}: {e}")

def prune_old_transcripts():
    """Delete raw Claude CLI transcripts and Jane session summaries older than
    TRANSCRIPT_RETENTION_DAYS. Durable conversation memory lives in ChromaDB;
    these files are per-session working state that grows unbounded otherwise.
    """
    cutoff_ts = time.time() - (TRANSCRIPT_RETENTION_DAYS * 24 * 60 * 60)
    for label, root, pattern in (
        ("claude transcripts", CLAUDE_TRANSCRIPT_DIR, "*.jsonl"),
        ("session summaries", SESSION_SUMMARY_DIR, "*.json"),
    ):
        if not os.path.isdir(root):
            continue
        removed = 0
        bytes_freed = 0
        for path in Path(root).glob(pattern):
            if not path.is_file():
                continue
            try:
                st = path.stat()
                if st.st_mtime < cutoff_ts:
                    bytes_freed += st.st_size
                    path.unlink()
                    removed += 1
            except Exception as e:
                print(f"Failed to remove {path}: {e}")
        print(
            f"{label}: removed {removed} files "
            f"({bytes_freed // 1024} KB freed, retention={TRANSCRIPT_RETENTION_DAYS}d)."
        )


def archive_completed_jobs():
    try:
        from agent_skills.job_queue_utils import archive_completed
        n = archive_completed()
        if n:
            print(f"Archived {n} completed jobs from queue.")
    except Exception as e:
        print(f"Job queue archiving failed: {e}")

if __name__ == "__main__":
    # Load gate: wait until CPU/memory is acceptable
    try:
        from agent_skills.system_load import wait_until_safe
        if not wait_until_safe(max_wait_minutes=10):
            print("System busy — skipping system janitor this cycle.")
            exit(0)
    except Exception:
        pass

    print("Starting System Janitor...")
    clean_temp_files()
    rotate_logs()
    prune_old_logs()
    prune_old_transcripts()
    archive_completed_jobs()
    print("System Janitor finished.")
