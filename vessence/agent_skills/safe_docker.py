"""
safe_docker.py — Safe Docker subprocess runner.

Prevents runaway containers by:
1. Using named containers so they can be force-killed on timeout
2. Enforcing --memory and --cpus limits
3. Using a global semaphore to limit concurrent containers
4. Properly cleaning up containers on timeout/error

Usage:
    from agent_skills.safe_docker import run_docker
    result = run_docker(
        image="ghcr.io/coqui-ai/tts:latest",
        args=["--text", "hello", "--out_path", "/output/out.wav"],
        volumes={"/tmp/tts": "/output"},
        env={"COQUI_TOS_AGREED": "1"},
        timeout=300,
        memory="4g",
        cpus=2,
        gpu=True,
    )
"""

import logging
import os
import subprocess
import threading
import uuid

logger = logging.getLogger("safe_docker")

# Global: only 1 heavy Docker container at a time
_docker_lock = threading.Lock()


def run_docker(
    image: str,
    args: list[str] | None = None,
    volumes: dict[str, str] | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 300,
    memory: str = "4g",
    cpus: int = 2,
    gpu: bool = False,
) -> subprocess.CompletedProcess | None:
    """Run a Docker container with resource limits and proper cleanup.

    Returns CompletedProcess on success, None on timeout/failure.
    Only one container runs at a time (global lock).
    """
    container_name = f"safe_{uuid.uuid4().hex[:8]}"

    cmd = [
        "docker", "run", "--rm",
        "--name", container_name,
        f"--memory={memory}",
        f"--cpus={cpus}",
    ]

    if gpu and os.path.exists("/usr/bin/nvidia-smi"):
        cmd.extend(["--gpus", "all"])

    if env:
        for k, v in env.items():
            cmd.extend(["-e", f"{k}={v}"])

    if volumes:
        for host_path, container_path in volumes.items():
            cmd.extend(["-v", f"{host_path}:{container_path}"])

    cmd.append(image)
    if args:
        cmd.extend(args)

    acquired = _docker_lock.acquire(timeout=timeout)
    if not acquired:
        logger.warning(f"Timed out waiting for Docker lock (another container is running)")
        return None

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        return result
    except subprocess.TimeoutExpired:
        logger.error(f"Container {container_name} timed out after {timeout}s — killing")
        _force_kill(container_name)
        return None
    except Exception as e:
        logger.error(f"Container {container_name} failed: {e}")
        _force_kill(container_name)
        return None
    finally:
        _docker_lock.release()


def _force_kill(container_name: str):
    """Force-kill and remove a Docker container."""
    try:
        subprocess.run(["docker", "kill", container_name],
                       capture_output=True, timeout=10)
    except Exception:
        pass
    try:
        subprocess.run(["docker", "rm", "-f", container_name],
                       capture_output=True, timeout=10)
    except Exception:
        pass
