"""Pure resource policy helpers for system_load.py."""
from __future__ import annotations


def is_nighttime_hour(hour: int, night_start_hour: int, night_end_hour: int) -> bool:
    if night_start_hour > night_end_hour:
        return hour >= night_start_hour or hour < night_end_hour
    return night_start_hour <= hour < night_end_hour


def recommended_parallelism_for_load(
    load: dict,
    *,
    max_parallel: int,
    mem_free_min_gb: float,
    cpu_threshold_high: float,
    cpu_threshold_med: float,
) -> int:
    cpu = load["cpu_percent"]
    mem_gb = load["memory_available_gb"]
    if mem_gb < mem_free_min_gb:
        return 1
    if load["is_nighttime"]:
        if cpu > cpu_threshold_high:
            return max(1, max_parallel // 2)
        return max_parallel
    if cpu > cpu_threshold_high:
        return 1
    if cpu > cpu_threshold_med:
        return min(2, max_parallel)
    return min(3, max_parallel)


def defer_reason_for_load(
    load: dict,
    *,
    gpu_threshold_high: float,
    vram_free_min_mb: float,
) -> str | None:
    mem_gb = load["memory_available_gb"]
    if mem_gb < 1.0:
        return f"Deferring: critically low memory ({mem_gb:.1f} GB)"

    cpu = load["cpu_percent"]
    threshold = 80 if load["is_nighttime"] else 60
    if cpu > threshold:
        return f"Deferring: CPU at {cpu:.0f}% (threshold: {threshold}%)"

    gpu = load.get("gpu_percent", 0)
    if gpu > gpu_threshold_high:
        return f"Deferring: GPU at {gpu:.0f}% (threshold: {gpu_threshold_high}%)"

    gpu_mem_free = load.get("gpu_memory_free_mb", 9999)
    if gpu_mem_free < vram_free_min_mb:
        return f"Deferring: VRAM free {gpu_mem_free:.0f} MB < {vram_free_min_mb:.0f} MB minimum"

    return None


def gpu_vram_used_percent(load: dict) -> float:
    gpu_total = load.get("gpu_memory_total_mb", 0)
    if gpu_total <= 0:
        return 0.0
    return (load.get("gpu_memory_used_mb", 0) / gpu_total) * 100


def has_ample_resources_for_load(load: dict, threshold_pct: float = 60) -> bool:
    if load["cpu_percent"] > threshold_pct:
        return False
    if load["memory_percent"] > threshold_pct:
        return False
    gpu_total = load.get("gpu_memory_total_mb", 0)
    if gpu_total > 0:
        if load.get("gpu_percent", 0) > threshold_pct:
            return False
        if gpu_vram_used_percent(load) > threshold_pct:
            return False
    return True


def _gpu_summary_part(load: dict, *, oneline: bool = False) -> str:
    if load.get("gpu_percent", 0) <= 0 and load.get("gpu_memory_total_mb", 0) <= 0:
        return ""
    if oneline:
        return (
            f"GPU: {load.get('gpu_percent', 0):.0f}% | "
            f"VRAM free: {load.get('gpu_memory_free_mb', 0):.0f}MB | "
        )
    return (
        f"GPU: {load.get('gpu_percent', 0):.0f}% | "
        f"VRAM: {load.get('gpu_memory_free_mb', 0):.0f}MB free / "
        f"{load.get('gpu_memory_total_mb', 0):.0f}MB | "
    )


def format_load_summary(load: dict, parallelism: int) -> str:
    period = "night" if load["is_nighttime"] else "day"
    return (
        f"CPU: {load['cpu_percent']:.0f}% | "
        f"Mem: {load['memory_available_gb']:.1f}GB free | "
        f"{_gpu_summary_part(load)}"
        f"Load: {load['load_avg_1min']} | "
        f"Period: {period} | "
        f"Recommended parallelism: {parallelism}"
    )


def format_oneline(load: dict, parallelism: int, defer: bool) -> str:
    period = "night" if load["is_nighttime"] else "day"
    status = "WARNING" if defer else "OK"
    defer_text = "YES" if defer else "No"
    suffix = " — reduce concurrency, system is stressed" if defer else ""
    return (
        f"[LOAD {status}] CPU: {load['cpu_percent']:.0f}% | "
        f"Mem: {load['memory_available_gb']:.1f}GB free | "
        f"{_gpu_summary_part(load, oneline=True)}"
        f"Parallel: {parallelism} | Defer: {defer_text} | Period: {period}"
        f"{suffix}"
    )
