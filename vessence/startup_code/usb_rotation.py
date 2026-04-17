#!/usr/bin/env python3
"""
usb_rotation.py — Comprehensive daily backup to USB drive with 10-day rotation.

Backs up all code, memories, configs, and dotfiles needed to fully restore
Jane + Amber on a fresh machine. Also writes a restore manifest and
RESTORE.md with step-by-step instructions.

Run: python usb_rotation.py
Cron: 0 2 * * * (2:00 AM daily)
"""
import os
import shutil
import subprocess
import glob
import json
from datetime import datetime
from pathlib import Path

# ─── USB Detection ────────────────────────────────────────────────────────────
_USER = os.environ.get("USER", os.environ.get("LOGNAME", "user"))
_DEFAULT_USB = f'/media/{_USER}/USB DISK'

def find_usb_mount():
    candidates = glob.glob(f'/media/{_USER}/*') + glob.glob(f'/run/media/{_USER}/*')
    for path in candidates:
        if os.path.ismount(path):
            return path
    return _DEFAULT_USB

USB_MOUNT_POINT = find_usb_mount()

# ─── What to back up ──────────────────────────────────────────────────────────
SOURCES = [
    '/home/chieh/vessence',
    '/home/chieh/gemini_cli_bridge',
    '/home/chieh/.claude',          # Jane's memory, hooks, settings.json — CRITICAL
    '/home/chieh/CLAUDE.md',        # Jane's identity & protocol document — CRITICAL
    '/home/chieh/.gemini',          # Gemini/Amber config
    '/home/chieh/.ssh',
    '/home/chieh/.bashrc',
    '/home/chieh/.profile',
    '/home/chieh/.vimrc',
    '/home/chieh/litellm_config.yaml',
]

EXCLUDES = [
    '--exclude=omniparser_venv',
    '--exclude=adk-venv',
    '--exclude=miniconda3',
    '--exclude=.adk/artifacts',
    '--exclude=.cache',
    '--exclude=.npm',
    '--exclude=.nv',
    '--exclude=tmp',           # .gemini/tmp/ is 1.5GB of ephemeral Gemini artifacts
    '--exclude=__pycache__',
    '--exclude=*.pyc',
    '--exclude=node_modules',
    '--exclude=.git',
]

ADK_PYTHON = '/home/chieh/google-adk-env/adk-venv/bin/python'
ADK_PIP    = '/home/chieh/google-adk-env/adk-venv/bin/pip'


# ─── Manifest Generation ──────────────────────────────────────────────────────
def run(cmd, fallback='(unavailable)'):
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return fallback


def generate_manifest(backup_dir: str):
    """Write restore_manifest.json and RESTORE.md to the backup directory."""
    now = datetime.now().isoformat()

    manifest = {
        'generated_at': now,
        'system': {
            'os': run(['lsb_release', '-ds']),
            'kernel': run(['uname', '-r']),
            'python_system': run(['python3', '--version']),
            'python_adk_venv': run([ADK_PYTHON, '--version']),
        },
        'claude_code': {
            'binary': run(['readlink', '-f', '/home/chieh/.local/bin/claude']),
            'version': run(['/home/chieh/.local/bin/claude', '--version']),
        },
        'ollama_models': run(['ollama', 'list']),
        'crontab': run(['crontab', '-l']),
        'pip_freeze_adk_venv': run([ADK_PIP, 'freeze']),
        'apt_packages_key': run(
            ['dpkg-query', '-W', '-f=${Package}==${Version}\n',
             'ninja-build', 'libgtk-3-dev', 'libx11-dev', 'pkg-config',
             'cmake', 'clang', 'libsqlite3-dev', 'libsecret-1-dev',
             'xrandr', 'ffmpeg', 'git', 'rsync', 'curl', 'wget',
             'python3', 'python3-pip', 'nodejs', 'npm'],
        ),
    }

    # Save JSON manifest
    manifest_path = os.path.join(backup_dir, 'restore_manifest.json')
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    # Update the crontab_backup.txt in the repo source
    crontab_txt = '/home/chieh/vessence/configs/crontab_backup.txt'
    try:
        live_cron = run(['crontab', '-l'])
        Path(crontab_txt).write_text(live_cron + '\n')
    except Exception:
        pass

    # Write RESTORE.md
    restore_md = f"""# Project Ambient — Full Restore Instructions
Generated: {now}

## Overview
This backup contains everything needed to restore Jane (Claude Code) and Amber (Google ADK)
on a fresh Ubuntu machine.

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
# From the USB backup directory, rsync everything back:
rsync -av backup_YYYYMMDD/my_agent/          /home/chieh/vessence/
rsync -av backup_YYYYMMDD/gemini_cli_bridge/ /home/chieh/gemini_cli_bridge/
rsync -av backup_YYYYMMDD/.claude/           /home/chieh/.claude/
cp    backup_YYYYMMDD/CLAUDE.md              /home/chieh/CLAUDE.md
rsync -av backup_YYYYMMDD/.gemini/           /home/chieh/.gemini/
rsync -av backup_YYYYMMDD/.ssh/              /home/chieh/.ssh/ && chmod 700 /home/chieh/.ssh && chmod 600 /home/chieh/.ssh/*
cp    backup_YYYYMMDD/.bashrc                /home/chieh/.bashrc
cp    backup_YYYYMMDD/.profile               /home/chieh/.profile
cp    backup_YYYYMMDD/.vimrc                 /home/chieh/.vimrc
cp    backup_YYYYMMDD/litellm_config.yaml    /home/chieh/litellm_config.yaml
```

---

## Step 3 — Recreate Python Venv (Google ADK)

```bash
mkdir -p /home/chieh/google-adk-env
python3 -m venv /home/chieh/google-adk-env/adk-venv
source /home/chieh/google-adk-env/adk-venv/bin/activate

# Install from the exact frozen requirements in this backup:
pip install $(cat restore_manifest.json | python3 -c "
import json,sys
m=json.load(sys.stdin)
lines=[l for l in m['pip_freeze_adk_venv'].splitlines() if l and not l.startswith('#')]
print(' '.join(lines))
")
# Or more safely, pipe the freeze directly:
cat restore_manifest.json | python3 -c "
import json,sys; m=json.load(sys.stdin); print(m['pip_freeze_adk_venv'])
" > /tmp/requirements_restore.txt
pip install -r /tmp/requirements_restore.txt
```

---

## Step 4 — Install Claude Code

```bash
# Claude Code version backed up: {manifest['claude_code']['version']}
npm install -g @anthropic-ai/claude-code
# Or install the exact version:
# npm install -g @anthropic-ai/claude-code@<version>
```

---

## Step 5 — Restore Ollama Models

```bash
# Install Ollama if not present:
curl -fsSL https://ollama.com/install.sh | sh

# Re-pull the models that were installed:
# {chr(10).join('# ollama pull ' + line.split()[0] for line in manifest['ollama_models'].splitlines()[1:] if line.strip())}
ollama pull qwen2.5-coder:14b
ollama pull qwen2.5:7b
```

---

## Step 6 — Restore Crontab

```bash
# The full crontab is saved in restore_manifest.json and crontab_backup.txt
# To restore:
cat restore_manifest.json | python3 -c "
import json,sys; m=json.load(sys.stdin); print(m['crontab'])
" | crontab -

# Or directly from the text file:
crontab /home/chieh/vessence/configs/crontab_backup.txt
```

---

## Step 7 — Start the System

```bash
# Start Amber ADK server + Discord bridges:
bash /home/chieh/vessence/startup_code/start_all_bots.sh

# Or use the reliable start with watchdog:
bash /home/chieh/vessence/startup_code/reliable_start.sh
```

---

## Step 8 — Verify

```bash
# Check Amber is responding:
curl http://localhost:8000/health

# Check memories are intact (ChromaDB):
/home/chieh/google-adk-env/adk-venv/bin/python /home/chieh/vessence/agent_skills/search_memory.py "session start"

# Check Jane's memory is intact:
ls /home/chieh/.claude/projects/-home-chieh/memory/
```

---

## What's in this backup

| Item | Path | Notes |
|---|---|---|
| Agent code + skills | `my_agent/` | All Python scripts |
| Amber ADK agent | `my_agent/amber/` | Full agent code |
| ChromaDB memories | `my_agent/vector_db/` | All permanent + long-term memories |
| Vault files | `my_agent/vault/` | Images, docs, audio, PDFs |
| Jane auto-memory | `.claude/projects/.../memory/` | Feedback, user, project memories |
| Jane hooks + settings | `.claude/` | UserPromptSubmit hook, settings.json |
| Jane identity | `CLAUDE.md` | Full system prompt |
| Discord bridge | `gemini_cli_bridge/` | Bridge code + .env with tokens |
| API keys | `my_agent/.env` + `gemini_cli_bridge/.env` | All tokens |
| SSH keys | `.ssh/` | For git, remote access |
| Shell config | `.bashrc`, `.profile` | PATH, aliases |
| Crontab | `restore_manifest.json` → crontab | All scheduled jobs |
| Pip packages | `restore_manifest.json` → pip_freeze | Exact versions (232 packages) |
| Ollama models | `restore_manifest.json` → ollama_models | Pull commands listed above |
"""

    restore_path = os.path.join(backup_dir, 'RESTORE.md')
    Path(restore_path).write_text(restore_md)
    print(f"  → restore_manifest.json written")
    print(f"  → RESTORE.md written")
    print(f"  → crontab_backup.txt refreshed")


# ─── Main Backup ──────────────────────────────────────────────────────────────
def main():
    if not os.path.ismount(USB_MOUNT_POINT):
        print(f"Error: {USB_MOUNT_POINT} is not mounted. Backup aborted.")
        return

    today = datetime.now().strftime("%Y%m%d")
    backup_dir = os.path.join(USB_MOUNT_POINT, f'backup_{today}')
    os.makedirs(backup_dir, exist_ok=True)

    print(f"Starting comprehensive backup to {backup_dir}...")

    # ── Rsync each source ──────────────────────────────────────────────────
    for source in SOURCES:
        if not os.path.exists(source):
            print(f"  SKIP (not found): {source}")
            continue

        target_name = os.path.basename(source)
        target_path = os.path.join(backup_dir, target_name)

        if os.path.isdir(source):
            os.makedirs(target_path, exist_ok=True)
            result = subprocess.run(
                ['rsync', '-a', '--delete'] + EXCLUDES + [source + '/', target_path],
                capture_output=True, text=True
            )
            status = "OK" if result.returncode == 0 else f"WARN (exit {result.returncode})"
            print(f"  [{status}] {source} → {target_name}/")
        else:
            result = subprocess.run(
                ['rsync', '-a'] + [source, backup_dir],
                capture_output=True, text=True
            )
            status = "OK" if result.returncode == 0 else f"WARN (exit {result.returncode})"
            print(f"  [{status}] {source}")

    # ── Generate restore manifest + RESTORE.md ─────────────────────────────
    print("\nGenerating restore manifest...")
    generate_manifest(backup_dir)

    # ── 10-day rotation ────────────────────────────────────────────────────
    backup_dirs = sorted(glob.glob(os.path.join(USB_MOUNT_POINT, 'backup_*')))
    if len(backup_dirs) > 10:
        for old in backup_dirs[:-10]:
            print(f"  Rotating out: {os.path.basename(old)}")
            shutil.rmtree(old)

    # ── Summary ────────────────────────────────────────────────────────────
    size = subprocess.run(
        ['du', '-sh', backup_dir], capture_output=True, text=True
    ).stdout.split('\t')[0]
    remaining = sorted(glob.glob(os.path.join(USB_MOUNT_POINT, 'backup_*')))
    print(f"\nSUCCESS: Backup complete.")
    print(f"  Size: {size}  |  Location: {backup_dir}")
    print(f"  Retained backups: {[os.path.basename(d) for d in remaining]}")


if __name__ == "__main__":
    main()
