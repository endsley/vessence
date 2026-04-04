# USB Incremental Sync Backup — Spec

**Replaces:** `usb_rotation.py` (daily full-copy-into-new-folder approach)
**Goal:** Only transfer changed/new files each run. Keep a small number of cheap point-in-time snapshots.

---

## Problem with Current Approach

`usb_rotation.py` creates a new `backup_YYYYMMDD/` directory every day, then rsyncs all sources into it. Because the target dir is brand-new each time, rsync has nothing to compare against — it copies **everything** every run. With the vault now holding hundreds of files, this is slow and wears out the USB.

---

## New Layout on USB

```
USB/
  current/                  ← always up-to-date mirror of all sources
    ambient/
      vessence/
      vessence-data/
      vault/
    system/
      gemini_cli_bridge/
      .claude/
      CLAUDE.md
      .gemini/
      .ssh/
      .bashrc
      .profile
      .vimrc
  snapshots/
    2026-03-17/             ← hard-linked snapshot (files unchanged vs current = zero extra bytes)
    2026-03-10/
    ...
  RESTORE.md                ← always regenerated from latest run
  sync_state.json           ← last sync time, files changed, snapshot schedule
```

---

## Algorithm

### Every run (`usb_sync.py`):

1. **Find USB mount** — same detection logic as before (`/media/chieh/*`, `/run/media/chieh/*`)
2. **Rsync each source → `current/ambient/` or `current/system/`** with:
   - `--archive` (preserve permissions/timestamps)
   - `--delete` (remove files deleted from source)
   - default rsync diffing by size + mtime (skip unchanged files — this is the key)
   - `--exclude` patterns (omniparser_venv, __pycache__, node_modules, .git, etc.)
   - Capture `--itemize-changes` output to know what actually changed
3. **Report diff** — count files added/updated/deleted per source
4. **Snapshot decision** — if last snapshot was >7 days ago (or no snapshots exist):
   - Create `snapshots/YYYY-MM-DD/` using `cp -al current/ snapshots/YYYY-MM-DD/` (hard links — instant, near-zero space for unchanged files)
5. **Rotate snapshots** — delete snapshots older than 30 days
6. **Write `sync_state.json`** — timestamp, files changed count, snapshot list
7. **Regenerate `RESTORE.md`** and `restore_manifest.json` (same as before)

---

## Key Design Decisions

### Why not `--checksum`?
`--checksum` is more accurate but forces rsync to read every file on both sides, which is slow for a large vault and unnecessary for same-machine → USB backups.

The live implementation uses default rsync comparison (mtime + size), which already detects what should be added, replaced, or skipped when the destination mirror exists.

### Why hard-link snapshots?
`cp -al src/ dst/` creates a new directory where every file is a hard link to the same inode as `current/`. If a file hasn't changed since the last sync, the snapshot takes 0 extra bytes. If it has changed, the new version is in `current/` and the old version is in the snapshot — but only the actual delta exists on disk (the old inode is preserved by the snapshot, new inode written to current/).

This is exactly how macOS Time Machine and rsnapshot work.

### Snapshot frequency: weekly
Daily snapshots would accumulate quickly. Weekly snapshots kept for 30 days = ~4 snapshots at a time. Good balance of history vs. USB space.

### What happens on first run?
`current/` doesn't exist → rsync creates it and copies everything into the new mirror layout. Same as before, but only once ever.

### What happens on subsequent runs?
rsync diffs the live sources against the existing mirror under `current/ambient/` and `current/system/`. Only changed/new/deleted files are transferred. Typical incremental run: seconds, not minutes.

---

## Files

| File | Change |
|---|---|
| `startup_code/usb_sync.py` | **New** — replaces `usb_rotation.py` logic |
| `startup_code/usb_rotation.py` | **Kept** for reference, no longer used by cron |
| `configs/CRON_JOBS.md` | Update cron entry to call `usb_sync.py` |

---

## Cron Entry

```
0 2 * * * /home/chieh/google-adk-env/adk-venv/bin/python /home/chieh/ambient/vessence/startup_code/usb_sync.py >> /home/chieh/ambient/vessence-data/logs/System_log/usb_backup.log 2>&1
```

(Same time, same log, just new script.)

---

## Restore

Restore is simpler than before: just rsync from `USB/current/ambient/` and `USB/current/system/` back to the machine. The `RESTORE.md` on the USB explains this.
