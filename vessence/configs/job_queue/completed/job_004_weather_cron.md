# Job #4: Weather Cron Job + Gemma4 Integration

Priority: 2
Status: completed
Created: 2026-04-03

## Description
Set up a 3:30am daily cron job that fetches weather data for Medford, MA and caches it. Wire gemma4 router to read the cache and answer weather questions directly without Claude.

### Components:
1. **Fetch script**: `agent_skills/fetch_weather.py` — calls Open-Meteo API (free, no key)
   - 7-day forecast: high/low temp, humidity, condition (rain/sun/cloudy/snow), wind
   - Current conditions + air quality (AQI, PM2.5, ozone)
   - Saves to `$VESSENCE_DATA_HOME/cache/weather.json`
2. **Cron job**: 3:30am ET daily via user crontab
3. **Gemma4 router**: detect weather keywords → read cache → SELF_HANDLE with weather data
4. **Location**: Medford, MA (42.4184, -71.1062)

### Prototype already working:
- Fetch script tested successfully (see /home/chieh/ambient/vessence-data/cache/weather.json)
- Open-Meteo API confirmed free and reliable

### Acceptance criteria:
- weather.json updated daily at 3:30am
- "What's the weather?" → gemma4 responds instantly with cached data
- "Will it rain tomorrow?" → gemma4 reads forecast and answers
- Falls back to Claude if weather data is stale (>24h old)
