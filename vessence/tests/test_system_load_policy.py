from agent_skills import system_load
from agent_skills.system_load_policy import (
    defer_reason_for_load,
    format_load_summary,
    format_oneline,
    gpu_vram_used_percent,
    has_ample_resources_for_load,
    is_nighttime_hour,
    recommended_parallelism_for_load,
)


def _load(
    *,
    cpu=10,
    mem_gb=8,
    night=False,
    gpu=0,
    vram_free=9999,
    mem_pct=20,
    gpu_total=0,
    gpu_used=0,
):
    return {
        "cpu_percent": cpu,
        "memory_available_gb": mem_gb,
        "is_nighttime": night,
        "gpu_percent": gpu,
        "gpu_memory_free_mb": vram_free,
        "memory_percent": mem_pct,
        "gpu_memory_total_mb": gpu_total,
        "gpu_memory_used_mb": gpu_used,
        "load_avg_1min": 0.0,
    }


def test_system_load_exposes_policy_helpers_as_compatibility_aliases():
    assert system_load._is_nighttime_hour is is_nighttime_hour
    assert system_load._recommended_parallelism_for_load is recommended_parallelism_for_load
    assert system_load._defer_reason_for_load is defer_reason_for_load
    assert system_load._has_ample_resources_for_load is has_ample_resources_for_load
    assert system_load._format_load_summary is format_load_summary
    assert system_load._format_oneline is format_oneline


def test_is_nighttime_hour_handles_wrapping_and_non_wrapping_windows():
    assert is_nighttime_hour(23, 23, 6)
    assert is_nighttime_hour(5, 23, 6)
    assert not is_nighttime_hour(12, 23, 6)
    assert is_nighttime_hour(10, 9, 17)
    assert not is_nighttime_hour(18, 9, 17)


def test_recommended_parallelism_for_load_preserves_day_and_night_policy():
    assert recommended_parallelism_for_load(
        _load(mem_gb=1.5),
        max_parallel=4,
        mem_free_min_gb=2.0,
        cpu_threshold_high=60,
        cpu_threshold_med=30,
    ) == 1
    assert recommended_parallelism_for_load(
        _load(cpu=70, night=True),
        max_parallel=4,
        mem_free_min_gb=2.0,
        cpu_threshold_high=60,
        cpu_threshold_med=30,
    ) == 2
    assert recommended_parallelism_for_load(
        _load(cpu=20, night=True),
        max_parallel=4,
        mem_free_min_gb=2.0,
        cpu_threshold_high=60,
        cpu_threshold_med=30,
    ) == 4
    assert recommended_parallelism_for_load(
        _load(cpu=70),
        max_parallel=4,
        mem_free_min_gb=2.0,
        cpu_threshold_high=60,
        cpu_threshold_med=30,
    ) == 1
    assert recommended_parallelism_for_load(
        _load(cpu=40),
        max_parallel=4,
        mem_free_min_gb=2.0,
        cpu_threshold_high=60,
        cpu_threshold_med=30,
    ) == 2
    assert recommended_parallelism_for_load(
        _load(cpu=20),
        max_parallel=4,
        mem_free_min_gb=2.0,
        cpu_threshold_high=60,
        cpu_threshold_med=30,
    ) == 3


def test_defer_reason_for_load_reports_first_stress_reason():
    assert (
        defer_reason_for_load(
            _load(mem_gb=0.5),
            gpu_threshold_high=70.0,
            vram_free_min_mb=1024,
        )
        == "Deferring: critically low memory (0.5 GB)"
    )
    assert (
        defer_reason_for_load(
            _load(cpu=61),
            gpu_threshold_high=70.0,
            vram_free_min_mb=1024,
        )
        == "Deferring: CPU at 61% (threshold: 60%)"
    )
    assert (
        defer_reason_for_load(
            _load(cpu=81, night=True),
            gpu_threshold_high=70.0,
            vram_free_min_mb=1024,
        )
        == "Deferring: CPU at 81% (threshold: 80%)"
    )
    assert (
        defer_reason_for_load(
            _load(gpu=75),
            gpu_threshold_high=70.0,
            vram_free_min_mb=1024,
        )
        == "Deferring: GPU at 75% (threshold: 70.0%)"
    )
    assert (
        defer_reason_for_load(
            _load(vram_free=512),
            gpu_threshold_high=70.0,
            vram_free_min_mb=1024,
        )
        == "Deferring: VRAM free 512 MB < 1024 MB minimum"
    )
    assert defer_reason_for_load(
        _load(),
        gpu_threshold_high=70.0,
        vram_free_min_mb=1024,
    ) is None


def test_gpu_vram_used_percent_preserves_zero_total_behavior():
    assert gpu_vram_used_percent(_load(gpu_total=0, gpu_used=3000)) == 0.0
    assert gpu_vram_used_percent(_load(gpu_total=4096, gpu_used=1024)) == 25.0


def test_has_ample_resources_for_load_checks_cpu_memory_gpu_and_vram():
    assert has_ample_resources_for_load(_load())
    assert not has_ample_resources_for_load(_load(cpu=61))
    assert not has_ample_resources_for_load(_load(mem_pct=61))
    assert not has_ample_resources_for_load(_load(gpu=61, gpu_total=4096, gpu_used=1024))
    assert not has_ample_resources_for_load(_load(gpu_total=4096, gpu_used=3000))


def test_format_load_summary_includes_gpu_when_present():
    assert format_load_summary(
        _load(cpu=12, mem_gb=3.4, gpu=10, vram_free=2048, gpu_total=4096),
        3,
    ) == (
        "CPU: 12% | Mem: 3.4GB free | GPU: 10% | VRAM: 2048MB free / "
        "4096MB | Load: 0.0 | Period: day | Recommended parallelism: 3"
    )


def test_format_oneline_preserves_ok_and_warning_shapes():
    assert format_oneline(_load(cpu=12, mem_gb=3.4), 3, False) == (
        "[LOAD OK] CPU: 12% | Mem: 3.4GB free | Parallel: 3 | "
        "Defer: No | Period: day"
    )
    assert format_oneline(
        _load(cpu=81, mem_gb=3.4, night=True, gpu=10, vram_free=2048, gpu_total=4096),
        2,
        True,
    ) == (
        "[LOAD WARNING] CPU: 81% | Mem: 3.4GB free | GPU: 10% | "
        "VRAM free: 2048MB | Parallel: 2 | Defer: YES | Period: night "
        "— reduce concurrency, system is stressed"
    )
