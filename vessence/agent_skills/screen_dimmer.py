#!/usr/bin/env python3
"""
screen_dimmer.py — Adjusts the primary monitor brightness for zip code 02155.

Uses sunrise-sunset.org API with hardcoded coordinates for Medford, MA (02155).
If after sunset → sets DP-1 brightness to 30% via xrandr.
If after 7:00 AM and before sunset → sets DP-1 brightness to 80%.
"""
import requests
import datetime
import subprocess

# Medford, MA 02155 — fixed coordinates, no geocoding needed
LAT = 42.4184
LON = -71.1062
DISPLAY_OUTPUT = "DP-1"
DIM_BRIGHTNESS = "0.3"
DAY_BRIGHTNESS = "0.8"
DAY_START_TIME = datetime.time(hour=7, minute=0)


def get_sunset_time(lat, lon):
    try:
        response = requests.get(
            f"https://api.sunrise-sunset.org/json?lat={lat}&lng={lon}&formatted=0",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        if data['status'] == 'OK':
            sunset_utc_str = data['results']['sunset']
            sunset_utc = datetime.datetime.fromisoformat(sunset_utc_str)
            return sunset_utc.astimezone().time()
        print(f"API returned non-OK status: {data['status']}")
        return None
    except Exception as e:
        print(f"Error fetching sunset time: {e}")
        return None


def get_connected_outputs():
    """Return list of connected xrandr output names."""
    try:
        result = subprocess.run(['xrandr'], capture_output=True, text=True, check=True)
        return [
            line.split()[0]
            for line in result.stdout.splitlines()
            if ' connected' in line
        ]
    except Exception as e:
        print(f"Error querying xrandr outputs: {e}")
        return []


def set_screen_brightness(output, brightness):
    try:
        subprocess.run(
            ['xrandr', '--output', output, '--brightness', brightness],
            check=True
        )
        print(f"Screen brightness set to {brightness} on {output}.")
    except FileNotFoundError:
        print("Error: 'xrandr' not found.")
    except subprocess.CalledProcessError as e:
        print(f"xrandr error on {output}: {e}")


def apply_brightness(brightness, reason, outputs):
    print(reason)

    if DISPLAY_OUTPUT in outputs:
        set_screen_brightness(DISPLAY_OUTPUT, brightness)
        return

    print(f"'{DISPLAY_OUTPUT}' not found. Connected outputs: {outputs}. Applying brightness to all.")
    for out in outputs:
        set_screen_brightness(out, brightness)


def main():
    sunset_time = get_sunset_time(LAT, LON)
    if not sunset_time:
        print("Could not retrieve sunset time. No action taken.")
        return

    current_time = datetime.datetime.now().time()
    print(f"Sunset: {sunset_time.strftime('%I:%M %p')}  |  Now: {current_time.strftime('%I:%M %p')}")
    outputs = get_connected_outputs()
    if not outputs:
        print("No connected xrandr outputs found.")
        return

    if current_time >= sunset_time:
        apply_brightness(DIM_BRIGHTNESS, "After sunset — dimming screen.", outputs)
        return

    if current_time >= DAY_START_TIME:
        apply_brightness(DAY_BRIGHTNESS, "After 07:00 AM and before sunset — brightening screen.", outputs)
        return

    print("Before 07:00 AM and before sunset — no action taken.")


if __name__ == "__main__":
    main()
