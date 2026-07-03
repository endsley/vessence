"""Pure Docker command builders for safe_docker.py."""

from __future__ import annotations


def safe_container_name(uuid_hex: str) -> str:
    return f"safe_{uuid_hex[:8]}"


def docker_run_command(
    *,
    container_name: str,
    image: str,
    args: list[str] | None = None,
    volumes: dict[str, str] | None = None,
    env: dict[str, str] | None = None,
    memory: str = "4g",
    cpus: int = 2,
    gpu_enabled: bool = False,
) -> list[str]:
    cmd = [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        f"--memory={memory}",
        f"--cpus={cpus}",
    ]
    if gpu_enabled:
        cmd.extend(["--gpus", "all"])
    if env:
        for key, value in env.items():
            cmd.extend(["-e", f"{key}={value}"])
    if volumes:
        for host_path, container_path in volumes.items():
            cmd.extend(["-v", f"{host_path}:{container_path}"])
    cmd.append(image)
    if args:
        cmd.extend(args)
    return cmd
