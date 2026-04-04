#!/bin/bash
# backup_all.sh - Creates a portable backup of the entire AI Agent system
set -e

BACKUP_NAME="amber_jane_backup_$(date +%Y%m%d_%H%M%S).tar.gz"
BACKUP_DIR="/home/chieh/backups"
mkdir -p $BACKUP_DIR

echo "-------------------------------------------------------"
echo "📦 CREATING PORTABLE BACKUP: $BACKUP_NAME"
echo "-------------------------------------------------------"

# 1. Refresh snapshots just in case
echo "[1/3] Refreshing environment snapshots..."
source /home/chieh/google-adk-env/adk-venv/bin/activate && pip freeze > /home/chieh/vessence/configs/requirements_adk.txt && deactivate
source /home/chieh/vessence/omniparser_venv/bin/activate && pip freeze > /home/chieh/vessence/configs/requirements_omniparser.txt && deactivate
/home/chieh/miniconda3/bin/conda env export -n kokoro > /home/chieh/vessence/configs/kokoro_env.yml 2>/dev/null || echo "Note: Conda export skipped."

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
    /home/chieh/vessence \
    /home/chieh/vector_db \
    /home/chieh/vault \
    /home/chieh/gemini_cli_bridge \
    /home/chieh/.env \
    /home/chieh/.gitignore \
    /home/chieh/.bashrc

echo "[3/3] Finalizing..."
echo "-------------------------------------------------------"
echo "✅ BACKUP SUCCESSFUL!"
echo "Location: $BACKUP_DIR/$BACKUP_NAME"
echo "Size: $(du -h $BACKUP_DIR/$BACKUP_NAME | cut -f1)"
echo "-------------------------------------------------------"
echo "Move this file to your external hard drive."
echo "To restore, just extract it to /home/chieh/ and follow README.md."
echo "-------------------------------------------------------"
