import os
import sys
import shutil
import time

# Add the parent directory to sys.path to import janitor_logs
sys.path.append("/home/chieh/vessence/agent_skills")
import janitor_logs

TEST_LOG_DIR = "/home/chieh/ambient/logs/test_logs"
TEST_LOG_FILE = os.path.join(TEST_LOG_DIR, "test_manual.log")
TEST_ROTATING_LOG = os.path.join(TEST_LOG_DIR, "test_rotating.log")

def setup_test():
    if os.path.exists(TEST_LOG_DIR):
        shutil.rmtree(TEST_LOG_DIR)
    os.makedirs(TEST_LOG_DIR)

def test_manual_rotation():
    print("Testing manual rotation...")
    # Create a dummy log file larger than 5MB
    with open(TEST_LOG_FILE, "wb") as f:
        f.write(b"0" * (6 * 1024 * 1024)) # 6MB
    
    print(f"Created dummy log file: {TEST_LOG_FILE} ({os.path.getsize(TEST_LOG_FILE)} bytes)")
    
    # Run janitor
    # Need to temporarily change the LOG_ROOT for janitor_logs
    janitor_logs.LOG_ROOT = TEST_LOG_DIR
    janitor_logs.run_janitor()
    
    # Check if original file is empty and a .gz file exists
    if os.path.getsize(TEST_LOG_FILE) == 0:
        print("PASS: Original file is now empty.")
    else:
        print("FAIL: Original file is NOT empty.")
        
    found_gz = False
    for f in os.listdir(TEST_LOG_DIR):
        if f.endswith(".gz") and "test_manual.log" in f:
            found_gz = True
            print(f"PASS: Found compressed rotated file: {f}")
            break
    
    if not found_gz:
        print("FAIL: Could not find rotated compressed file.")

def test_automatic_rotation():
    print("\nTesting automatic rotation via logger...")
    # Configure logger with small maxBytes for easy testing
    logger = janitor_logs.get_rotating_logger("test_auto", TEST_ROTATING_LOG, max_bytes=1000, backup_count=3)
    
    # Write some logs to trigger rotation
    for i in range(50):
        logger.info(f"This is log message number {i} designed to fill up the file quickly.")
        
    time.sleep(1) # Wait for file operations
    
    # Check for rotated files
    files = os.listdir(TEST_LOG_DIR)
    gz_files = [f for f in files if f.endswith(".gz") and "test_rotating.log" in f]
    
    print(f"Found {len(gz_files)} rotated compressed files for automatic rotation.")
    if len(gz_files) > 0:
        print("PASS: Automatic rotation and compression works.")
    else:
        print("FAIL: No rotated files found.")

if __name__ == "__main__":
    setup_test()
    try:
        test_manual_rotation()
        test_automatic_rotation()
    finally:
        # cleanup
        # shutil.rmtree(TEST_LOG_DIR)
        pass
