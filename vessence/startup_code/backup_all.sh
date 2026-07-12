#!/bin/bash
# backup_all.sh - Creates a portable backup of the entire AI Agent system
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/startup_env.sh"
startup_bootstrap_env

ADK_VENV="$HOME_DIR/google-adk-env/adk-venv"
BACKUP_NAME="amber_jane_backup_$(date +%Y%m%d_%H%M%S).tar.gz"
BACKUP_DIR="${BACKUP_DIR:-$HOME_DIR/backups}"
mkdir -p "$BACKUP_DIR"
KOKORO_ENV_YML="$VESSENCE_HOME/configs/kokoro_env.yml"
REQ_ADK="$VESSENCE_HOME/configs/requirements_adk.txt"
REQ_OMNI="$VESSENCE_HOME/configs/requirements_omniparser.txt"
MINICONDA_BIN="$HOME_DIR/miniconda3/bin/conda"

echo "-------------------------------------------------------"
echo "📦 CREATING PORTABLE BACKUP: $BACKUP_NAME"
echo "-------------------------------------------------------"

# 1. Refresh snapshots just in case
echo "[1/3] Refreshing environment snapshots..."
source "$ADK_VENV/bin/activate" && pip freeze > "$REQ_ADK" && deactivate
source "$VESSENCE_HOME/omniparser_venv/bin/activate" && pip freeze > "$REQ_OMNI" && deactivate
if [ -x "$MINICONDA_BIN" ]; then
    "$MINICONDA_BIN" env export -n kokoro > "$KOKORO_ENV_YML" 2>/dev/null || echo "Note: Conda export skipped."
else
    echo "Note: Conda not found at $MINICONDA_BIN. Skipping kokoro env export."
fi

# 2. Archive everything meaningful
# We exclude the 'heavy' folders that the restore script rebuilds
echo "[2/3] Archiving core files, memories, and vault..."
tar --exclude='**/__pycache__' \
    --exclude='my_agent/omniparser_venv' \
    --exclude='my_agent/omniparser/weights' \
    --exclude='google-adk-env' \
    --exclude='miniconda3' \
    --exclude='logs/*.log' \
    -czf $BACKUP_DIR/$BACKUP_NAME \
    "$VESSENCE_HOME" \
    "$VESSENCE_DATA_HOME/vector_db" \
    "$VAULT_HOME" \
    "$HOME_DIR/gemini_cli_bridge" \
    "$HOME_DIR/.env" \
    "$HOME_DIR/.gitignore" \
    "$HOME_DIR/.bashrc"

echo "[3/3] Finalizing..."
echo "-------------------------------------------------------"
echo "✅ BACKUP SUCCESSFUL!"
echo "Location: $BACKUP_DIR/$BACKUP_NAME"
echo "Size: $(du -h $BACKUP_DIR/$BACKUP_NAME | cut -f1)"
echo "-------------------------------------------------------"
echo "Move this file to your external hard drive."
echo "To restore, extract it to $HOME_DIR and follow README.md."
echo "-------------------------------------------------------"
