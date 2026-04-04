import pexpect
from pathlib import Path
import sys
import time

def test_jane_wrapper():
    print("Starting Jane Wrapper test...")
    repo_root = Path(__file__).resolve().parents[1]
    wrapper_path = repo_root / "jane" / "jane_session_wrapper.py"
    # Spawn the wrapper
    # Use -u for unbuffered python
    child = pexpect.spawn(
        f'/home/chieh/google-adk-env/adk-venv/bin/python -u {wrapper_path}',
        cwd=str(repo_root),
        encoding='utf-8',
        timeout=60,
    )
    # Stream child stdout to our stdout for visibility
    child.logfile = sys.stdout
    
    try:
        # Wait for the startup banner
        child.expect('--- Jane Pro-Wrapper Started ---', timeout=10)
        print("\n[Test] Wrapper started successfully.")
        
        # Wait for the prompt
        child.expect('You: ', timeout=10)
        print("\n[Test] Seen 'You: ' prompt.")
        
        # Send a simple hello
        child.sendline('hello, are you there?')
        print("\n[Test] Sent greeting.")
        
        # Wait for some text from gemini
        # Since gemini CLI might take time, we wait up to 30s
        # Looking for common gemini output (like ✦ or some content)
        # or even the next "You: "
        child.expect('You: ', timeout=45)
        print("\n[Test] Received response and back to prompt.")
        
        # Send exit
        child.sendline('/exit')
        child.expect(pexpect.EOF, timeout=10)
        print("\n[Test] Wrapper exited cleanly.")
        
    except pexpect.TIMEOUT:
        print("\n[Test] TIMEOUT waiting for expected output.")
        print("Before timeout:", child.before)
    except Exception as e:
        print(f"\n[Test] Error: {e}")
    finally:
        child.close()

if __name__ == "__main__":
    test_jane_wrapper()
