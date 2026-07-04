import pytest

from agent_skills import fetch_weather
from agent_skills.weather_payload_helpers import (
    POLLEN_LABELS,
    air_quality_payload,
    current_weather_payload,
    forecast_day_payload,
    forecast_payload,
    pollen_payload,
    weather_cache_payload,
)


def test_fetch_weather_exposes_pollen_labels_alias():
    assert fetch_weather._POLLEN_LABELS is POLLEN_LABELS


def test_pollen_payload_maps_indices_and_defaults_missing_values():
    assert pollen_payload({"treeIndex": 1, "grassIndex": 4, "weedIndex": 9}) == {
        "tree": "Very Low",
        "grass": "High",
        "weed": "Unknown",
        "tree_index": 1,
        "grass_index": 4,
        "weed_index": 9,
    }
    assert pollen_payload({}) == {
        "tree": "None",
        "grass": "None",
        "weed": "None",
        "tree_index": 0,
        "grass_index": 0,
        "weed_index": 0,
    }
    with pytest.raises(ValueError):
        pollen_payload({"treeIndex": "bad"})


def test_weather_payload_section_builders_preserve_units_and_unknown_codes():
    weather = {
        "current": {
            "temperature_2m": 72,
            "apparent_temperature": 74,
            "relative_humidity_2m": 55,
            "wind_speed_10m": 8,
            "weather_code": 1,
        },
        "daily": {
            "time": ["2026-07-02", "2026-07-03"],
            "temperature_2m_max": [80, 81],
            "temperature_2m_min": [62, 63],
            "weathercode": [0, 999],
            "precipitation_sum": [0.1, 0],
            "relative_humidity_2m_min": [40, 41],
            "relative_humidity_2m_max": [70, 71],
            "wind_speed_10m_max": [12, 13],
            "uv_index_max": [7, 8],
        },
    }
    aqi = {"current": {"us_aqi": 42, "pm2_5": 3.2, "pm10": 7.1, "ozone": 90}}

    assert current_weather_payload(weather, {1: "Mainly clear"}) == {
        "temperature": "72°F",
        "feels_like": "74°F",
        "humidity": "55%",
        "wind": "8 mph",
        "condition": "Mainly clear",
    }
    assert air_quality_payload(aqi) == {
        "us_aqi": 42,
        "pm2_5": "3.2 µg/m³",
        "pm10": "7.1 µg/m³",
        "ozone": "90 µg/m³",
    }
    assert forecast_day_payload(weather["daily"], 1, wmo_codes={0: "Clear sky"}) == {
        "date": "2026-07-03",
        "weekday": "Friday",
        "high": "81°F",
        "low": "63°F",
        "condition": "Unknown",
        "precipitation": "0 in",
        "humidity": "41-71%",
        "wind": "13 mph",
        "uv_index": 8,
    }
    assert len(forecast_payload(weather, {0: "Clear sky"})) == 2


def test_weather_cache_payload_builds_cached_weather_json_shape():
    weather = {
        "current": {
            "temperature_2m": 72,
            "apparent_temperature": 74,
            "relative_humidity_2m": 55,
            "wind_speed_10m": 8,
            "weather_code": 1,
        },
        "daily": {
            "time": ["2026-07-02", "2026-07-03"],
            "temperature_2m_max": [80, 81],
            "temperature_2m_min": [62, 63],
            "weathercode": [0, 999],
            "precipitation_sum": [0.1, 0],
            "relative_humidity_2m_min": [40, 41],
            "relative_humidity_2m_max": [70, 71],
            "wind_speed_10m_max": [12, 13],
            "uv_index_max": [7, 8],
        },
    }
    aqi = {
        "current": {
            "us_aqi": 42,
            "pm2_5": 3.2,
            "pm10": 7.1,
            "ozone": 90,
        }
    }

    payload = weather_cache_payload(
        weather,
        aqi,
        {"tree": "Low"},
        location="Medford, MA",
        fetched="2026-07-02 08:30",
        wmo_codes={0: "Clear sky", 1: "Mainly clear"},
    )

    assert payload["location"] == "Medford, MA"
    assert payload["fetched"] == "2026-07-02 08:30"
    assert payload["current"] == {
        "temperature": "72°F",
        "feels_like": "74°F",
        "humidity": "55%",
        "wind": "8 mph",
        "condition": "Mainly clear",
    }
    assert payload["air_quality"] == {
        "us_aqi": 42,
        "pm2_5": "3.2 µg/m³",
        "pm10": "7.1 µg/m³",
        "ozone": "90 µg/m³",
    }
    assert payload["pollen"] == {"tree": "Low"}
    assert payload["forecast"] == [
        {
            "date": "2026-07-02",
            "weekday": "Thursday",
            "high": "80°F",
            "low": "62°F",
            "condition": "Clear sky",
            "precipitation": "0.1 in",
            "humidity": "40-70%",
            "wind": "12 mph",
            "uv_index": 7,
        },
        {
            "date": "2026-07-03",
            "weekday": "Friday",
            "high": "81°F",
            "low": "63°F",
            "condition": "Unknown",
            "precipitation": "0 in",
            "humidity": "41-71%",
            "wind": "13 mph",
            "uv_index": 8,
        },
    ]


def test_weather_cache_payload_omits_empty_pollen_block():
    payload = weather_cache_payload(
        {
            "current": {
                "temperature_2m": 1,
                "apparent_temperature": 2,
                "relative_humidity_2m": 3,
                "wind_speed_10m": 4,
                "weather_code": 5,
            },
            "daily": {
                "time": [],
                "temperature_2m_max": [],
                "temperature_2m_min": [],
                "weathercode": [],
                "precipitation_sum": [],
                "relative_humidity_2m_min": [],
                "relative_humidity_2m_max": [],
                "wind_speed_10m_max": [],
                "uv_index_max": [],
            },
        },
        {"current": {"us_aqi": 1, "pm2_5": 2, "pm10": 3, "ozone": 4}},
        {},
        location="Medford, MA",
        fetched="now",
        wmo_codes={},
    )

    assert "pollen" not in payload
