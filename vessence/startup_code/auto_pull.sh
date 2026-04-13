#!/bin/bash
# auto_pull.sh — pull the latest vessence code from GitHub.
#
# Designed to run under cron. Safe to run by hand.
#
# Behavior:
#   - Fetches origin; if the tracking branch is ahead, fast-forward pulls.
#   - If requirements.txt changed → pip-install into the venv.
#   - If any code changed → graceful_restart.sh (falls back to systemctl).
#   - If the working tree is dirty, skips the pull and logs a warning so a
#     human can resolve it — never forces, never stashes.
#
# Log:  vessence-data/logs/auto_pull.log

set -u

AMBIENT_BASE="${AMBIENT_BASE:-$HOME/ambient}"
VENV_PY="$AMBIENT_BASE/venv/bin/python"
VENV_PIP="$AMBIENT_BASE/venv/bin/pip"
LOG_DIR="$AMBIENT_BASE/vessence-data/logs"
LOG_FILE="$LOG_DIR/auto_pull.log"

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

cd "$AMBIENT_BASE" || { log "ERROR: cannot cd to $AMBIENT_BASE"; exit 1; }

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    log "ERROR: $AMBIENT_BASE is not a git repo"
    exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
    log "SKIP: working tree has local changes — not pulling"
    exit 0
fi

if ! git fetch --quiet origin 2>>"$LOG_FILE"; then
    log "ERROR: git fetch failed"
    exit 1
fi

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse '@{u}' 2>/dev/null || echo "")

if [ -z "$REMOTE" ]; then
    log "ERROR: no upstream configured for current branch"
    exit 1
fi

if [ "$LOCAL" = "$REMOTE" ]; then
    log "up-to-date ($LOCAL)"
    exit 0
fi

CHANGED=$(git diff --name-only "$LOCAL" "$REMOTE")
log "pulling $(echo "$CHANGED" | wc -l) changed file(s) — $LOCAL → $REMOTE"

if ! git pull --ff-only --quiet 2>>"$LOG_FILE"; then
    log "ERROR: git pull --ff-only failed (non-fast-forward?) — leaving alone"
    exit 1
fi

# Re-install deps if requirements changed.
if echo "$CHANGED" | grep -qE '(^|/)requirements(-optional)?\.txt$'; then
    if [ -x "$VENV_PIP" ]; then
        log "requirements.txt changed — pip installing"
        "$VENV_PIP" install -r vessence/requirements.txt --quiet 2>>"$LOG_FILE"
    else
        log "WARN: venv pip not found at $VENV_PIP — skipping dep install"
    fi
fi

# Restart the service if any code under vessence/ changed. Markdown / config
# text edits don't need a restart.
if echo "$CHANGED" | grep -qE '^vessence/.*\.(py|html|css|js)$'; then
    GRACEFUL="$AMBIENT_BASE/vessence/startup_code/graceful_restart.sh"
    if [ -x "$GRACEFUL" ]; then
        log "code changed — running graceful_restart.sh"
        bash "$GRACEFUL" >>"$LOG_FILE" 2>&1 || log "WARN: graceful_restart exited non-zero"
    else
        log "code changed — systemctl restart (graceful_restart not available)"
        systemctl --user restart jane-web.service >>"$LOG_FILE" 2>&1 \
            || log "WARN: systemctl restart failed"
    fi
else
    log "non-code changes only — no restart needed"
fi

log "done"
