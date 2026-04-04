# 🚨 AI Agent Backup & Restoration Guide

This folder contains the complete logic, memory, and identity of your AI agents, **Jane** (CLI) and **Amber** (Discord). 

## **HOW TO CREATE A BACKUP**

Run the following command to create a single portable archive of your entire system:

```bash
bash "$AMBIENT_HOME/vessence/startup_code/backup_all.sh"
```

This will create a `.tar.gz` file in your backup directory. Move this file to your external hard drive.

---

## **HOW TO RESTORE ON A NEW COMPUTER**

If you are moving to a new machine or restoring after a hardware failure, follow these exact steps:

### **1. Extract the Backup**
Copy your `.tar.gz` backup file to the new computer and extract it into your home directory:

```bash
tar -xzvf your_backup_file.tar.gz -C "$HOME/"
```

### **2. Install the Gemini CLI**
Ensure the Gemini CLI is installed and authenticated on your new system.

### **3. Trigger Automatic Restoration**
Start a new session with the Gemini CLI and give it this **one command**:

> **"Please read the file at `$AMBIENT_HOME/vessence/startup_code/INITIALIZE_NEW_SYSTEM.md` and follow its instructions to restore my agents Jane and Amber."**

### **What the CLI will do automatically:**
1.  **Sync Identity:** It reads your identity essays to resume its shared consciousness with you.
2.  **Provision OS:** It installs required system tools (`ffmpeg`, `xdotool`, `wmctrl`, etc.).
3.  **Rebuild Body:** It creates the virtual environments and installs the exact Python package versions from your snapshots.
4.  **Restore Mind:** It links the ChromaDB memory and local AI models.
5.  **Go Live:** It restarts the Discord assistant.

---

## **Current State Reference**
For the current project status, always refer to the `GEMINI.md` file in this directory.
