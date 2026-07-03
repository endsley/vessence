"""Pure decision helpers for screen_dimmer.py."""
from __future__ import annotations

import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class BrightnessPlan:
    brightness: str
    reason: str


def sunset_time_from_api_response(data: dict) -> datetime.time | None:
    if data.get("status") != "OK":
        return None
    try:
        sunset_utc = datetime.datetime.fromisoformat(data["results"]["sunset"])
        return sunset_utc.astimezone().time()
    except (KeyError, TypeError, ValueError):
        return None


def connected_outputs_from_xrandr(stdout: str) -> list[str]:
    return [
        line.split()[0]
        for line in stdout.splitlines()
        if " connected" in line
    ]


def target_outputs_for_brightness(outputs: list[str], preferred_output: str) -> list[str]:
    if preferred_output in outputs:
        return [preferred_output]
    return list(outputs)


def brightness_plan(
    *,
    current_time: datetime.time,
    sunset_time: datetime.time,
    day_start_time: datetime.time,
    dim_brightness: str,
    day_brightness: str,
) -> BrightnessPlan | None:
    if current_time >= sunset_time:
        return BrightnessPlan(dim_brightness, "After sunset — dimming screen.")
    if current_time >= day_start_time:
        return BrightnessPlan(day_brightness, "After 07:00 AM and before sunset — brightening screen.")
    return None
