import datetime

from agent_skills import screen_dimmer
from agent_skills.screen_dimmer_rules import (
    BrightnessPlan,
    brightness_plan,
    connected_outputs_from_xrandr,
    sunset_time_from_api_response,
    target_outputs_for_brightness,
)


def test_screen_dimmer_exposes_rule_helpers():
    assert screen_dimmer._brightness_plan is brightness_plan
    assert screen_dimmer._connected_outputs_from_xrandr is connected_outputs_from_xrandr
    assert screen_dimmer._sunset_time_from_api_response is sunset_time_from_api_response
    assert screen_dimmer._target_outputs_for_brightness is target_outputs_for_brightness


def test_connected_outputs_from_xrandr_preserves_connected_output_filter():
    stdout = """
DP-1 connected primary 3840x2160+0+0
HDMI-1 disconnected
eDP-1 connected 1920x1080+3840+0
Virtual-1 unknown connection
"""
    assert connected_outputs_from_xrandr(stdout) == ["DP-1", "eDP-1"]


def test_target_outputs_prefers_configured_output_and_falls_back_to_all():
    assert target_outputs_for_brightness(["DP-1", "eDP-1"], "DP-1") == ["DP-1"]
    assert target_outputs_for_brightness(["HDMI-1", "eDP-1"], "DP-1") == ["HDMI-1", "eDP-1"]
    assert target_outputs_for_brightness([], "DP-1") == []


def test_brightness_plan_matches_time_windows():
    day_start = datetime.time(7, 0)
    sunset = datetime.time(19, 30)

    assert brightness_plan(
        current_time=datetime.time(20, 0),
        sunset_time=sunset,
        day_start_time=day_start,
        dim_brightness="0.3",
        day_brightness="0.8",
    ) == BrightnessPlan("0.3", "After sunset — dimming screen.")

    assert brightness_plan(
        current_time=datetime.time(7, 0),
        sunset_time=sunset,
        day_start_time=day_start,
        dim_brightness="0.3",
        day_brightness="0.8",
    ) == BrightnessPlan("0.8", "After 07:00 AM and before sunset — brightening screen.")

    assert brightness_plan(
        current_time=datetime.time(6, 59),
        sunset_time=sunset,
        day_start_time=day_start,
        dim_brightness="0.3",
        day_brightness="0.8",
    ) is None


def test_sunset_time_from_api_response_handles_ok_and_invalid_payloads():
    assert sunset_time_from_api_response({"status": "INVALID_REQUEST"}) is None
    assert sunset_time_from_api_response({"status": "OK", "results": {}}) is None

    parsed = sunset_time_from_api_response(
        {"status": "OK", "results": {"sunset": "2026-07-02T19:30:00-04:00"}}
    )
    assert parsed is not None
    assert parsed.hour == 19
    assert parsed.minute == 30
