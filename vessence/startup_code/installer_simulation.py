#!/usr/bin/env python3
"""Lightweight installer simulations for packaged Vessence installers."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


class InstallerSimulationError(RuntimeError):
    """Raised when an installer simulation fails."""


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _assert_install_result(install_dir: Path, docker_log: Path, *, require_runtime_env: bool = True) -> None:
    required_files = [
        install_dir / "docker-compose.yml",
        install_dir / ".env.example",
    ]
    if require_runtime_env:
        required_files.append(install_dir / "runtime" / ".env")
    for path in required_files:
        if not path.exists():
            raise InstallerSimulationError(f"expected installed file missing: {path}")

    if require_runtime_env:
        env_text = (install_dir / "runtime" / ".env").read_text(encoding="utf-8")
        if "JANE_BRAIN=gemini" not in env_text:
            raise InstallerSimulationError("runtime/.env missing JANE_BRAIN=gemini after install")
        if "JANE_WEB_PERMISSIONS=0" not in env_text:
            raise InstallerSimulationError("runtime/.env missing JANE_WEB_PERMISSIONS=0 after install")

    log_text = docker_log.read_text(encoding="utf-8")
    for expected in ("info", "compose version", "compose build --no-cache", "compose up -d"):
        if expected not in log_text:
            raise InstallerSimulationError(f"docker shim never received expected command: {expected}")


def _simulate_unix(package_root: Path, installer_name: str, open_command: str) -> None:
    with tempfile.TemporaryDirectory(prefix="vessence-installer-sim-") as tmp:
        tmp_path = Path(tmp)
        home_dir = tmp_path / "home"
        install_dir = home_dir / "sim-vessence"
        shim_dir = tmp_path / "bin"
        docker_log = tmp_path / "docker.log"
        open_log = tmp_path / "open.log"
        home_dir.mkdir()
        shim_dir.mkdir()

        _write_executable(
            shim_dir / "docker",
            f"""#!/bin/sh
set -eu
printf '%s\\n' "$*" >> "{docker_log}"
exit 0
""",
        )
        _write_executable(
            shim_dir / "curl",
            """#!/bin/sh
set -eu
if [ "${1:-}" = "-fsS" ] && [ "${2:-}" = "http://localhost:3000/health" ]; then
  printf '{"status":"ok"}\\n'
  exit 0
fi
exit 1
""",
        )
        _write_executable(
            shim_dir / open_command,
            f"""#!/bin/sh
set -eu
printf '%s\\n' "$*" >> "{open_log}"
exit 0
""",
        )

        env = os.environ.copy()
        env.update(
            {
                "HOME": str(home_dir),
                "PATH": f"{shim_dir}:{env.get('PATH', '')}",
                "VESSENCE_INSTALL_DIR": str(install_dir),
                "VESSENCE_NONINTERACTIVE": "1",
                "VESSENCE_PROVIDER_CHOICE": "1",
                "VESSENCE_SKIP_BROWSER": "1",
            }
        )

        result = subprocess.run(
            ["bash", installer_name],
            cwd=package_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise InstallerSimulationError(
                f"{installer_name} failed with code {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )

        _assert_install_result(install_dir, docker_log)


def _winepath(path: Path, env: dict[str, str]) -> str:
    result = subprocess.run(
        ["winepath", "-w", str(path)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise InstallerSimulationError(f"winepath failed for {path}: {result.stderr.strip()}")
    return result.stdout.strip()


def _simulate_windows(package_root: Path, installer_name: str) -> None:
    if shutil.which("wine") is None or shutil.which("winepath") is None:
        raise InstallerSimulationError("wine/winepath are required to simulate the Windows installer")

    with tempfile.TemporaryDirectory(prefix="vessence-installer-sim-win-") as tmp:
        tmp_path = Path(tmp)
        install_dir = package_root
        shim_dir = tmp_path / "bin"
        docker_log = tmp_path / "docker.log"
        shim_dir.mkdir()

        docker_shim = shim_dir / "docker.bat"
        _write_executable(
            docker_shim,
            """@echo off
if not defined SIM_LOG exit /b 9
echo %*>> "%SIM_LOG%"
exit /b 0
""",
        )
        powershell_shim = shim_dir / "powershell.bat"
        _write_executable(
            powershell_shim,
            """@echo off
exit /b 0
""",
        )
        runner_name = "install-runner.bat"
        source_text = (package_root / installer_name).read_text(encoding="utf-8", errors="replace")
        runner_text = re.sub(r"(?im)^(\s*)docker(\s+)", r"\1call docker\2", source_text)
        runner_text = re.sub(r"(?im)^\s*xcopy\s+.*$", "        ver >nul", runner_text)
        runner_text = runner_text.replace(
            'if not exist "%INSTALL_DIR%\\docker-compose.yml" (',
            "if 0==1 (",
        )
        runner_text = runner_text.replace(
            'if not exist "%INSTALL_DIR%\\.env.example" (',
            "if 0==1 (",
        )
        runner_text = re.sub(r'(?im)^\s*if not "%NONINTERACTIVE%"=="1" pause\s*$', "        rem simulated pause", runner_text)
        runner_text = re.sub(r"(?im)^\s*pause\s*$", "rem simulated pause", runner_text)
        runner_text = re.sub(
            r'(?im)^\s*if not "%SKIP_BROWSER%"=="1" start "" "http://localhost:3000"\s*$',
            "rem simulated browser launch",
            runner_text,
        )
        runner_path = package_root / runner_name
        runner_path.write_text(runner_text.replace("\n", "\r\n"), encoding="utf-8")

        wine_env = os.environ.copy()
        wine_env.setdefault("WINEDEBUG", "-all")
        shim_win = _winepath(shim_dir, wine_env)
        package_win = _winepath(package_root, wine_env)
        install_win = _winepath(install_dir, wine_env)
        log_win = _winepath(docker_log, wine_env)

        cmd = (
            f'set PATH={shim_win};%PATH% && '
            f'set SIM_LOG={log_win} && '
            f'set VESSENCE_NONINTERACTIVE=1 && '
            f'set VESSENCE_PROVIDER_CHOICE=1 && '
            f'set VESSENCE_SKIP_BROWSER=1 && '
            f'set VESSENCE_SKIP_COPY=1 && '
            f'set VESSENCE_INSTALL_DIR={install_win} && '
            f'cd /d {package_win} && '
            f'call {runner_name}'
        )
        result = subprocess.run(
            ["wine", "cmd", "/c", cmd],
            env=wine_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        if result.returncode != 0:
            raise InstallerSimulationError(
                f"{installer_name} failed with code {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )

        if ".env created with JANE_BRAIN=gemini" not in result.stdout and "Existing .env found" not in result.stdout:
            raise InstallerSimulationError("Windows installer did not report creating or reusing runtime/.env")

        _assert_install_result(install_dir, docker_log, require_runtime_env=False)


def simulate_installer_package(platform: str, package_root: Path) -> None:
    """Execute an installer package in a temporary sandbox with fake docker/open shims."""
    if platform == "linux":
        _simulate_unix(package_root, "install-linux.sh", "xdg-open")
    elif platform == "mac":
        _simulate_unix(package_root, "install-mac.command", "open")
    elif platform == "windows":
        _simulate_windows(package_root, "Install Vessence.bat")
    else:
        raise ValueError(f"Unsupported platform: {platform}")
