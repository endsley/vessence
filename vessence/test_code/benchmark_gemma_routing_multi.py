"""Multi-class routing benchmark for gemma4:e2b.

Two classes: weather and playlist. Each class has a schema block that
describes what the local cache/store actually contains (no raw values
injected). The model outputs one line in the format:

    <class>:<confidence>

Where <class> is one of {weather, playlist, none} and <confidence> is
one of {High, Medium, Low}.

Label meanings (same idea as the single-class schema benchmark):
  High   = answer is a single-field lookup against the class's store;
           phrasing the value in natural language still counts as High.
  Medium = the prompt is clearly about this class, but answering needs
           reasoning over multiple stored values OR the specific field
           / location / time is NOT in the store.
  Low    = the prompt is not asking for information from this class at
           all (small talk, code questions, unrelated requests).

Gold labels reflect the new Low definition: "unanswerable weather" and
"unanswerable playlist" questions are still weather / playlist intent,
so their gold is Medium (not Low).
"""

import json
import os
import re
import time
from pathlib import Path

import requests

MODEL = os.environ.get("BENCH_MODEL", "gemma4:e2b")
OLLAMA_URL = "http://localhost:11434/api/generate"
WEATHER_PATH = Path("/home/chieh/ambient/vessence-data/cache/weather.json")


def _build_weather_block() -> str:
    data = json.loads(WEATHER_PATH.read_text())
    forecast = data["forecast"]
    first, last = forecast[0], forecast[-1]
    return (
        "[weather]\n"
        "Local weather cache contents:\n"
        "- Location: Medford, MA (ONLY location stored)\n"
        f"- Today's date: {first['date']} ({first['weekday']})\n"
        f"- Forecast window: {first['date']} ({first['weekday']}) "
        f"through {last['date']} ({last['weekday']}) — {len(forecast)} days\n"
        "- Current conditions: temperature, feels-like, humidity, "
        "wind speed, sky condition\n"
        "- Current air quality: US AQI, PM2.5, PM10, ozone\n"
        "- Daily forecast per day: high, low, condition, precipitation, "
        "humidity range, wind, UV index\n"
        "- NOT stored: dew point, barometric pressure, wind direction, "
        "sunrise/sunset, pollen, past weather, other cities, beyond the "
        "forecast window"
    )


MUSIC_PLAY_BLOCK = (
    "[music play]\n"
    "This class handles requests to START PLAYING music from the user's "
    "local library. The library contains audio files organized into "
    "folders (each folder is effectively a natural playlist), plus a "
    "song registry that maps titles, artists, and nicknames to files.\n"
    "- Pick this class ONLY when the user wants music to actually start "
    "playing (playback action).\n"
    "- Example intents that belong here: play a specific song, play a "
    "playlist or folder, put on some music, shuffle a set, resume playback.\n"
    "- DOES NOT handle: questions ABOUT songs or playlists (how many "
    "songs, when was it added, who is the artist). Those go to 'others'.\n"
    "- DOES NOT handle: questions about music outside the user's library "
    "(Billboard, Spotify, lyrics, release dates). Those go to 'others'."
)


SYSTEM_TEMPLATE = """You are a routing classifier. Below are the classes \
the system can serve. For each class, you are told what its local store \
actually contains.

{weather_block}

{music_play_block}

Given a user prompt, pick the SINGLE best-matching class and rate how \
confident you are that this is the right class for routing the prompt. \
Output exactly one line in this format:

    <class>:<confidence>

Where:
- <class> is one of: weather, music play, others
- <confidence> is one of: High, Medium, Low

Confidence guidance:
- High   = you are sure this is the right class AND the class's store \
can directly answer the prompt (a single-field lookup; phrasing a raw \
value in natural language still counts).
- Medium = you are sure this is the right class, but answering needs \
reasoning across multiple stored values OR the specific location, date, \
or field may not be in the store.
- Low    = you are picking this class only as a fallback; the prompt \
does not really ask for information from any of the known classes.

Use "others:Low" when the prompt is not asking for weather information \
and not asking for music / playlist information — for example small \
talk, unrelated questions, or questions about the code / implementation \
of these features.

IMPORTANT: containing a topic word is not the same as asking about it. \
"Nice weather we're having" mentions weather but is small talk, not a \
question. "Explain the playlist schema" mentions playlists but is a \
code question. Both are "others:Low".

Examples:
- "What's the temperature in Medford right now?" -> weather:High
- "Will it rain tomorrow?" -> weather:High
- "What was the temperature last Tuesday?" -> weather:Medium
- "Play Bohemian Rhapsody" -> music play:High
- "Put on some music" -> music play:High
- "Play my chill playlist" -> music play:High
- "I want to listen to something relaxing" -> music play:High
- "What playlists do I have?" -> others:Low
- "How many songs are in my workout playlist?" -> others:Low
- "Who is on the Billboard Hot 100?" -> others:Low
- "When was Bohemian Rhapsody released?" -> others:Low
- "Nice weather we're having, huh." -> others:Low
- "Ugh, I hate this cold." -> others:Low
- "The weather's been crazy lately." -> others:Low
- "My grandpa used to predict weather by his knee." -> others:Low
- "I'm going for a walk." -> others:Low
- "Good morning!" -> others:Low
- "How does the weather fetch script work?" -> others:Low

User prompt: {prompt}

Respond with exactly one line in the format <class>:<confidence>. \
No explanation."""


WEATHER_ANSWERABLE = [
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

WEATHER_UNANSWERABLE = [
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

MUSIC_PLAY_ACTIONS = [
    "Play Bohemian Rhapsody",
    "Put on some music",
    "Play my chill playlist",
    "Start playing the piano folder",
    "Shuffle my workout songs",
    "Play something relaxing",
    "Queue up Alex Ubago",
    "Can you play the Polish song?",
    "I want to listen to Brazilian music",
    "Start my morning playlist",
    "Play the Doc McStuffins theme",
    "Put on the Emily Songs folder",
    "Play some Chinese music",
    "Resume my last playlist",
    "Play a random song",
    "I'd like to hear Bachata",
    "Play the sleep relax sounds",
    "Play some music for me",
    "Start the Encanto playlist",
    "Put on Baby Sleep",
]

# Previously "playlist_answerable" — now these are OTHERS because they
# ask ABOUT songs/playlists rather than requesting playback.
OTHERS_MUSIC_INFO = [
    "What playlists do I have?",
    "List all my playlists.",
    "How many playlists have I created?",
    "Do I have a playlist called Chill?",
    "What's in my workout playlist?",
    "Show me the songs in my study playlist.",
    "How many songs are in my morning playlist?",
    "Which playlist has the most songs?",
    "What was the last song I added to my favorites?",
    "When did I create my road trip playlist?",
    "Who is the artist of the third song in my chill playlist?",
    "How long is my workout playlist in total?",
    "Is 'Bohemian Rhapsody' in any of my playlists?",
    "What are the first five songs in my focus playlist?",
    "Do I have any empty playlists?",
]

OTHERS_MUSIC_EXTERNAL = [
    "What are the top trending songs on Spotify right now?",
    "When was Blinding Lights released?",
    "Who produced Taylor Swift's latest album?",
    "What's the most popular playlist on Apple Music this week?",
    "Show me the lyrics to Bohemian Rhapsody.",
    "When did The Beatles release Abbey Road?",
    "Who is currently on the Billboard Hot 100?",
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
    "Can you refactor fetch_weather.py?",
    "Add a unit test for the weather parser.",
    "How does the playlist essence save data?",
    "Where are playlist JSON files stored on disk?",
    "Show me the code for the playlist player view.",
    "How does the playlist essence integrate with Life Librarian?",
    "Write a function that formats a playlist into JSON.",
    "How do we handle errors if the weather fetch fails?",
    "Explain the playlist data schema.",
    "What format does the weather JSON use?",
]

WEATHER_BLOCK = _build_weather_block()
PROMPT_TEMPLATE_FULL = SYSTEM_TEMPLATE.replace("{weather_block}", WEATHER_BLOCK) \
                                     .replace("{music_play_block}", MUSIC_PLAY_BLOCK)


RESP_RE = re.compile(
    r"\b(weather|music\s*play|others|playlist|none)\s*[:=]?\s*(high|medium|low)\b",
    re.IGNORECASE,
)


def _normalize_class(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    if s in ("playlist", "music", "music play", "musicplay"):
        return "music play"
    if s in ("none", "other", "others"):
        return "others"
    return s


def classify(prompt: str) -> tuple[str, str, float, str]:
    body = {
        "model": MODEL,
        "prompt": PROMPT_TEMPLATE_FULL.replace("{prompt}", prompt),
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 12},
        "keep_alive": "1h",
    }
    t0 = time.perf_counter()
    r = requests.post(OLLAMA_URL, json=body, timeout=120)
    elapsed = time.perf_counter() - t0
    r.raise_for_status()
    raw = r.json().get("response", "").strip()
    m = RESP_RE.search(raw)
    if m:
        cls = _normalize_class(m.group(1))
        conf = m.group(2).capitalize()
    else:
        cls, conf = "?", "?"
    return cls, conf, elapsed, raw


def main() -> None:
    cases: list[tuple[str, str, str, str]] = []  # category, prompt, gold_class, gold_conf
    for p in WEATHER_ANSWERABLE:
        cases.append(("weather_answerable", p, "weather", "High"))
    for p in WEATHER_UNANSWERABLE:
        cases.append(("weather_unanswerable", p, "weather", "Medium"))
    for p in MUSIC_PLAY_ACTIONS:
        cases.append(("music_play_action", p, "music play", "High"))
    for p in OTHERS_MUSIC_INFO:
        cases.append(("others_music_info", p, "others", "Low"))
    for p in OTHERS_MUSIC_EXTERNAL:
        cases.append(("others_music_external", p, "others", "Low"))
    for p in NO_SMALL_TALK:
        cases.append(("others_small_talk", p, "others", "Low"))
    for p in NO_CODE_QUESTIONS:
        cases.append(("others_code", p, "others", "Low"))

    print(f"Model: {MODEL}  (multi-class: weather, playlist, none)")
    print(f"Cases: {len(cases)}\n")

    results = []
    for i, (category, prompt, gold_cls, gold_conf) in enumerate(cases, 1):
        cls, conf, elapsed, raw = classify(prompt)
        class_correct = cls == gold_cls
        full_correct = class_correct and conf == gold_conf
        results.append({
            "i": i,
            "category": category,
            "prompt": prompt,
            "gold_class": gold_cls,
            "gold_conf": gold_conf,
            "pred_class": cls,
            "pred_conf": conf,
            "raw": raw,
            "elapsed": elapsed,
            "class_correct": class_correct,
            "full_correct": full_correct,
        })
        mark = "OK" if full_correct else ("cls" if class_correct else "XX")
        print(
            f"[{i:3d}] {mark:3s} {category:21s} "
            f"gold={gold_cls+':'+gold_conf:15s} got={cls+':'+conf:17s} "
            f"t={elapsed*1000:5.0f}ms  {prompt[:50]}"
        )

    total = len(results)
    avg_ms = sum(r["elapsed"] for r in results) / total * 1000
    p50_ms = sorted(r["elapsed"] for r in results)[total // 2] * 1000
    p95_ms = sorted(r["elapsed"] for r in results)[int(total * 0.95)] * 1000
    class_acc = sum(1 for r in results if r["class_correct"]) / total * 100
    full_acc = sum(1 for r in results if r["full_correct"]) / total * 100

    print("\n=== speed ===")
    print(f"avg {avg_ms:.0f}ms | p50 {p50_ms:.0f}ms | p95 {p95_ms:.0f}ms")

    print("\n=== accuracy ===")
    print(f"class only  : {class_acc:.1f}%  ({sum(1 for r in results if r['class_correct'])}/{total})")
    print(f"class+conf  : {full_acc:.1f}%  ({sum(1 for r in results if r['full_correct'])}/{total})")

    print("\n=== accuracy by category ===")
    cats: dict[str, list[dict]] = {}
    for r in results:
        cats.setdefault(r["category"], []).append(r)
    for cat, rs in cats.items():
        c_cls = sum(1 for r in rs if r["class_correct"])
        c_full = sum(1 for r in rs if r["full_correct"])
        print(f"  {cat:22s} n={len(rs):3d}  class {c_cls}/{len(rs)} = {c_cls/len(rs)*100:5.1f}%"
              f"  | full {c_full}/{len(rs)} = {c_full/len(rs)*100:5.1f}%")

    print("\n=== confusion by class (predicted vs gold) ===")
    classes = ["weather", "music play", "others", "?"]
    header = " " * 12 + "".join(f"{c:>12s}" for c in classes)
    print(header)
    for gold in ["weather", "music play", "others"]:
        row = [f"{gold:>12s}"]
        for pred in classes:
            n = sum(1 for r in results if r["gold_class"] == gold and r["pred_class"] == pred)
            row.append(f"{n:>12d}")
        print("".join(row))

    class_misses = [r for r in results if not r["class_correct"]]
    if class_misses:
        print(f"\n=== class-level misses ({len(class_misses)}) ===")
        for r in class_misses[:30]:
            print(f"  [{r['i']}] {r['category']:22s} gold={r['gold_class']}:{r['gold_conf']:6s} "
                  f"got={r['pred_class']}:{r['pred_conf']:6s}  {r['prompt']}")
        if len(class_misses) > 30:
            print(f"  ... and {len(class_misses) - 30} more")

    out_path = Path(__file__).parent / "benchmark_gemma_routing_multi_results.json"
    out_path.write_text(json.dumps({
        "model": MODEL,
        "total": total,
        "class_accuracy": class_acc,
        "full_accuracy": full_acc,
        "avg_ms": avg_ms,
        "p50_ms": p50_ms,
        "p95_ms": p95_ms,
        "results": results,
    }, indent=2))
    print(f"\nsaved: {out_path}")


if __name__ == "__main__":
    main()
