#!/usr/bin/env python3
"""
process_watchdog.py — Kill zombie subprocesses and enforce resource limits.

Runs periodically via cron. Handles:
1. Orphaned Docker TTS containers (running >10 min)
2. Zombie Gradle/Kotlin daemons (idle >15 min)
3. Any single process using >40% of RAM

Does NOT kill: chrome, claude, jane-web, ollama (expected long-runners).
"""

import os
import subprocess
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [watchdog] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("watchdog")

# Processes that are allowed to be long-running
PROTECTED_NAMES = {"chrome", "claude", "uvicorn", "ollama", "Xorg", "systemd", "jane"}
MAX_CONTAINER_AGE_MINUTES = 10
MAX_RAM_PERCENT = 40  # kill if single process exceeds this


def kill_old_tts_containers():
    """Kill Docker TTS containers running longer than MAX_CONTAINER_AGE_MINUTES."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "ancestor=ghcr.io/coqui-ai/tts:latest",
             "--format", "{{.ID}} {{.RunningFor}} {{.Names}}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return

        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split()
            container_id = parts[0]
            running_for = " ".join(parts[1:-1])  # e.g. "15 minutes"
            name = parts[-1] if len(parts) > 2 else ""

            # Parse duration — kill if >MAX_CONTAINER_AGE_MINUTES
            if "hour" in running_for or _parse_minutes(running_for) > MAX_CONTAINER_AGE_MINUTES:
                log.warning(f"Killing old TTS container {container_id} ({name}, running {running_for})")
                subprocess.run(["docker", "kill", container_id], capture_output=True, timeout=10)
                subprocess.run(["docker", "rm", "-f", container_id], capture_output=True, timeout=10)

    except Exception as e:
        log.error(f"Docker cleanup failed: {e}")


def _parse_minutes(duration_str: str) -> int:
    """Parse Docker's 'RunningFor' string into minutes."""
    try:
        if "minute" in duration_str:
            return int(duration_str.split()[0])
        if "second" in duration_str:
            return 0
        if "hour" in duration_str:
            return int(duration_str.split()[0]) * 60
    except (ValueError, IndexError):
        pass
    return 0


def kill_idle_build_daemons():
    """Kill Gradle and Kotlin daemons that have been idle."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "GradleDaemon|KotlinCompileDaemon"],
            capture_output=True, text=True, timeout=5,
        )
        for pid_str in result.stdout.strip().split("\n"):
            if not pid_str.strip():
                continue
            pid = int(pid_str.strip())
            # Check if it's been idle (low CPU for a while)
            try:
                stat = subprocess.run(
                    ["ps", "-p", str(pid), "-o", "%cpu=", "--no-headers"],
                    capture_output=True, text=True, timeout=5,
                )
                cpu = float(stat.stdout.strip() or "0")
                if cpu < 1.0:
                    cmdline = subprocess.run(
                        ["ps", "-p", str(pid), "-o", "comm="],
                        capture_output=True, text=True, timeout=5,
                    ).stdout.strip()
                    log.warning(f"Killing idle build daemon: PID {pid} ({cmdline}, CPU={cpu}%)")
                    os.kill(pid, 15)  # SIGTERM
            except (ValueError, ProcessLookupError):
                pass
    except Exception as e:
        log.error(f"Build daemon cleanup failed: {e}")


def kill_memory_hogs():
    """Kill non-protected processes using more than MAX_RAM_PERCENT of total RAM."""
    try:
        result = subprocess.run(
            ["ps", "aux", "--sort=-%mem", "--no-headers"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.strip().split("\n")[:20]:  # check top 20
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue
            user, pid_str, cpu, mem, *_, command = parts
            mem_pct = float(mem)
            pid = int(pid_str)

            if mem_pct < MAX_RAM_PERCENT:
                break  # sorted by mem, so rest are lower

            # Check if protected
            cmd_lower = command.lower()
            if any(name in cmd_lower for name in PROTECTED_NAMES):
                continue

            log.warning(f"Killing memory hog: PID {pid} ({command[:60]}, {mem_pct}% RAM)")
            os.kill(pid, 15)  # SIGTERM
            time.sleep(2)
            # Force kill if still alive
            try:
                os.kill(pid, 0)  # check if alive
                os.kill(pid, 9)  # SIGKILL
            except ProcessLookupError:
                pass

    except Exception as e:
        log.error(f"Memory hog cleanup failed: {e}")


def main():
    log.info("Running process watchdog...")
    kill_old_tts_containers()
    kill_idle_build_daemons()
    kill_memory_hogs()
    log.info("Watchdog complete.")


if __name__ == "__main__":
    main()
