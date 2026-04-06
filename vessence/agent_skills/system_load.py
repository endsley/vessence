#!/usr/bin/env python3
"""
system_load.py — Load-aware task throttling for Vessence.

Checks CPU, memory, and time of day to determine safe parallelism levels.
Used by prompt queue, cron jobs, and Jane's agent spawning to avoid
overloading the system and making web/Android unresponsive.

Daytime (6 AM - 11 PM): conservative — keep services responsive.
Nighttime (11 PM - 6 AM): aggressive — user is sleeping, use full resources.
"""

import datetime
import logging
import os
import subprocess

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger("system_load")

# ── Configurable thresholds ──────────────────────────────────────────────────
MAX_PARALLEL = int(os.environ.get("JANE_MAX_PARALLEL", "4"))
CPU_THRESHOLD_HIGH = float(os.environ.get("JANE_LOAD_THRESHOLD_CPU", "60"))
CPU_THRESHOLD_MED = float(os.environ.get("JANE_LOAD_THRESHOLD_CPU_MED", "30"))
MEM_FREE_MIN_GB = float(os.environ.get("JANE_LOAD_THRESHOLD_MEM_GB", "2.0"))
GPU_THRESHOLD_HIGH = float(os.environ.get("JANE_LOAD_THRESHOLD_GPU", "70"))
VRAM_FREE_MIN_MB = float(os.environ.get("JANE_LOAD_THRESHOLD_VRAM_MB", "1024"))
NIGHT_START_HOUR = int(os.environ.get("JANE_NIGHT_START", "23"))  # 11 PM
NIGHT_END_HOUR = int(os.environ.get("JANE_NIGHT_END", "6"))       # 6 AM


def _is_nighttime() -> bool:
    """Return True if current local time is in the nighttime window."""
    hour = datetime.datetime.now().hour
    if NIGHT_START_HOUR > NIGHT_END_HOUR:
        # Wraps midnight: e.g., 23-6
        return hour >= NIGHT_START_HOUR or hour < NIGHT_END_HOUR
    else:
        return NIGHT_START_HOUR <= hour < NIGHT_END_HOUR


def _query_gpu() -> dict:
    """Query NVIDIA GPU utilization and VRAM via nvidia-smi.

    Returns dict with gpu_percent, gpu_memory_used_mb, gpu_memory_total_mb,
    gpu_memory_free_mb.  Defaults to 0% / 9999 MB free if nvidia-smi fails.
    """
    defaults = {
        "gpu_percent": 0.0,
        "gpu_memory_used_mb": 0.0,
        "gpu_memory_total_mb": 0.0,
        "gpu_memory_free_mb": 9999.0,
    }
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode != 0:
            return defaults
        parts = [p.strip() for p in out.stdout.strip().split(",")]
        if len(parts) >= 4:
            return {
                "gpu_percent": float(parts[0]),
                "gpu_memory_used_mb": float(parts[1]),
                "gpu_memory_total_mb": float(parts[2]),
                "gpu_memory_free_mb": float(parts[3]),
            }
    except Exception as e:
        logger.debug(f"nvidia-smi unavailable: {e}")
    return defaults


def get_system_load() -> dict:
    """
    Returns current system load metrics.
    Falls back to load average if psutil is not available.
    """
    result = {
        "cpu_percent": 0.0,
        "memory_percent": 0.0,
        "memory_available_gb": 999.0,
        "load_avg_1min": 0.0,
        "load_avg_5min": 0.0,
        "is_nighttime": _is_nighttime(),
    }

    if psutil is not None:
        try:
            result["cpu_percent"] = psutil.cpu_percent(interval=0)
            mem = psutil.virtual_memory()
            result["memory_percent"] = mem.percent
            result["memory_available_gb"] = round(mem.available / (1024 ** 3), 2)
        except Exception as e:
            logger.warning(f"psutil error: {e}")

    try:
        load = os.getloadavg()
        result["load_avg_1min"] = round(load[0], 2)
        result["load_avg_5min"] = round(load[1], 2)
    except (OSError, AttributeError):
        pass

    # GPU metrics
    gpu = _query_gpu()
    result.update(gpu)

    return result


def recommended_parallelism() -> int:
    """
    Returns the recommended number of parallel agents/subprocesses.

    Nighttime: more aggressive (up to MAX_PARALLEL).
    Daytime: conservative to keep web/Android responsive.
    """
    load = get_system_load()
    cpu = load["cpu_percent"]
    mem_gb = load["memory_available_gb"]
    night = load["is_nighttime"]

    # Hard constraint: not enough memory
    if mem_gb < MEM_FREE_MIN_GB:
        logger.info(f"Low memory ({mem_gb:.1f} GB free) → parallelism: 1")
        return 1

    if night:
        # Nighttime: be more aggressive
        if cpu > CPU_THRESHOLD_HIGH:
            level = max(1, MAX_PARALLEL // 2)
        else:
            level = MAX_PARALLEL
    else:
        # Daytime: be conservative
        if cpu > CPU_THRESHOLD_HIGH:
            level = 1
        elif cpu > CPU_THRESHOLD_MED:
            level = min(2, MAX_PARALLEL)
        else:
            level = min(3, MAX_PARALLEL)

    logger.info(
        f"Load: CPU={cpu:.0f}%, Mem={mem_gb:.1f}GB free, "
        f"{'night' if night else 'day'} → parallelism: {level}"
    )
    return level


def should_defer() -> bool:
    """
    Returns True if the system is too loaded to start new background work.
    Used by cron jobs to skip runs when the system is stressed.
    """
    load = get_system_load()
    cpu = load["cpu_percent"]
    mem_gb = load["memory_available_gb"]
    gpu = load.get("gpu_percent", 0)
    gpu_mem_free = load.get("gpu_memory_free_mb", 9999)

    if mem_gb < 1.0:
        logger.info(f"Deferring: critically low memory ({mem_gb:.1f} GB)")
        return True

    # Daytime: defer if CPU > 60%
    # Nighttime: defer if CPU > 80%
    threshold = 80 if load["is_nighttime"] else 60
    if cpu > threshold:
        logger.info(f"Deferring: CPU at {cpu:.0f}% (threshold: {threshold}%)")
        return True

    if gpu > GPU_THRESHOLD_HIGH:
        logger.info(f"Deferring: GPU at {gpu:.0f}% (threshold: {GPU_THRESHOLD_HIGH}%)")
        return True

    if gpu_mem_free < VRAM_FREE_MIN_MB:
        logger.info(f"Deferring: VRAM free {gpu_mem_free:.0f} MB < {VRAM_FREE_MIN_MB:.0f} MB minimum")
        return True

    return False


def has_ample_resources(threshold_pct: float = 60) -> bool:
    """Return True if CPU, GPU, RAM, and VRAM are all below *threshold_pct* usage.

    Default 60% — the system has genuine spare capacity for background work.
    """
    load = get_system_load()
    cpu = load["cpu_percent"]
    mem_pct = load["memory_percent"]
    gpu = load.get("gpu_percent", 0)
    gpu_total = load.get("gpu_memory_total_mb", 0)
    gpu_used = load.get("gpu_memory_used_mb", 0)

    if cpu > threshold_pct:
        logger.debug(f"CPU {cpu:.0f}% > {threshold_pct}% — not ample")
        return False
    if mem_pct > threshold_pct:
        logger.debug(f"RAM {mem_pct:.0f}% > {threshold_pct}% — not ample")
        return False
    if gpu_total > 0:
        vram_pct = (gpu_used / gpu_total) * 100
        if gpu > threshold_pct:
            logger.debug(f"GPU {gpu:.0f}% > {threshold_pct}% — not ample")
            return False
        if vram_pct > threshold_pct:
            logger.debug(f"VRAM {vram_pct:.0f}% > {threshold_pct}% — not ample")
            return False
    return True


def wait_until_safe(max_wait_minutes: int = 15, check_interval_seconds: int = 240) -> bool:
    """
    Block until system load is acceptable, or give up after max_wait_minutes.
    Returns True if safe to proceed, False if still busy after max wait.
    """
    import time as _time

    if not should_defer():
        return True  # already safe

    total_checks = (max_wait_minutes * 60) // check_interval_seconds
    for i in range(total_checks):
        logger.info(
            f"System busy — waiting {check_interval_seconds}s before retry "
            f"({i + 1}/{total_checks}, max {max_wait_minutes}min)"
        )
        _time.sleep(check_interval_seconds)
        # Clear the cache so we get a fresh reading
        try:
            os.remove(_CACHE_FILE)
        except OSError:
            pass
        if not should_defer():
            logger.info("System load dropped — proceeding.")
            return True

    logger.warning(f"System still busy after {max_wait_minutes} min — giving up.")
    return False


def load_summary() -> str:
    """Human-readable one-line load summary."""
    load = get_system_load()
    parallelism = recommended_parallelism()
    period = "night" if load["is_nighttime"] else "day"
    gpu_part = ""
    if load.get("gpu_percent", 0) > 0 or load.get("gpu_memory_total_mb", 0) > 0:
        gpu_part = (
            f"GPU: {load['gpu_percent']:.0f}% | "
            f"VRAM: {load.get('gpu_memory_free_mb', 0):.0f}MB free / "
            f"{load.get('gpu_memory_total_mb', 0):.0f}MB | "
        )
    return (
        f"CPU: {load['cpu_percent']:.0f}% | "
        f"Mem: {load['memory_available_gb']:.1f}GB free | "
        f"{gpu_part}"
        f"Load: {load['load_avg_1min']} | "
        f"Period: {period} | "
        f"Recommended parallelism: {parallelism}"
    )


_CACHE_FILE = "/tmp/system_load_cache.json"
_CACHE_TTL_SECS = 10


def _cached_oneline() -> str | None:
    """Return cached oneline result if fresh enough (<10s old)."""
    try:
        import json as _json
        stat = os.stat(_CACHE_FILE)
        if (datetime.datetime.now().timestamp() - stat.st_mtime) < _CACHE_TTL_SECS:
            with open(_CACHE_FILE, "r") as f:
                return _json.load(f).get("oneline", None)
    except Exception:
        pass
    return None


def _save_cache(result: str):
    """Cache oneline result to avoid repeated 1s CPU checks."""
    try:
        import json as _json
        with open(_CACHE_FILE, "w") as f:
            _json.dump({"oneline": result}, f)
    except Exception:
        pass


def oneline() -> str:
    """Compact one-line output for Claude Code hook. Cached for 10s."""
    cached = _cached_oneline()
    if cached:
        return cached

    load = get_system_load()
    parallelism = recommended_parallelism()
    defer = should_defer()
    period = "night" if load["is_nighttime"] else "day"
    cpu = load["cpu_percent"]
    mem = load["memory_available_gb"]

    gpu = load.get("gpu_percent", 0)
    vram_free = load.get("gpu_memory_free_mb", 0)
    gpu_part = ""
    if gpu > 0 or load.get("gpu_memory_total_mb", 0) > 0:
        gpu_part = f"GPU: {gpu:.0f}% | VRAM free: {vram_free:.0f}MB | "

    if defer:
        result = (
            f"[LOAD WARNING] CPU: {cpu:.0f}% | Mem: {mem:.1f}GB free | "
            f"{gpu_part}"
            f"Parallel: {parallelism} | Defer: YES | Period: {period} "
            f"— reduce concurrency, system is stressed"
        )
    else:
        result = (
            f"[LOAD OK] CPU: {cpu:.0f}% | Mem: {mem:.1f}GB free | "
            f"{gpu_part}"
            f"Parallel: {parallelism} | Defer: No | Period: {period}"
        )
    _save_cache(result)
    return result


if __name__ == "__main__":
    import sys
    if "--oneline" in sys.argv:
        print(oneline())
    else:
        logging.basicConfig(level=logging.INFO)
        print(load_summary())
        print(f"Should defer: {should_defer()}")
        print(f"Recommended parallelism: {recommended_parallelism()}")
