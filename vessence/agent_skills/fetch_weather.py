#!/usr/bin/env python3
"""Fetch 7-day weather forecast + air quality for Medford, MA.

Saves to $VESSENCE_DATA_HOME/cache/weather.json.
Run daily via cron at 3:30am ET.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import requests

# Location from .env or defaults to Medford, MA
LAT = float(os.environ.get("WEATHER_LAT", "42.4184"))
LON = float(os.environ.get("WEATHER_LON", "-71.1062"))
LOCATION = os.environ.get("WEATHER_LOCATION", "Medford, MA")

VESSENCE_DATA_HOME = Path(os.environ.get(
    "VESSENCE_DATA_HOME",
    os.path.expanduser("~/ambient/vessence-data"),
))
CACHE_DIR = VESSENCE_DATA_HOME / "cache"
OUTPUT_PATH = CACHE_DIR / "weather.json"

WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}


def fetch_weather() -> dict:
    weather = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": LAT, "longitude": LON,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode,"
                     "sunrise,sunset,uv_index_max,relative_humidity_2m_max,"
                     "relative_humidity_2m_min,wind_speed_10m_max",
            "current": "temperature_2m,relative_humidity_2m,weather_code,"
                       "wind_speed_10m,apparent_temperature",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "America/New_York",
            "forecast_days": 7,
        },
        timeout=15,
    ).json()

    aqi = requests.get(
        "https://air-quality-api.open-meteo.com/v1/air-quality",
        params={
            "latitude": LAT, "longitude": LON,
            "current": "us_aqi,pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,ozone",
            "timezone": "America/New_York",
        },
        timeout=15,
    ).json()

    result = {
        "location": LOCATION,
        "fetched": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "current": {
            "temperature": f"{weather['current']['temperature_2m']}°F",
            "feels_like": f"{weather['current']['apparent_temperature']}°F",
            "humidity": f"{weather['current']['relative_humidity_2m']}%",
            "wind": f"{weather['current']['wind_speed_10m']} mph",
            "condition": WMO_CODES.get(weather["current"]["weather_code"], "Unknown"),
        },
        "air_quality": {
            "us_aqi": aqi["current"]["us_aqi"],
            "pm2_5": f"{aqi['current']['pm2_5']} µg/m³",
            "pm10": f"{aqi['current']['pm10']} µg/m³",
            "ozone": f"{aqi['current']['ozone']} µg/m³",
        },
        "forecast": [],
    }

    for i, date in enumerate(weather["daily"]["time"]):
        result["forecast"].append({
            "date": date,
            "high": f"{weather['daily']['temperature_2m_max'][i]}°F",
            "low": f"{weather['daily']['temperature_2m_min'][i]}°F",
            "condition": WMO_CODES.get(weather["daily"]["weathercode"][i], "Unknown"),
            "precipitation": f"{weather['daily']['precipitation_sum'][i]} in",
            "humidity": f"{weather['daily']['relative_humidity_2m_min'][i]}-{weather['daily']['relative_humidity_2m_max'][i]}%",
            "wind": f"{weather['daily']['wind_speed_10m_max'][i]} mph",
            "uv_index": weather["daily"]["uv_index_max"][i],
        })

    return result


def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    data = fetch_weather()
    OUTPUT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"Weather saved to {OUTPUT_PATH} ({len(data['forecast'])} day forecast)")


if __name__ == "__main__":
    main()
