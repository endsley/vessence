"""Benchmark gemma4:e2b on weather-class confidence-score classification.

Task: given the cached weather.json injected as context, ask the model
to output a confidence score in [0.0, 1.0] for the question:
"Given the weather information I currently have, can I directly answer
the prompt?"

We test four kinds of prompts:
  - answerable weather questions (gold = 1.0)
  - casual weather small talk / non-questions (gold = 0.0)
  - questions about the code that produces the weather feature (gold = 0.0)
  - weather questions our data cannot answer, e.g. other cities, past
    days, far future, or fields we don't store (gold = 0.0)

Output: average speed, confidence distributions per category, and
accuracy at several thresholds so we can pick the best cutoff.
"""

import json
import re
import time
from pathlib import Path

import requests

MODEL = "gemma4:e2b"
OLLAMA_URL = "http://localhost:11434/api/generate"
WEATHER_PATH = Path("/home/chieh/ambient/vessence-data/cache/weather.json")


SYSTEM_TEMPLATE = """You are a routing classifier. You are given the weather \
information the system currently has cached, and a user prompt. Your job is \
to output a single confidence score between 0.00 and 1.00 for the question: \
given ONLY this weather information, can the assistant directly answer the \
user's prompt?

Scoring guidance:
- 1.00 = the prompt is a weather question AND the cached data clearly \
contains the specific answer (location, date range, and field).
- 0.00 = the prompt is casual small talk not asking for information, OR \
is about the code/implementation of the weather feature, OR asks about \
a location, date, or field the cached data does not cover.
- Use intermediate values when you are unsure.

Weather information (JSON):
{weather}

User prompt: {prompt}

Respond with exactly one decimal number between 0.00 and 1.00. \
No words, no explanation. Just the number."""


# 50 YES — questions the cached data (Medford MA, today + 7-day forecast,
# current temp/humidity/wind/condition/feels-like, AQI) can directly answer.
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

NO_PROMPTS = NO_SMALL_TALK + NO_CODE_QUESTIONS + NO_UNANSWERABLE_WEATHER
assert len(YES_PROMPTS) == 50
assert len(NO_PROMPTS) == 50


SCORE_RE = re.compile(r"([01](?:\.\d+)?|0?\.\d+)")


def classify(weather_str: str, prompt: str) -> tuple[float, float, str]:
    body = {
        "model": MODEL,
        "prompt": SYSTEM_TEMPLATE.format(weather=weather_str, prompt=prompt),
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 16},
        "keep_alive": "1h",
    }
    t0 = time.perf_counter()
    r = requests.post(OLLAMA_URL, json=body, timeout=120)
    elapsed = time.perf_counter() - t0
    r.raise_for_status()
    raw = r.json().get("response", "").strip()
    m = SCORE_RE.search(raw)
    score = float(m.group(1)) if m else float("nan")
    if score == score:
        score = max(0.0, min(1.0, score))
    return score, elapsed, raw


def main() -> None:
    weather_data = json.loads(WEATHER_PATH.read_text())
    weather_str = json.dumps(weather_data, indent=2)

    cases: list[tuple[str, str, float]] = []
    for p in YES_PROMPTS:
        cases.append(("yes_answerable", p, 1.0))
    for p in NO_SMALL_TALK:
        cases.append(("no_small_talk", p, 0.0))
    for p in NO_CODE_QUESTIONS:
        cases.append(("no_code", p, 0.0))
    for p in NO_UNANSWERABLE_WEATHER:
        cases.append(("no_unanswerable", p, 0.0))

    print(f"Model: {MODEL}")
    print(f"Cases: {len(cases)} (50 positive / 50 negative)\n")

    results = []
    for i, (category, prompt, gold) in enumerate(cases, 1):
        score, elapsed, raw = classify(weather_str, prompt)
        results.append(
            {
                "i": i,
                "category": category,
                "prompt": prompt,
                "gold": gold,
                "score": score,
                "raw": raw,
                "elapsed": elapsed,
            }
        )
        print(
            f"[{i:3d}] {category:17s} gold={gold:.1f} score={score:.2f} "
            f"t={elapsed*1000:6.0f}ms  raw={raw[:20]!r:22s}  {prompt[:55]}"
        )

    total = len(results)
    valid = [r for r in results if r["score"] == r["score"]]
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

    print("\n=== confidence distribution by category ===")
    cats: dict[str, list[dict]] = {}
    for r in valid:
        cats.setdefault(r["category"], []).append(r)
    for cat, rs in cats.items():
        scores = sorted(r["score"] for r in rs)
        mean = sum(scores) / len(scores)
        median = scores[len(scores) // 2]
        lo, hi = scores[0], scores[-1]
        print(f"  {cat:18s} n={len(rs):3d}  mean={mean:.2f}  median={median:.2f}  "
              f"min={lo:.2f}  max={hi:.2f}")

    print("\n=== accuracy at threshold (predict YES if score >= T) ===")
    print("  thresh | overall | pos (yes) | neg (no)")
    for t in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        tp = sum(1 for r in valid if r["gold"] == 1.0 and r["score"] >= t)
        tn = sum(1 for r in valid if r["gold"] == 0.0 and r["score"] < t)
        fp = sum(1 for r in valid if r["gold"] == 0.0 and r["score"] >= t)
        fn = sum(1 for r in valid if r["gold"] == 1.0 and r["score"] < t)
        pos = tp + fn
        neg = tn + fp
        overall = (tp + tn) / len(valid) * 100
        pos_acc = tp / pos * 100 if pos else 0
        neg_acc = tn / neg * 100 if neg else 0
        print(f"   {t:.2f}  |  {overall:5.1f}% |  {pos_acc:5.1f}%   |  {neg_acc:5.1f}%")

    best_t, best_acc = max(
        (
            (
                t,
                sum(
                    1
                    for r in valid
                    if (r["gold"] == 1.0 and r["score"] >= t)
                    or (r["gold"] == 0.0 and r["score"] < t)
                )
                / len(valid),
            )
            for t in [i / 100 for i in range(1, 100)]
        ),
        key=lambda x: x[1],
    )
    print(f"\nbest threshold (fine sweep): {best_t:.2f} -> {best_acc*100:.1f}% accuracy")

    out_path = Path(__file__).parent / "benchmark_gemma_weather_class_results.json"
    out_path.write_text(
        json.dumps(
            {
                "model": MODEL,
                "total": total,
                "avg_ms": avg_ms,
                "p50_ms": p50_ms,
                "p95_ms": p95_ms,
                "best_threshold": best_t,
                "best_accuracy": best_acc,
                "results": results,
            },
            indent=2,
        )
    )
    print(f"\nsaved: {out_path}")


if __name__ == "__main__":
    main()
