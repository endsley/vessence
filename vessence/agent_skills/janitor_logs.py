import os
import gzip
import shutil
import logging
from logging.handlers import RotatingFileHandler
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jane.config import JANITOR_REPORT, LOGS_DIR

# Configuration
LOG_ROOT = LOGS_DIR
REPORT_PATH = JANITOR_REPORT
DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5MB
DEFAULT_BACKUP_COUNT = 5

# Setup internal logging for the janitor itself
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("janitor_logs")

def namer(name):
    """Appends .gz to the rotated file name."""
    return name + ".gz"

def rotator(source, dest):
    """Compresses the rotated log file using gzip."""
    logger.debug(f"Compressing {source} to {dest}")
    try:
        with open(source, 'rb') as f_in:
            with gzip.open(dest, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(source)
        logger.info(f"Successfully rotated and compressed: {dest}")
    except Exception as e:
        logger.error(f"Failed to rotate {source} to {dest}: {e}")

def get_rotating_logger(name, log_file, max_bytes=DEFAULT_MAX_BYTES, backup_count=DEFAULT_BACKUP_COUNT):
    """Returns a logger with a RotatingFileHandler configured with compression."""
    l = logging.getLogger(name)
    l.setLevel(logging.DEBUG)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
    handler.namer = namer
    handler.rotator = rotator
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    l.addHandler(handler)
    return l

def run_janitor():
    """
    Manually scans the LOG_ROOT for .log files that exceed DEFAULT_MAX_BYTES
    and rotates them if they are not currently being handled.
    """
    logger.info("Starting manual log rotation scan...")
    stats = {
        "timestamp": str(datetime.datetime.now()),
        "files_scanned": 0,
        "files_rotated": [],
        "errors": []
    }

    for root, dirs, files in os.walk(LOG_ROOT):
        for file in files:
            if file.endswith(".log"):
                file_path = os.path.join(root, file)
                stats["files_scanned"] += 1
                try:
                    file_size = os.path.getsize(file_path)
                    logger.debug(f"Checking {file_path} (Size: {file_size} bytes)")
                    
                    if file_size > DEFAULT_MAX_BYTES:
                        logger.info(f"File {file_path} exceeds size limit. Manually rotating...")
                        
                        # Manual rotation logic for files not in active use by a logger
                        # We simulate the RotatingFileHandler behavior
                        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                        dest_path = f"{file_path}.{timestamp}.gz"
                        
                        rotator(file_path, dest_path)
                        # Re-create empty log file
                        Path(file_path).touch()
                        
                        stats["files_rotated"].append({
                            "path": file_path,
                            "size_before": file_size,
                            "rotated_to": dest_path
                        })
                except Exception as e:
                    err_msg = f"Error processing {file_path}: {e}"
                    logger.error(err_msg)
                    stats["errors"].append(err_msg)

    # Save report
    try:
        with open(REPORT_PATH, "w") as f:
            json.dump(stats, f, indent=2)
        logger.info(f"Janitor report saved to {REPORT_PATH}")
    except Exception as e:
        logger.error(f"Failed to save report: {e}")

    return stats

if __name__ == "__main__":
    run_janitor()
