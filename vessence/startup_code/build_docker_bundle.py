#!/usr/bin/env python3
"""Build OS-specific Vessence installer packages (Windows, Mac, Linux)."""
from __future__ import annotations

import re
import shutil
import subprocess
import zipfile
from pathlib import Path


VERSION = "0.0.12"

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKETING_ROOT = REPO_ROOT / "marketing_site"
DOWNLOADS_DIR = MARKETING_ROOT / "downloads"
INSTALLERS_DIR = REPO_ROOT / "startup_code" / "installers"

PLATFORMS = {
    "windows": {
        "zip_name": f"vessence-windows-installer-v{VERSION}.zip",
        "installer": "Install Vessence.bat",
        "installer_src": "install-windows.bat",
        "uninstaller": "Uninstall Vessence.bat",
        "uninstaller_src": "uninstall-windows.bat",
        "readme": "README-windows.txt",
    },
    "mac": {
        "zip_name": f"vessence-mac-installer-v{VERSION}.zip",
        "installer": "install-mac.command",
        "uninstaller": "uninstall-mac.command",
        "uninstaller_src": "uninstall-mac.command",
        "readme": "README-mac.txt",
    },
    "linux": {
        "zip_name": f"vessence-linux-installer-v{VERSION}.zip",
        "installer": "install-linux.sh",
        "uninstaller": "uninstall-linux.sh",
        "uninstaller_src": "uninstall-linux.sh",
        "readme": "README-linux.txt",
    },
}


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_tree(src: Path, dst: Path, *, ignore=None) -> None:
    shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=True)


def _ensure_crlf(path: Path) -> None:
    """Convert a text file to CRLF line endings (required for Windows .bat files)."""
    data = path.read_bytes()
    # Normalize to LF first, then convert to CRLF
    data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n").replace(b"\n", b"\r\n")
    path.write_bytes(data)


def build_readme(platform: str) -> str:
    install_steps = {
        "windows": (
            "1. Make sure Docker Desktop is installed and running.\n"
            "   Download: https://www.docker.com/products/docker-desktop/\n"
            "2. Extract this zip to a folder.\n"
            "3. IMPORTANT: Right-click \"Install Vessence.bat\" → Properties → check \"Unblock\" → OK\n"
            "   (Windows blocks downloaded scripts by default)\n"
            "4. Double-click \"Install Vessence\" to run it.\n"
            "5. If Windows asks \"Do you want to run this?\", click Yes/Run anyway.\n"
            "6. The installer will copy files, pull images, and start Vessence.\n"
            "7. Your browser will open to the onboarding wizard."
        ),
        "mac": (
            "1. Make sure Docker Desktop is installed and running.\n"
            "   Download: https://www.docker.com/products/docker-desktop/\n"
            "2. Extract this zip to a folder.\n"
            "3. Double-click install-mac.command\n"
            "   (If macOS blocks it: right-click > Open)\n"
            "4. The installer will copy files, pull images, and start Vessence.\n"
            "5. Your browser will open to the onboarding wizard."
        ),
        "linux": (
            "1. Make sure Docker Engine is installed and running.\n"
            "   Quick install: curl -fsSL https://get.docker.com | sudo sh\n"
            "2. Extract this zip to a folder.\n"
            "3. Run: bash install-linux.sh\n"
            "4. The installer will copy files, pull images, and start Vessence.\n"
            "5. Your browser will open to the onboarding wizard."
        ),
    }
    stop_start = {
        "windows": (
            "To stop:   Open a terminal and run: cd %USERPROFILE%\\vessence && docker compose down\n"
            "To start:  Open a terminal and run: cd %USERPROFILE%\\vessence && docker compose up -d"
        ),
        "mac": (
            "To stop:   cd ~/vessence && docker compose down\n"
            "To start:  cd ~/vessence && docker compose up -d"
        ),
        "linux": (
            "To stop:   cd ~/vessence && docker compose down\n"
            "To start:  cd ~/vessence && docker compose up -d"
        ),
    }

    return f"""Vessence Installer ({platform.capitalize()})
{'=' * (24 + len(platform))}

Quick start
-----------
{install_steps[platform]}

After installation
------------------
- Onboarding:  http://localhost:3000
- Jane:        http://jane.localhost

{stop_start[platform]}

Contents
--------
- {PLATFORMS[platform]['installer']}  (installer script)
- docker-compose.yml
- .env.example
- traefik/traefik.yml
- marketing_site/  (local landing page)
"""


def build_platform_package(platform: str) -> Path:
    """Build a single platform's installer zip. Returns the zip path."""
    cfg = PLATFORMS[platform]
    staging = DOWNLOADS_DIR / f"vessence-{platform}-staging"
    zip_path = DOWNLOADS_DIR / cfg["zip_name"]

    reset_dir(staging)

    # Copy installer script (use source name if different from package name)
    src_name = cfg.get("installer_src", cfg["installer"])
    src_installer = INSTALLERS_DIR / src_name
    dst_installer = staging / cfg["installer"]
    shutil.copy2(src_installer, dst_installer)
    # Ensure Windows batch files have CRLF line endings (cmd.exe crashes on LF-only)
    if dst_installer.suffix.lower() == ".bat":
        _ensure_crlf(dst_installer)

    # Copy uninstaller script
    unsrc_name = cfg.get("uninstaller_src", cfg.get("uninstaller"))
    if unsrc_name:
        unsrc_path = INSTALLERS_DIR / unsrc_name
        if unsrc_path.exists():
            dst_uninstaller = staging / cfg["uninstaller"]
            shutil.copy2(unsrc_path, dst_uninstaller)
            if dst_uninstaller.suffix.lower() == ".bat":
                _ensure_crlf(dst_uninstaller)

    # Shared files
    shutil.copy2(REPO_ROOT / "docker-compose.yml", staging / "docker-compose.yml")
    shutil.copy2(REPO_ROOT / ".env.example", staging / ".env.example")

    traefik_src = REPO_ROOT / "traefik"
    if traefik_src.exists():
        copy_tree(traefik_src, staging / "traefik")

    marketing_ignore = shutil.ignore_patterns("downloads", ".gitkeep", "docker-compose.yml")
    copy_tree(MARKETING_ROOT, staging / "marketing_site", ignore=marketing_ignore)

    # Docker build context — Dockerfiles + source needed for `docker compose up --build`
    docker_dir = REPO_ROOT / "docker"
    if docker_dir.exists():
        docker_ignore = shutil.ignore_patterns("amber", "vault", "chromadb")
        copy_tree(docker_dir, staging / "docker", ignore=docker_ignore)

    # Source directories needed by the Dockerfiles
    for src_dir in ("jane", "jane_web", "vault_web", "agent_skills", "onboarding", "essences", "tools"):
        src_path = REPO_ROOT / src_dir
        if src_path.exists():
            build_ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".git", "node_modules")
            copy_tree(src_path, staging / src_dir, ignore=build_ignore)

    # Requirements files
    for req_file in ("requirements.txt", "requirements-jane.txt", "requirements-onboarding.txt"):
        req_path = REPO_ROOT / req_file
        if req_path.exists():
            shutil.copy2(req_path, staging / req_file)

    # Config files needed at build/runtime
    configs_src = REPO_ROOT / "configs"
    if configs_src.exists():
        configs_ignore = shutil.ignore_patterns("job_queue", "project_specs", "systemd", "kokoro_env.yml", "crontab_backup.txt", "*.pyc")
        copy_tree(configs_src, staging / "configs", ignore=configs_ignore)

    # README
    (staging / "README.txt").write_text(build_readme(platform), encoding="utf-8")

    # Zip
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                arcname = Path("vessence") / path.relative_to(staging)
                zf.write(path, arcname)

    # Clean up staging
    shutil.rmtree(staging)

    size_kb = zip_path.stat().st_size / 1024
    print(f"  Built {cfg['zip_name']} ({size_kb:.0f} KB)")
    return zip_path


# Known-good binaries per base image for healthcheck validation
HEALTHCHECK_BINS: dict[str, list[str]] = {
    "chromadb/chroma": ["bash", "sh"],
    "python": ["python", "pip", "bash", "sh", "curl"],      # slim installs curl in our Dockerfile
    "python:3.13-alpine": ["python", "pip", "sh", "curl"],   # alpine + apk add curl
    "nginx": ["curl", "wget", "sh"],
    "traefik": ["sh"],
    "cloudflare/cloudflared": ["sh", "cloudflared"],
}


def _match_image_bins(image: str) -> list[str]:
    """Return the known-good binary list for an image string."""
    # Try exact match first, then prefix match
    for key, bins in HEALTHCHECK_BINS.items():
        if image == key or image.startswith(key + ":"):
            return bins
    # Fallback: allow anything (we can't validate unknown images)
    return []


def _parse_compose_services(compose_path: Path) -> dict:
    """Lightweight YAML parse of docker-compose.yml to extract service info.

    We avoid importing PyYAML (not guaranteed available) by using
    ``docker compose config`` JSON output when docker is available,
    falling back to regex extraction.
    """
    try:
        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_path), "config", "--format", "json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            import json
            return json.loads(result.stdout).get("services", {})
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass
    return {}


def validate() -> bool:
    """Run pre-build validation checks. Returns True if all pass."""
    errors: list[str] = []
    compose_path = REPO_ROOT / "docker-compose.yml"

    # ── 1. Validate compose syntax ──────────────────────────────────────────
    print("  [1/7] Validating docker-compose.yml syntax...")
    try:
        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_path), "config", "--quiet"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            errors.append(f"docker compose config failed:\n{result.stderr.strip()}")
    except FileNotFoundError:
        errors.append("docker CLI not found — cannot validate compose syntax")
    except subprocess.TimeoutExpired:
        errors.append("docker compose config timed out")

    # ── 2. Verify all Dockerfile paths referenced in docker-compose.yml ─────
    print("  [2/7] Checking Dockerfile paths...")
    compose_text = compose_path.read_text()
    dockerfile_refs = re.findall(r"dockerfile:\s*(.+)", compose_text)
    for df_rel in dockerfile_refs:
        df_rel = df_rel.strip()
        # Skip commented-out lines
        # Find the line in compose_text and check if it's commented
        for line in compose_text.splitlines():
            stripped = line.lstrip()
            if f"dockerfile: {df_rel}" in line or f"dockerfile:{df_rel}" in line:
                if stripped.startswith("#"):
                    break
        else:
            # Not commented — verify existence
            df_path = REPO_ROOT / df_rel
            if not df_path.exists():
                errors.append(f"Dockerfile not found: {df_rel}")

    # ── 3. Verify COPY/ADD sources in each Dockerfile ───────────────────────
    print("  [3/7] Checking COPY/ADD source paths in Dockerfiles...")
    active_dockerfiles = []
    for df_rel in dockerfile_refs:
        df_rel = df_rel.strip()
        # Check if the line is commented out
        is_commented = False
        for line in compose_text.splitlines():
            stripped = line.lstrip()
            if df_rel in line and stripped.startswith("#"):
                is_commented = True
                break
        if is_commented:
            continue
        df_path = REPO_ROOT / df_rel
        if df_path.exists():
            active_dockerfiles.append(df_path)

    for df_path in active_dockerfiles:
        df_text = df_path.read_text()
        # The build context is REPO_ROOT (context: .)
        for match in re.finditer(r"^(?:COPY|ADD)\s+(.+?)\s+\S+\s*$", df_text, re.MULTILINE):
            src = match.group(1).strip()
            # Skip --from= (multi-stage), --chmod, --chown flags
            if src.startswith("--"):
                # Parse past the flag
                parts = match.group(0).split()
                # Find actual source (skip instruction + flags)
                srcs = [p for p in parts[1:-1] if not p.startswith("--")]
                src = srcs[0] if srcs else ""
            if not src or src.startswith("http"):
                continue
            src_path = REPO_ROOT / src
            if not src_path.exists():
                errors.append(f"{df_path.name}: COPY/ADD source not found: {src} (expected at {src_path})")

    # ── 4. Verify requirements*.txt files referenced in Dockerfiles ─────────
    print("  [4/7] Checking requirements files referenced in Dockerfiles...")
    for df_path in active_dockerfiles:
        df_text = df_path.read_text()
        for req_match in re.finditer(r"(?:COPY|ADD)\s+(\S*requirements\S*\.txt)\s", df_text):
            req_rel = req_match.group(1)
            req_path = REPO_ROOT / req_rel
            if not req_path.exists():
                errors.append(f"{df_path.name}: requirements file not found: {req_rel}")

    # ── 5. Healthcheck binary validation ────────────────────────────────────
    print("  [5/7] Validating healthcheck commands...")
    services = _parse_compose_services(compose_path)
    if services:
        for svc_name, svc in services.items():
            hc = svc.get("healthcheck", {})
            test = hc.get("test")
            if not test:
                continue
            # test can be a list like ["CMD", "curl", ...] or ["CMD-SHELL", "bash -c ..."]
            if isinstance(test, list) and len(test) >= 2:
                if test[0] == "CMD":
                    binary = test[1]
                elif test[0] == "CMD-SHELL":
                    # Extract the first command word
                    shell_cmd = test[1] if len(test) == 2 else " ".join(test[1:])
                    binary = shell_cmd.split()[0]
                else:
                    continue
            else:
                continue

            image = svc.get("image", "")
            # For services with build context, check Dockerfile FROM line
            if not image and "build" in svc:
                build_cfg = svc["build"]
                df = build_cfg.get("dockerfile", "Dockerfile") if isinstance(build_cfg, dict) else "Dockerfile"
                df_full = REPO_ROOT / df
                if df_full.exists():
                    from_match = re.search(r"^FROM\s+(\S+)", df_full.read_text(), re.MULTILINE)
                    if from_match:
                        image = from_match.group(1)

            known_bins = _match_image_bins(image)
            if known_bins and binary not in known_bins:
                errors.append(
                    f"Service '{svc_name}': healthcheck uses '{binary}' but image "
                    f"'{image}' only has {known_bins}"
                )

    # ── 6. Verify .env.example exists ───────────────────────────────────────
    print("  [6/7] Checking .env.example...")
    if not (REPO_ROOT / ".env.example").exists():
        errors.append(".env.example not found in repo root")

    # ── 7. Verify traefik/traefik.yml exists ────────────────────────────────
    print("  [7/7] Checking traefik/traefik.yml...")
    if not (REPO_ROOT / "traefik" / "traefik.yml").exists():
        errors.append("traefik/traefik.yml not found in repo root")

    # ── Report ──────────────────────────────────────────────────────────────
    if errors:
        print(f"\n  VALIDATION FAILED — {len(errors)} error(s):")
        for i, err in enumerate(errors, 1):
            print(f"    {i}. {err}")
        return False

    print("  Validation passed.")
    return True


def build_all() -> None:
    print("Running pre-build validation...")
    if not validate():
        print("\nBuild aborted due to validation errors.")
        raise SystemExit(1)
    print()

    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    # Remove old combined package
    old_zip = DOWNLOADS_DIR / "vessence-docker-package.zip"
    old_staging = DOWNLOADS_DIR / "vessence-docker-package"
    if old_zip.exists():
        old_zip.unlink()
        print("  Removed old vessence-docker-package.zip")
    if old_staging.exists():
        shutil.rmtree(old_staging)

    print("Building OS-specific installer packages...")
    for platform in PLATFORMS:
        build_platform_package(platform)
    print("Done.")


if __name__ == "__main__":
    build_all()
