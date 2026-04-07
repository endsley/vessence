#!/usr/bin/env python3
import os
import subprocess
import sys
import shutil
from datetime import datetime

def get_mounted_drives():
    """Finds all mounted external drives and their available space."""
    drives = []
    username = os.getlogin()
    search_paths = [f'/media/{username}', '/mnt', f'/run/media/{username}']
    
    for base_path in search_paths:
        if not os.path.exists(base_path):
            continue
        try:
            for entry in os.listdir(base_path):
                mount_path = os.path.join(base_path, entry)
                if os.path.ismount(mount_path) and os.path.isdir(mount_path):
                    try:
                        usage = shutil.disk_usage(mount_path)
                        drives.append({
                            'name': entry,
                            'path': mount_path,
                            'free_gb': usage.free / (1024**3),
                            'total_gb': usage.total / (1024**3)
                        })
                    except OSError as e:
                        print(f"Warning: Could not get disk usage for '{mount_path}': {e}", file=sys.stderr)
        except OSError as e:
            print(f"Warning: Could not read directory '{base_path}': {e}", file=sys.stderr)
            
    return drives

def get_total_size(paths):
    """Calculates the total size of all files in a list of paths."""
    total_size_bytes = 0
    for p in paths:
        if not os.path.exists(p):
            print(f"Warning: Source path does not exist, skipping: {p}", file=sys.stderr)
            continue
        if os.path.isfile(p):
            total_size_bytes += os.path.getsize(p)
        elif os.path.isdir(p):
            for root, _, files in os.walk(p):
                for name in files:
                    try:
                        total_size_bytes += os.path.getsize(os.path.join(root, name))
                    except OSError as e:
                        print(f"Warning: Could not get size of file '{os.path.join(root, name)}': {e}", file=sys.stderr)
    return total_size_bytes

def main():
    """Main function to run the backup process."""
    source_paths = ['/home/chieh/vessence', '/home/chieh/gemini_cli_bridge']
    
    print("Calculating backup size...")
    total_size_bytes = get_total_size(source_paths)
    
    required_gb = (total_size_bytes / (1024**3)) * 1.1
    actual_data_gb = total_size_bytes / (1024**3)
    print(f"Total data to backup: ~{actual_data_gb:.2f} GB (Required space: ~{required_gb:.2f} GB)")

    drives = get_mounted_drives()

    if not drives:
        print("\n[!] No external USB drives detected.")
        print("Please plug in your USB drive, ensure it is mounted, and try again.")
        return

    valid_drives = [d for d in drives if d['free_gb'] > required_gb]

    if not valid_drives:
        print("\n[!] USB drive(s) found, but none have enough free space.")
        print(f"Required: {required_gb:.2f} GB")
        for d in drives:
            print(f" - {d['name']} ({d['path']}): {d['free_gb']:.2f} GB available")
        return

    if len(valid_drives) == 1:
        selected = valid_drives[0]
        print(f"\nOnly one valid drive found. Auto-selecting: {selected['name']} ({selected['path']})")
    else:
        print("\nAvailable USB Drives for Backup:")
        for i, d in enumerate(valid_drives):
            print(f"[{i+1}] {d['name']} ({d['path']}) - {d['free_gb']:.2f} GB free")

        try:
            choice_str = input("\nSelect a drive number to begin backup (or 0 to cancel): ")
            choice = int(choice_str)
            
            if choice == 0:
                print("Backup cancelled.")
                return
            if not (1 <= choice <= len(valid_drives)):
                raise IndexError("Choice out of range.")
                
            selected = valid_drives[choice - 1]
        except (ValueError, IndexError):
            print("Invalid selection. Exiting.")
            return
        except EOFError:
            print("\nNo input received (running in non-interactive mode?). Exiting.")
            return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"vessence_backup_{timestamp}.tar.gz"
    dest_path = os.path.join(selected['path'], backup_filename)

    print(f"\nStarting backup to: {dest_path}")
    print("This may take a few minutes. Please wait...")

    existing_source_paths = [p for p in source_paths if os.path.exists(p)]
    if not existing_source_paths:
        print("Error: None of the source directories exist. Nothing to back up.", file=sys.stderr)
        return

    _home = os.path.expanduser("~")
    source_dirs_relative = [os.path.relpath(p, _home) for p in existing_source_paths]

    try:
        cmd = ['tar', '-czvf', dest_path, '--exclude=my_agent/logs', '--exclude=my_agent/*.log', '-C', _home] + source_dirs_relative
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"\nSUCCESS! Backup completed: {dest_path}")
        print("You can now safely unmount the USB drive.")
    except subprocess.CalledProcessError as e:
        print(f"\nBACKUP FAILED (Exit Code: {e.returncode}):")
        print(f"Command: {' '.join(e.cmd)}")
        if e.stdout:
            print(f"Standard Output:\n{e.stdout}")
        if e.stderr:
            print(f"Error Output:\n{e.stderr}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
