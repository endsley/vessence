#!/usr/bin/env python3
"""
screen_dimmer.py — Dims the primary monitor after sunset for zip code 02155.

Uses sunrise-sunset.org API with hardcoded coordinates for Medford, MA (02155).
If after sunset → sets DP-1 brightness to 30% via xrandr.
"""
import requests
import datetime
import subprocess

# Medford, MA 02155 — fixed coordinates, no geocoding needed
LAT = 42.4184
LON = -71.1062
DISPLAY_OUTPUT = "DP-1"
DIM_BRIGHTNESS = "0.3"


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


def dim_screen(output):
    try:
        subprocess.run(
            ['xrandr', '--output', output, '--brightness', DIM_BRIGHTNESS],
            check=True
        )
        print(f"Screen dimmed to {DIM_BRIGHTNESS} on {output}.")
    except FileNotFoundError:
        print("Error: 'xrandr' not found.")
    except subprocess.CalledProcessError as e:
        print(f"xrandr error on {output}: {e}")


def main():
    sunset_time = get_sunset_time(LAT, LON)
    if not sunset_time:
        print("Could not retrieve sunset time. No action taken.")
        return

    current_time = datetime.datetime.now().time()
    print(f"Sunset: {sunset_time.strftime('%I:%M %p')}  |  Now: {current_time.strftime('%I:%M %p')}")

    if current_time <= sunset_time:
        print("Before sunset — no action taken.")
        return

    print("After sunset — dimming screen.")
    outputs = get_connected_outputs()
    if not outputs:
        print("No connected xrandr outputs found.")
        return

    # Dim the configured output if connected, otherwise dim all connected outputs
    if DISPLAY_OUTPUT in outputs:
        dim_screen(DISPLAY_OUTPUT)
    else:
        print(f"'{DISPLAY_OUTPUT}' not found. Connected outputs: {outputs}. Dimming all.")
        for out in outputs:
            dim_screen(out)


if __name__ == "__main__":
    main()
