#!/usr/bin/env python3
"""
usb_sync.py — Incremental USB backup using rsync + hard-link snapshots.

Replaces usb_rotation.py. Instead of creating a new full-copy directory every
day, we maintain one persistent `current/` mirror on the USB. rsync only
transfers changed files. Weekly hard-link snapshots give point-in-time history
at near-zero extra space.

Cron: 0 2 * * * (2:00 AM daily)
Run manually: python usb_sync.py [--dry-run]
"""
import os
import sys
import glob
import json
import shutil
import subprocess
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# ─── Config ───────────────────────────────────────────────────────────────────

HOME = str(Path.home())
AMBIENT_BASE = os.environ.get("AMBIENT_BASE", os.path.join(HOME, "ambient"))
VESSENCE_HOME = os.environ.get("VESSENCE_HOME", os.path.join(AMBIENT_BASE, "vessence"))
VESSENCE_DATA_HOME = os.environ.get("VESSENCE_DATA_HOME", os.path.join(AMBIENT_BASE, "vessence-data"))
VAULT_HOME = os.environ.get("VAULT_HOME", os.path.join(AMBIENT_BASE, "vault"))

SOURCES = [
    {"source": VESSENCE_HOME, "target": "ambient/vessence"},
    {"source": VESSENCE_DATA_HOME, "target": "ambient/vessence-data"},
    {"source": VAULT_HOME, "target": "ambient/vault"},
    {"source": f"{HOME}/gemini_cli_bridge", "target": "system/gemini_cli_bridge"},
    {"source": f"{HOME}/.claude", "target": "system/.claude"},
    {"source": f"{HOME}/CLAUDE.md", "target": "system/CLAUDE.md"},
    {"source": f"{HOME}/.gemini", "target": "system/.gemini"},
    {"source": f"{HOME}/.ssh", "target": "system/.ssh"},
    {"source": f"{HOME}/.bashrc", "target": "system/.bashrc"},
    {"source": f"{HOME}/.profile", "target": "system/.profile"},
    {"source": f"{HOME}/.vimrc", "target": "system/.vimrc"},
]

EXCLUDES = [
    '--exclude=omniparser_venv',
    '--exclude=venv',
    '--exclude=adk-venv',
    '--exclude=miniconda3',
    '--exclude=.adk/artifacts',
    '--exclude=.cache',
    '--exclude=.npm',
    '--exclude=.nv',
    '--exclude=tmp',
    '--exclude=__pycache__',
    '--exclude=*.pyc',
    '--exclude=node_modules',
    '--exclude=.git',
]

SNAPSHOT_INTERVAL_DAYS = 7
SNAPSHOT_RETENTION_DAYS = 30
STALE_TOP_LEVEL_ENTRIES = [
    'vessence',
    'gemini_cli_bridge',
    '.claude',
    'CLAUDE.md',
    '.gemini',
    '.ssh',
    '.bashrc',
    '.profile',
    '.vimrc',
    'litellm_config.yaml',
]

ADK_PYTHON = os.path.join(HOME, 'google-adk-env', 'adk-venv', 'bin', 'python')
ADK_PIP    = os.path.join(HOME, 'google-adk-env', 'adk-venv', 'bin', 'pip')

# ─── USB Detection ────────────────────────────────────────────────────────────

def find_usb_mount() -> str | None:
    user = os.path.basename(HOME)
    candidates = glob.glob(f'/media/{user}/*') + glob.glob(f'/run/media/{user}/*')
    for path in sorted(candidates):
        if os.path.ismount(path):
            return path
    return None


# ─── Rsync ────────────────────────────────────────────────────────────────────

def rsync_source(source: str, target_rel: str, current_dir: str, dry_run: bool) -> dict:
    """Rsync one source into current_dir. Returns {added, updated, deleted, errors}."""
    if not os.path.exists(source):
        return {'skipped': True, 'reason': 'source not found'}

    target = os.path.join(current_dir, target_rel)

    if os.path.isdir(source):
        os.makedirs(target, exist_ok=True)
        cmd = ['rsync', '-a', '--delete', '--itemize-changes'] + EXCLUDES
        if dry_run:
            cmd.append('--dry-run')
        cmd += [source + '/', target]
    else:
        # Single file
        cmd = ['rsync', '-a', '--itemize-changes']
        if dry_run:
            cmd.append('--dry-run')
        os.makedirs(os.path.dirname(target), exist_ok=True)
        cmd += [source, target]

    result = subprocess.run(cmd, capture_output=True, text=True)

    stats = {'added': 0, 'updated': 0, 'deleted': 0}
    for line in result.stdout.splitlines():
        if not line or line.startswith('sending') or line.startswith('sent'):
            continue
        action = line[:11] if len(line) > 11 else line
        if action.startswith('>f+'):
            stats['added'] += 1
        elif action.startswith('>f.') or action.startswith('>f'):
            stats['updated'] += 1
        elif action.startswith('*deleting'):
            stats['deleted'] += 1

    if result.returncode not in (0, 24):  # 24 = partial transfer (vanished files), acceptable
        stats['error'] = result.stderr[:200]

    return stats


# ─── Hard-link Snapshot ───────────────────────────────────────────────────────

def should_take_snapshot(snapshots_dir: str) -> bool:
    """True if no snapshot exists or last snapshot is >SNAPSHOT_INTERVAL_DAYS old."""
    existing = sorted(glob.glob(os.path.join(snapshots_dir, '????-??-??')))
    if not existing:
        return True
    last = existing[-1]
    last_date_str = os.path.basename(last)
    try:
        last_date = datetime.strptime(last_date_str, '%Y-%m-%d').date()
        return (datetime.now().date() - last_date).days >= SNAPSHOT_INTERVAL_DAYS
    except ValueError:
        return True


def take_snapshot(current_dir: str, snapshots_dir: str, today: str, dry_run: bool) -> str:
    """Create a hard-link snapshot of current/ → snapshots/YYYY-MM-DD/."""
    snapshot_path = os.path.join(snapshots_dir, today)
    if os.path.exists(snapshot_path):
        print(f"  Snapshot {today} already exists, skipping.")
        return snapshot_path
    if dry_run:
        print(f"  [dry-run] Would create snapshot: {snapshot_path}")
        return snapshot_path
    os.makedirs(snapshots_dir, exist_ok=True)
    result = subprocess.run(['cp', '-al', current_dir, snapshot_path], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  Snapshot created: {snapshot_path}")
    else:
        print(f"  Snapshot FAILED: {result.stderr[:100]}")
    return snapshot_path


def rotate_snapshots(snapshots_dir: str, dry_run: bool):
    """Delete snapshots older than SNAPSHOT_RETENTION_DAYS."""
    cutoff = datetime.now().date() - timedelta(days=SNAPSHOT_RETENTION_DAYS)
    existing = sorted(glob.glob(os.path.join(snapshots_dir, '????-??-??')))
    for snap in existing:
        name = os.path.basename(snap)
        try:
            snap_date = datetime.strptime(name, '%Y-%m-%d').date()
            if snap_date < cutoff:
                if dry_run:
                    print(f"  [dry-run] Would remove old snapshot: {name}")
                else:
                    shutil.rmtree(snap)
                    print(f"  Removed old snapshot: {name}")
        except ValueError:
            pass


def remove_stale_layout_entries(current_dir: str, dry_run: bool):
    """Remove old top-level entries from the pre-ambient backup layout."""
    for name in STALE_TOP_LEVEL_ENTRIES:
        path = os.path.join(current_dir, name)
        if not os.path.lexists(path):
            continue
        if dry_run:
            print(f"  [dry-run] Would remove stale entry: {name}")
            continue
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        print(f"  Removed stale entry: {name}")


# ─── Manifest ─────────────────────────────────────────────────────────────────

def run(cmd, fallback='(unavailable)'):
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return fallback


def write_restore_docs(usb_root: str, sync_state: dict):
    now = datetime.now().isoformat()

    manifest = {
        'generated_at': now,
        'system': {
            'os': run(['lsb_release', '-ds']),
            'kernel': run(['uname', '-r']),
            'python_adk_venv': run([ADK_PYTHON, '--version']),
        },
        'claude_code': {
            'version': run([os.path.join(HOME, '.local', 'bin', 'claude'), '--version']),
        },
        'ollama_models': run(['ollama', 'list']),
        'crontab': run(['crontab', '-l']),
        'pip_freeze_adk_venv': run([ADK_PIP, 'freeze']),
        'sync_state': sync_state,
    }

    manifest_path = os.path.join(usb_root, 'restore_manifest.json')
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    # Update crontab_backup.txt
    crontab_txt = os.path.join(VESSENCE_HOME, 'configs', 'crontab_backup.txt')
    try:
        Path(crontab_txt).write_text(manifest['crontab'] + '\n')
    except Exception:
        pass

    restore_md = f"""# Project Ambient — Full Restore Instructions
Generated: {now}

## Overview
Restore Jane and Amber from this USB backup.
The `current/` directory is a complete, up-to-date mirror of all sources.

---

## Step 1 — System Prerequisites
```bash
sudo apt-get update && sudo apt-get install -y \\
    git rsync curl wget python3 python3-pip \\
    ninja-build libgtk-3-dev libx11-dev pkg-config cmake clang \\
    libsqlite3-dev libsecret-1-dev xrandr ffmpeg nodejs npm
```

---

## Step 2 — Restore Files
```bash
USB=<your usb mount point>
mkdir -p $HOME/ambient
rsync -av $USB/current/ambient/vessence/      $HOME/ambient/vessence/
rsync -av $USB/current/ambient/vessence-data/ $HOME/ambient/vessence-data/
rsync -av $USB/current/ambient/vault/         $HOME/ambient/vault/
rsync -av $USB/current/system/gemini_cli_bridge/ $HOME/gemini_cli_bridge/
rsync -av $USB/current/system/.claude/           $HOME/.claude/
rsync -av $USB/current/system/.gemini/           $HOME/.gemini/
rsync -av $USB/current/system/.ssh/              $HOME/.ssh/ && chmod 700 $HOME/.ssh && chmod 600 $HOME/.ssh/*
cp    $USB/current/system/CLAUDE.md             $HOME/CLAUDE.md
cp    $USB/current/system/.bashrc               $HOME/.bashrc
cp    $USB/current/system/.profile              $HOME/.profile
cp    $USB/current/system/.vimrc                $HOME/.vimrc
```

---

## Step 3 — Recreate Python Venv
```bash
mkdir -p $HOME/google-adk-env
python3 -m venv $HOME/google-adk-env/adk-venv
source $HOME/google-adk-env/adk-venv/bin/activate
cat restore_manifest.json | python3 -c "
import json,sys; m=json.load(sys.stdin); print(m['pip_freeze_adk_venv'])
" > /tmp/requirements_restore.txt
pip install -r /tmp/requirements_restore.txt
```

---

## Step 4 — Install Claude Code
```bash
npm install -g @anthropic-ai/claude-code
```

---

## Step 5 — Restore Ollama Models
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5-coder:14b
```

---

## Step 6 — Restore Crontab
```bash
crontab $HOME/ambient/vessence/configs/crontab_backup.txt
```

---

## Step 7 — Start the System
```bash
bash $HOME/ambient/vessence/startup_code/reliable_start.sh
```

---

## Available Snapshots
{chr(10).join('- ' + s for s in sync_state.get('snapshots', []))}
"""

    restore_path = os.path.join(usb_root, 'RESTORE.md')
    Path(restore_path).write_text(restore_md)
    print(f"  → restore_manifest.json and RESTORE.md written")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Incremental USB sync backup')
    parser.add_argument('--dry-run', action='store_true', help='Show what would change without doing it')
    args = parser.parse_args()

    usb = find_usb_mount()
    if not usb:
        print("Error: No USB drive mounted. Plug in USB and try again.")
        sys.exit(1)

    print(f"USB found: {usb}")
    if args.dry_run:
        print("DRY RUN — no files will be written\n")

    current_dir  = os.path.join(usb, 'current')
    snapshots_dir = os.path.join(usb, 'snapshots')
    state_path   = os.path.join(usb, 'sync_state.json')
    today        = datetime.now().strftime('%Y-%m-%d')

    os.makedirs(current_dir, exist_ok=True)

    # ── Sync all sources ──────────────────────────────────────────────────────
    print(f"\nSyncing to {current_dir} ...")
    total_added = total_updated = total_deleted = 0
    source_results = {}

    for item in SOURCES:
        source = item["source"]
        target_rel = item["target"]
        name = target_rel
        stats = rsync_source(source, target_rel, current_dir, args.dry_run)
        source_results[name] = stats
        if stats.get('skipped'):
            print(f"  SKIP  {name} ({stats['reason']})")
        else:
            a, u, d = stats.get('added', 0), stats.get('updated', 0), stats.get('deleted', 0)
            total_added   += a
            total_updated += u
            total_deleted += d
            status = 'ERROR' if 'error' in stats else 'OK'
            print(f"  [{status}] {name:30s}  +{a} ~{u} -{d}")
            if 'error' in stats:
                print(f"          {stats['error']}")

    print(f"\n  Total: +{total_added} added  ~{total_updated} updated  -{total_deleted} deleted")

    # ── Snapshot ─────────────────────────────────────────────────────────────
    print("\nChecking snapshot schedule...")
    snapshot_taken = False
    if should_take_snapshot(snapshots_dir):
        take_snapshot(current_dir, snapshots_dir, today, args.dry_run)
        snapshot_taken = True
    else:
        existing = sorted(glob.glob(os.path.join(snapshots_dir, '????-??-??')))
        last = os.path.basename(existing[-1]) if existing else 'none'
        print(f"  Last snapshot: {last} — next due in "
              f"{SNAPSHOT_INTERVAL_DAYS - (datetime.now().date() - datetime.strptime(last, '%Y-%m-%d').date()).days if last != 'none' else 0} day(s)")

    rotate_snapshots(snapshots_dir, args.dry_run)
    remove_stale_layout_entries(current_dir, args.dry_run)

    # ── State + restore docs ──────────────────────────────────────────────────
    snapshots_list = sorted(
        os.path.basename(s)
        for s in glob.glob(os.path.join(snapshots_dir, '????-??-??'))
    )
    sync_state = {
        'last_sync': datetime.now().isoformat(),
        'files_added': total_added,
        'files_updated': total_updated,
        'files_deleted': total_deleted,
        'snapshot_taken': snapshot_taken,
        'snapshots': snapshots_list,
    }

    if not args.dry_run:
        with open(state_path, 'w') as f:
            json.dump(sync_state, f, indent=2)
        print("\nWriting restore docs...")
        write_restore_docs(usb, sync_state)

    # ── Summary ───────────────────────────────────────────────────────────────
    size = subprocess.run(['du', '-sh', current_dir], capture_output=True, text=True).stdout.split('\t')[0]
    print(f"\nSUCCESS: Sync complete.")
    print(f"  current/ size: {size}")
    print(f"  Snapshots kept: {snapshots_list}")


if __name__ == '__main__':
    main()
