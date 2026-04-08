#!/usr/bin/env python3
import os
import subprocess
import datetime
import logging
import ollama
import sys
from pathlib import Path

# Configuration
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jane.config import LOGS_DIR, VESSENCE_HOME

REPO_DIR = VESSENCE_HOME
LOG_FILE = os.path.join(LOGS_DIR, 'backup_service.log')
REMOTE_NAME = "backup"
from jane.llm_config import LOCAL_LLM_MODEL as MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("GitBackup")

def run_cmd(cmd_list, cwd=REPO_DIR):
    if isinstance(cmd_list, str):
        cmd_list = cmd_list.split()
    result = subprocess.run(cmd_list, shell=False, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        logger.error(f"Command failed: {cmd_list}\nError: {result.stderr}")
        return None
    return result.stdout.strip()

def get_commit_summary(diff):
    if not diff:
        return "Regular automated backup"
    
    # Cap the diff to avoid token limits if any
    capped_diff = diff[:4000]
    
    prompt = (
        f"You are a code summary expert. Summarize the following git changes concisely for a commit message. "
        f"Keep it under 80 characters.\n\nChanges:\n{capped_diff}"
    )
    
    try:
        response = ollama.chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a concise git commit message generator."},
                {"role": "user", "content": prompt}
            ]
        )
        summary = response['message']['content'].strip().strip('"').strip("'")
        # Ensure it's on one line
        summary = summary.replace('\n', ' ')
        return summary
    except Exception as e:
        logger.warning(f"Failed to get summary from Qwen: {e}")
        return f"Automated backup: {datetime.datetime.now().isoformat()}"

def main():
    logger.info("Starting automated git backup.")
    
    if not os.path.isdir(os.path.join(REPO_DIR, ".git")):
        logger.error(f"{REPO_DIR} is not a git repository.")
        return

    # Add all changes
    run_cmd(["git", "add", "."])

    # Check if there are staged changes
    status = run_cmd(["git", "status", "--porcelain"])
    if not status:
        logger.info("No changes to backup.")
        return

    # Get diff for summary
    diff = run_cmd(["git", "diff", "--cached"])
    
    # Get Qwen summary
    summary = get_commit_summary(diff)
    logger.info(f"Generated commit summary: {summary}")
    
    # Commit — use list form to prevent shell injection from LLM-generated summary
    commit_res = subprocess.run(
        ["git", "commit", "-m", summary],
        cwd=REPO_DIR, capture_output=True, text=True
    )
    if commit_res.returncode != 0:
        logger.error(f"Commit failed: {commit_res.stderr}")
        return
    logger.info("Commit successful.")
    
    # Push
    # Find current branch
    branch = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if not branch:
        branch = "master"

    logger.info(f"Pushing to {REMOTE_NAME} branch {branch}...")
    push_res = run_cmd(["git", "push", REMOTE_NAME, branch])
    if push_res is None:
        logger.error("!!! ALERT: Git push failed. Backup not synced to peer.")
        # Optional: send alert if push fails (already logged as ERROR)
        return
    
    logger.info("Backup successfully pushed to peer.")

if __name__ == "__main__":
    main()
