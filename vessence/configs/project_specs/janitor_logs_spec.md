# Spec: Log-Rotating Utility (`janitor_logs.py`)

## Overview:
A utility designed to manage log file size and rotation in the `my_agent` workspace. Its primary role is to ensure that log files do not grow indefinitely and to maintain a historical record through rotation and optional compression.

## Functional Requirements:
1. **Log Rotation**: Automatically rotate logs when they reach a certain size (e.g., 5MB).
2. **Retention**: Keep a configurable number of backup log files (e.g., 5).
3. **Compression**: Compress older log files (e.g., `.gz` format) to save disk space.
4. **Target Directory**: Focus on the `/home/chieh/ambient/logs/` directory.
5. **Debug Information**: Provide verbose internal logging for debugging rotation events.
6. **Integration**: Compatible with standard Python `logging` module.

## Implementation Details:
- **Language**: Python 3.
- **Module Path**: `/home/chieh/vessence/agent_skills/janitor_logs.py`.
- **Primary Mechanism**: Use `logging.handlers.RotatingFileHandler` or a custom implementation if compression is required beyond standard library capabilities.

## Error Handling:
- Handle permission errors for file operations.
- Gracefully handle cases where the log directory is empty or inaccessible.
- Ensure rotation does not cause log data loss.

## Performance Considerations:
- Minimal performance overhead for the main agent application.
- Efficient file operations.
