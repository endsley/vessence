"""Benchmark gemma4:e2b on weather routing with SCHEMA context and
High / Medium / Low labels.

Instead of injecting the full weather JSON values, we inject a short
description of what the local cache actually contains (location,
fields, time window) so the model can reject questions about fields or
locations we do not store, without getting confused by the actual
numbers. The model outputs a categorical confidence label: High,
Medium, or Low.
"""

import json
import re
import time
from pathlib import Path

import requests

MODEL = "gemma4:e2b"
OLLAMA_URL = "http://localhost:11434/api/generate"
WEATHER_PATH = Path("/home/chieh/ambient/vessence-data/cache/weather.json")


def _build_schema_description() -> str:
    data = json.loads(WEATHER_PATH.read_text())
    forecast = data["forecast"]
    first = forecast[0]
    last = forecast[-1]
    today_line = f"- Today's date: {first['date']} ({first['weekday']})"
    window_line = (
        f"- Forecast window: {first['date']} ({first['weekday']}) "
        f"through {last['date']} ({last['weekday']}) "
        f"— {len(forecast)} days total"
    )
    return (
        "Local weather cache contents:\n"
        "- Location: Medford, MA (this is the ONLY location stored; no other cities)\n"
        f"{today_line}\n"
        f"{window_line}\n"
        "- Current conditions: temperature, feels-like temperature, humidity, "
        "wind speed, sky condition (e.g. clear, overcast, drizzle)\n"
        "- Current air quality: US AQI, PM2.5, PM10, ozone\n"
        "- Daily forecast entry for each day in the window: high and low "
        "temperature, condition, precipitation amount, humidity range, wind "
        "speed, UV index\n"
        "- NOT stored: dew point, barometric pressure, wind direction, "
        "sunrise/sunset times, pollen counts, historical / past weather, "
        "weather for any city other than Medford, anything outside the "
        "forecast window above"
    )


SCHEMA_DESCRIPTION = _build_schema_description()


SYSTEM_TEMPLATE = """You are a routing classifier. Below is a description \
of what the local weather cache contains. Given a user prompt, decide \
how confident you are that the cache can directly answer it.

{schema}

Output exactly one of these three labels:
- High   = the prompt clearly asks about something the cache stores \
(right location, right time window, right field).
- Medium = plausibly a weather question for this location and time \
window, but it is unclear whether the specific field is in the cache, \
OR the prompt needs some reasoning over the stored values.
- Low    = casual small talk not asking for information, OR a question \
about the code / implementation of the weather feature, OR a request \
about a location / time / field the cache does NOT store.

User prompt: {prompt}

Respond with exactly one word: High, Medium, or Low. No explanation."""


YES_PROMPTS = [
    "What's the temperature in Medford right now?",
    "How warm is it outside?",
    "Is it cold out today?",
    "What does it feel like outside right now?",
    "What's the humidity like right now in Medford?",
    "How windy is it outside?",
    "What are the current conditions in Medford?",
    "Is the sky clear right now?",
    "What's the air quality index right now?",
    "Is the air quality good today in Medford?",
    "What's the PM2.5 level right now?",
    "How much ozone is in the air right now?",
    "What's the high temperature today?",
    "What's the low temperature tonight?",
    "Will it rain today in Medford?",
    "Is there any precipitation expected today?",
    "What's the UV index today?",
    "How humid will it get today?",
    "What's the forecast for tomorrow?",
    "Will it rain tomorrow?",
    "What's the high tomorrow in Medford?",
    "How cold will it get tomorrow night?",
    "What's the weather on April 13th?",
    "Will it rain on Monday?",
    "How much rain is expected on April 13?",
    "What's Tuesday's forecast?",
    "How hot will it get on April 14?",
    "What's the high on Wednesday in Medford?",
    "Will it be overcast on Wednesday?",
    "What's Thursday looking like?",
    "How hot will it get on April 15?",
    "Will there be rain on April 15?",
    "What's the UV index on Thursday?",
    "What's Friday's weather in Medford?",
    "Will it rain on April 16?",
    "What's Saturday's forecast?",
    "How warm will it be on April 17?",
    "What's the forecast for the next few days?",
    "Give me this week's weather.",
    "What's the hottest day this week in Medford?",
    "Which day this week has the most rain?",
    "Are we expecting any rain this week?",
    "Is it going to warm up later this week?",
    "What's the coldest night this week?",
    "How's the weather looking for the rest of the week?",
    "Will I need an umbrella tomorrow?",
    "Should I wear a jacket today?",
    "Is it warmer today than tomorrow will be?",
    "Will Thursday be warmer than today?",
    "Is it going to be sunny or overcast today?",
]

NO_SMALL_TALK = [
    "Nice weather we're having, huh.",
    "The weather's been crazy lately.",
    "I love how spring is finally here.",
    "Yesterday was such a beautiful day.",
    "Ugh, I hate this cold.",
    "Remember that blizzard last year?",
    "Weather, weather, weather, that's all anyone talks about.",
    "Good morning!",
    "Hope you're having a great day.",
    "The weather reminds me of when I was a kid.",
    "I wish it were summer already.",
    "Small talk about the weather is so boring.",
    "Weather is a fun topic for conversation starters.",
    "I like rainy days, they're cozy.",
    "Sunshine always puts me in a good mood.",
    "My grandpa used to predict weather by his knee.",
    "Climate and weather aren't the same thing, you know.",
    "Let's talk about something other than the weather.",
    "I'm going for a walk.",
    "What should I have for lunch?",
]

NO_CODE_QUESTIONS = [
    "How does the weather fetch script work?",
    "Which API are we using to get the weather data?",
    "Where is the weather cron job configured?",
    "Show me the code that pulls the forecast.",
    "How often does weather.json get refreshed?",
    "Why is weather.json stored under vessence-data/cache?",
    "Can you refactor fetch_weather.py?",
    "Add a unit test for the weather parser.",
    "How is the weather data injected into the prompt?",
    "What format does the weather JSON use?",
    "Write a function that formats the weather into a short string.",
    "Why does the weather cron log go to weather_cron.log?",
    "Can we switch the weather API to a paid provider?",
    "How do we handle errors if the weather fetch fails?",
    "Explain the schema of the weather cache file.",
]

NO_UNANSWERABLE_WEATHER = [
    "What's the weather in Tokyo right now?",
    "How's the weather in San Francisco today?",
    "Will it snow in Boston in December?",
    "What was the temperature in Medford last Tuesday?",
    "What was yesterday's high?",
    "How much did it rain last week?",
    "What's the weather going to be like in three weeks?",
    "Will there be a hurricane next month?",
    "What's the dew point right now?",
    "What direction is the wind blowing from?",
    "What's the barometric pressure right now?",
    "When is sunrise tomorrow in Medford?",
    "What time does the sun set today?",
    "What's the pollen count right now?",
    "How long will this weather pattern last into May?",
]

assert len(YES_PROMPTS) == 50
assert len(NO_SMALL_TALK) == 20
assert len(NO_CODE_QUESTIONS) == 15
assert len(NO_UNANSWERABLE_WEATHER) == 15


LABEL_RE = re.compile(r"\b(high|medium|low)\b", re.IGNORECASE)
LABEL_SCORE = {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.0}


def classify(prompt: str) -> tuple[str, float, str]:
    body = {
        "model": MODEL,
        "prompt": SYSTEM_TEMPLATE.format(schema=SCHEMA_DESCRIPTION, prompt=prompt),
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 8},
        "keep_alive": "1h",
    }
    t0 = time.perf_counter()
    r = requests.post(OLLAMA_URL, json=body, timeout=120)
    elapsed = time.perf_counter() - t0
    r.raise_for_status()
    raw = r.json().get("response", "").strip()
    m = LABEL_RE.search(raw)
    label = m.group(1).upper() if m else "?"
    return label, elapsed, raw


def main() -> None:
    cases: list[tuple[str, str, str]] = []
    for p in YES_PROMPTS:
        cases.append(("yes_answerable", p, "HIGH"))
    for p in NO_SMALL_TALK:
        cases.append(("no_small_talk", p, "LOW"))
    for p in NO_CODE_QUESTIONS:
        cases.append(("no_code", p, "LOW"))
    for p in NO_UNANSWERABLE_WEATHER:
        cases.append(("no_unanswerable", p, "LOW"))

    print(f"Model: {MODEL}  (schema-only context, High/Medium/Low output)")
    print(f"Cases: {len(cases)} (50 positive / 50 negative)\n")

    results = []
    for i, (category, prompt, gold) in enumerate(cases, 1):
        label, elapsed, raw = classify(prompt)
        results.append(
            {
                "i": i,
                "category": category,
                "prompt": prompt,
                "gold": gold,
                "label": label,
                "raw": raw,
                "elapsed": elapsed,
            }
        )
        print(
            f"[{i:3d}] {category:17s} gold={gold:6s} got={label:6s} "
            f"t={elapsed*1000:6.0f}ms  raw={raw[:16]!r:18s}  {prompt[:55]}"
        )

    total = len(results)
    valid = [r for r in results if r["label"] != "?"]
    invalid = total - len(valid)
    avg_ms = sum(r["elapsed"] for r in results) / total * 1000
    p50_ms = sorted(r["elapsed"] for r in results)[total // 2] * 1000
    p95_ms = sorted(r["elapsed"] for r in results)[int(total * 0.95)] * 1000
    total_s = sum(r["elapsed"] for r in results)

    print("\n=== speed ===")
    print(f"avg {avg_ms:.0f}ms | p50 {p50_ms:.0f}ms | p95 {p95_ms:.0f}ms "
          f"| throughput {total/total_s:.2f} req/s")
    if invalid:
        print(f"unparseable responses: {invalid}")

    print("\n=== label distribution by category ===")
    cats: dict[str, dict[str, int]] = {}
    for r in valid:
        d = cats.setdefault(r["category"], {"HIGH": 0, "MEDIUM": 0, "LOW": 0})
        d[r["label"]] += 1
    for cat, d in cats.items():
        total_cat = sum(d.values())
        print(
            f"  {cat:18s} n={total_cat:3d}  High={d['HIGH']:2d}  "
            f"Medium={d['MEDIUM']:2d}  Low={d['LOW']:2d}"
        )

    print("\n=== accuracy (strict: High=YES, Medium+Low=NO) ===")
    tp = sum(1 for r in valid if r["gold"] == "HIGH" and r["label"] == "HIGH")
    tn = sum(1 for r in valid if r["gold"] == "LOW" and r["label"] != "HIGH")
    fp = sum(1 for r in valid if r["gold"] == "LOW" and r["label"] == "HIGH")
    fn = sum(1 for r in valid if r["gold"] == "HIGH" and r["label"] != "HIGH")
    pos = tp + fn
    neg = tn + fp
    print(f"  overall   {(tp+tn)/len(valid)*100:5.1f}%")
    print(f"  positives {tp}/{pos} = {tp/pos*100:5.1f}%")
    print(f"  negatives {tn}/{neg} = {tn/neg*100:5.1f}%")

    print("\n=== accuracy (permissive: High+Medium=YES, Low=NO) ===")
    tp2 = sum(1 for r in valid if r["gold"] == "HIGH" and r["label"] in ("HIGH", "MEDIUM"))
    tn2 = sum(1 for r in valid if r["gold"] == "LOW" and r["label"] == "LOW")
    fp2 = sum(1 for r in valid if r["gold"] == "LOW" and r["label"] in ("HIGH", "MEDIUM"))
    fn2 = sum(1 for r in valid if r["gold"] == "HIGH" and r["label"] == "LOW")
    print(f"  overall   {(tp2+tn2)/len(valid)*100:5.1f}%")
    print(f"  positives {tp2}/{tp2+fn2} = {tp2/(tp2+fn2)*100:5.1f}%")
    print(f"  negatives {tn2}/{tn2+fp2} = {tn2/(tn2+fp2)*100:5.1f}%")

    misses_strict = [r for r in valid if
                     (r["gold"] == "HIGH" and r["label"] != "HIGH") or
                     (r["gold"] == "LOW" and r["label"] == "HIGH")]
    if misses_strict:
        print(f"\n=== strict misses ({len(misses_strict)}) ===")
        for r in misses_strict:
            print(f"  [{r['i']}] {r['category']:17s} gold={r['gold']:6s} "
                  f"got={r['label']:6s}  {r['prompt']}")

    out_path = Path(__file__).parent / "benchmark_gemma_weather_class_schema_results.json"
    out_path.write_text(
        json.dumps(
            {
                "model": MODEL,
                "mode": "schema_context_3label",
                "total": total,
                "avg_ms": avg_ms,
                "p50_ms": p50_ms,
                "p95_ms": p95_ms,
                "results": results,
            },
            indent=2,
        )
    )
    print(f"\nsaved: {out_path}")


if __name__ == "__main__":
    main()
