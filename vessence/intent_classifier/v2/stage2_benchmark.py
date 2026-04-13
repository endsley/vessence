#!/usr/bin/env python3
"""
Stage 2 metadata extraction benchmark.
Compares gemma4:e2b vs qwen2.5:7b on 40 prompts across all NEEDS_LLM classes.
Measures: latency (median/p95) and parse quality (did it produce valid structured output).
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path
from statistics import median, quantiles

OLLAMA_URL = "http://localhost:11434"
MODELS = ["gemma4:e2b", "qwen2.5:7b"]
TIMEOUT = 20.0

# ── Class contexts ─────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from intent_classifier.v2.classes.send_message  import CONTEXT as CTX_SEND
from intent_classifier.v2.classes.music_play    import CONTEXT as CTX_MUSIC
from intent_classifier.v2.classes.read_messages import CONTEXT as CTX_READ_MSG
from intent_classifier.v2.classes.read_email    import CONTEXT as CTX_READ_EMAIL
from intent_classifier.v2.classes.shopping_list import CONTEXT as CTX_SHOP

# ── 40 test prompts with expected parse fields ─────────────────────────────────
PROMPTS = [
    # SEND_MESSAGE (10)
    {"cls": "SEND_MESSAGE", "ctx": CTX_SEND, "msg": "tell my wife I'll be home by 7",
     "expect": {"RECIPIENT": "wife", "BODY": "I'll be home by 7", "COHERENT": "yes"}},
    {"cls": "SEND_MESSAGE", "ctx": CTX_SEND, "msg": "text john that the meeting is moved to thursday",
     "expect": {"RECIPIENT": "john", "BODY": "the meeting is moved to thursday", "COHERENT": "yes"}},
    {"cls": "SEND_MESSAGE", "ctx": CTX_SEND, "msg": "message kathia I miss her",
     "expect": {"RECIPIENT": "kathia", "BODY": "I miss her", "COHERENT": "yes"}},
    {"cls": "SEND_MESSAGE", "ctx": CTX_SEND, "msg": "let mom know I landed safely",
     "expect": {"RECIPIENT": "mom", "BODY": "I landed safely", "COHERENT": "yes"}},
    {"cls": "SEND_MESSAGE", "ctx": CTX_SEND, "msg": "tell my boss I'm working from home today",
     "expect": {"RECIPIENT": "boss", "BODY": "I'm working from home today", "COHERENT": "yes"}},
    {"cls": "SEND_MESSAGE", "ctx": CTX_SEND, "msg": "text sarah happy birthday",
     "expect": {"RECIPIENT": "sarah", "BODY": "happy birthday", "COHERENT": "yes"}},
    {"cls": "SEND_MESSAGE", "ctx": CTX_SEND, "msg": "send my dad a message saying call me when you can",
     "expect": {"RECIPIENT": "dad", "BODY": "call me when you can", "COHERENT": "yes"}},
    {"cls": "SEND_MESSAGE", "ctx": CTX_SEND, "msg": "tell my sister I'll see her at christmas",
     "expect": {"RECIPIENT": "sister", "BODY": "I'll see her at christmas", "COHERENT": "yes"}},
    {"cls": "SEND_MESSAGE", "ctx": CTX_SEND, "msg": "message bob that the report is done",
     "expect": {"RECIPIENT": "bob", "BODY": "the report is done", "COHERENT": "yes"}},
    {"cls": "SEND_MESSAGE", "ctx": CTX_SEND, "msg": "asdfjkl qwerty blorp snarf",
     "expect": {"COHERENT": "no"}},  # garbled

    # MUSIC_PLAY (8)
    {"cls": "MUSIC_PLAY", "ctx": CTX_MUSIC, "msg": "play some jazz",
     "expect": {"QUERY": "jazz"}},
    {"cls": "MUSIC_PLAY", "ctx": CTX_MUSIC, "msg": "put on the weeknd",
     "expect": {"QUERY": "the weeknd"}},
    {"cls": "MUSIC_PLAY", "ctx": CTX_MUSIC, "msg": "play something relaxing",
     "expect": {"QUERY": "relaxing"}},
    {"cls": "MUSIC_PLAY", "ctx": CTX_MUSIC, "msg": "throw on some hip hop",
     "expect": {"QUERY": "hip hop"}},
    {"cls": "MUSIC_PLAY", "ctx": CTX_MUSIC, "msg": "shuffle my playlist",
     "expect": {"QUERY": ""}},   # no specific query
    {"cls": "MUSIC_PLAY", "ctx": CTX_MUSIC, "msg": "play bohemian rhapsody by queen",
     "expect": {"QUERY": "bohemian rhapsody queen"}},
    {"cls": "MUSIC_PLAY", "ctx": CTX_MUSIC, "msg": "can you play some lo-fi beats",
     "expect": {"QUERY": "lo-fi"}},
    {"cls": "MUSIC_PLAY", "ctx": CTX_MUSIC, "msg": "play workout music",
     "expect": {"QUERY": "workout"}},

    # READ_MESSAGES (8)
    {"cls": "READ_MESSAGES", "ctx": CTX_READ_MSG, "msg": "check my texts",
     "expect": {"FILTER": "all"}},
    {"cls": "READ_MESSAGES", "ctx": CTX_READ_MSG, "msg": "any messages from kathia",
     "expect": {"FILTER": "kathia"}},
    {"cls": "READ_MESSAGES", "ctx": CTX_READ_MSG, "msg": "what did john text me",
     "expect": {"FILTER": "john"}},
    {"cls": "READ_MESSAGES", "ctx": CTX_READ_MSG, "msg": "read my unread texts",
     "expect": {"FILTER": "all"}},
    {"cls": "READ_MESSAGES", "ctx": CTX_READ_MSG, "msg": "did my wife message me",
     "expect": {"FILTER": "wife"}},
    {"cls": "READ_MESSAGES", "ctx": CTX_READ_MSG, "msg": "show me messages from mom",
     "expect": {"FILTER": "mom"}},
    {"cls": "READ_MESSAGES", "ctx": CTX_READ_MSG, "msg": "any new texts",
     "expect": {"FILTER": "all"}},
    {"cls": "READ_MESSAGES", "ctx": CTX_READ_MSG, "msg": "read texts from sarah",
     "expect": {"FILTER": "sarah"}},

    # READ_EMAIL (7)
    {"cls": "READ_EMAIL", "ctx": CTX_READ_EMAIL, "msg": "check my email",
     "expect": {"QUERY": "unread"}},
    {"cls": "READ_EMAIL", "ctx": CTX_READ_EMAIL, "msg": "any emails from amazon",
     "expect": {"QUERY": "amazon"}},
    {"cls": "READ_EMAIL", "ctx": CTX_READ_EMAIL, "msg": "did the bank email me",
     "expect": {"QUERY": "bank"}},
    {"cls": "READ_EMAIL", "ctx": CTX_READ_EMAIL, "msg": "check for new mail",
     "expect": {"QUERY": "unread"}},
    {"cls": "READ_EMAIL", "ctx": CTX_READ_EMAIL, "msg": "any emails from john",
     "expect": {"QUERY": "john"}},
    {"cls": "READ_EMAIL", "ctx": CTX_READ_EMAIL, "msg": "read email from my doctor",
     "expect": {"QUERY": "doctor"}},
    {"cls": "READ_EMAIL", "ctx": CTX_READ_EMAIL, "msg": "show my unread emails",
     "expect": {"QUERY": "unread"}},

    # SHOPPING_LIST (7)
    {"cls": "SHOPPING_LIST", "ctx": CTX_SHOP, "msg": "add milk to my list",
     "expect": {"ACTION": "add milk"}},
    {"cls": "SHOPPING_LIST", "ctx": CTX_SHOP, "msg": "put bread on the grocery list",
     "expect": {"ACTION": "add bread"}},
    {"cls": "SHOPPING_LIST", "ctx": CTX_SHOP, "msg": "remove eggs I already got them",
     "expect": {"ACTION": "remove eggs"}},
    {"cls": "SHOPPING_LIST", "ctx": CTX_SHOP, "msg": "what's on my shopping list",
     "expect": {"ACTION": "show list"}},
    {"cls": "SHOPPING_LIST", "ctx": CTX_SHOP, "msg": "add coffee and orange juice",
     "expect": {"ACTION": "add coffee"}},  # multiple items
    {"cls": "SHOPPING_LIST", "ctx": CTX_SHOP, "msg": "take bananas off the list",
     "expect": {"ACTION": "remove bananas"}},
    {"cls": "SHOPPING_LIST", "ctx": CTX_SHOP, "msg": "add a dozen eggs",
     "expect": {"ACTION": "add eggs"}},
]


# ── Ollama call ────────────────────────────────────────────────────────────────

def ollama_call(model: str, context: str, message: str) -> tuple[str, float]:
    prompt = f"{context}\n\nUser: {message}"
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        raw = urllib.request.urlopen(req, timeout=TIMEOUT).read()
        elapsed = time.time() - t0
        return json.loads(raw).get("response", "").strip(), elapsed
    except Exception as e:
        return f"ERROR: {e}", time.time() - t0


# ── Parse quality ──────────────────────────────────────────────────────────────

def parse_fields(raw: str) -> dict[str, str]:
    """Extract key: value pairs from structured LLM output."""
    import re
    fields = {}
    for line in raw.splitlines():
        m = re.match(r"^([A-Z_]+):\s*(.+)$", line.strip())
        if m:
            fields[m.group(1)] = m.group(2).strip()
    return fields


def score_response(raw: str, expect: dict, cls: str) -> dict:
    """Score how well the response matches expected fields."""
    fields = parse_fields(raw)
    parsed_ok = bool(fields)

    if cls == "SEND_MESSAGE":
        has_recipient = "RECIPIENT" in fields and fields["RECIPIENT"]
        has_body      = "BODY" in fields and fields["BODY"]
        has_coherent  = fields.get("COHERENT", "").lower() in ("yes", "no")
        coherent_val  = fields.get("COHERENT", "").lower()
        # For garbled test, coherent=no is correct
        coherent_correct = (
            coherent_val == expect.get("COHERENT", "yes").lower()
        )
        quality = "good" if (has_recipient and has_body and has_coherent and coherent_correct) else \
                  "partial" if parsed_ok else "fail"
        return {"quality": quality, "fields": fields, "parsed_ok": parsed_ok}

    # For other classes just check the key field is present and non-empty
    key_map = {
        "MUSIC_PLAY":    "QUERY",
        "READ_MESSAGES": "FILTER",
        "READ_EMAIL":    "QUERY",
        "SHOPPING_LIST": "ACTION",
    }
    key = key_map.get(cls)
    if key:
        present = key in fields
        quality = "good" if present else ("partial" if parsed_ok else "fail")
    else:
        quality = "good" if parsed_ok else "fail"

    return {"quality": quality, "fields": fields, "parsed_ok": parsed_ok}


# ── Warmup ─────────────────────────────────────────────────────────────────────

def warmup(model: str):
    print(f"  Warming up {model}…", end=" ", flush=True)
    _, t = ollama_call(model, CTX_SEND, "text john hello")
    _, t2 = ollama_call(model, CTX_SEND, "text john hello")  # second call uses KV cache
    print(f"cold={t:.2f}s  warm={t2:.2f}s")


# ── Main ───────────────────────────────────────────────────────────────────────

def run():
    print(f"\n{'='*65}")
    print("Stage 2 Metadata Extraction Benchmark")
    print(f"Models: {', '.join(MODELS)}  |  Prompts: {len(PROMPTS)}")
    print(f"{'='*65}\n")

    # Warmup both models
    print("[Warmup]")
    for m in MODELS:
        warmup(m)
    print()

    results = {m: [] for m in MODELS}

    print(f"[Running {len(PROMPTS)} prompts × {len(MODELS)} models]\n")
    print(f"{'#':>2}  {'Class':<15} {'Msg':<42}  ", end="")
    for m in MODELS:
        short = m.split(":")[0][:10]
        print(f"{'Lat':>5} {'Q':>5}  ", end="")
    print()
    print("-" * 90)

    for i, p in enumerate(PROMPTS):
        row_label = f"{i+1:>2}  {p['cls']:<15} {p['msg'][:40]:<42}  "
        print(row_label, end="", flush=True)

        for model in MODELS:
            raw, elapsed = ollama_call(model, p["ctx"], p["msg"])
            sc = score_response(raw, p["expect"], p["cls"])
            results[model].append({
                "cls": p["cls"],
                "msg": p["msg"],
                "raw": raw[:300],
                "latency_s": elapsed,
                "quality": sc["quality"],
                "fields": sc["fields"],
            })
            q_sym = {"good": "✓", "partial": "~", "fail": "✗"}[sc["quality"]]
            print(f"{elapsed:5.2f}s {q_sym:>5}  ", end="", flush=True)

        print()

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print("RESULTS SUMMARY")
    print(f"{'='*65}")

    for model in MODELS:
        rows = results[model]
        lats = [r["latency_s"] for r in rows]
        good = sum(1 for r in rows if r["quality"] == "good")
        partial = sum(1 for r in rows if r["quality"] == "partial")
        fail = sum(1 for r in rows if r["quality"] == "fail")
        med = median(lats)
        p95 = quantiles(lats, n=20)[18] if len(lats) >= 20 else max(lats)

        print(f"\n[{model}]")
        print(f"  Latency:  median {med:.2f}s   p95 {p95:.2f}s   min {min(lats):.2f}s   max {max(lats):.2f}s")
        print(f"  Quality:  ✓ good={good}  ~ partial={partial}  ✗ fail={fail}  ({good/len(rows)*100:.0f}% good)")

        # Per-class breakdown
        for cls in sorted(set(r["cls"] for r in rows)):
            cls_rows = [r for r in rows if r["cls"] == cls]
            cls_good = sum(1 for r in cls_rows if r["quality"] == "good")
            cls_lats = [r["latency_s"] for r in cls_rows]
            print(f"    {cls:<18} {cls_good}/{len(cls_rows)} good   median {median(cls_lats):.2f}s")

    # ── Side-by-side fail inspection ───────────────────────────────────────────
    print(f"\n{'='*65}")
    print("FAILURES / PARTIAL RESPONSES")
    print(f"{'='*65}")
    shown = 0
    for i, p in enumerate(PROMPTS):
        for model in MODELS:
            r = results[model][i]
            if r["quality"] != "good":
                print(f"\n[{model}] [{r['cls']}] \"{r['msg']}\"")
                print(f"  Quality: {r['quality']}")
                print(f"  Raw: {r['raw'][:200]!r}")
                shown += 1
    if shown == 0:
        print("  None — all responses were good!")

    # Save JSON
    out = Path(__file__).parent / "results" / f"stage2_benchmark_{int(time.time())}.json"
    out.write_text(json.dumps({"models": MODELS, "prompts": PROMPTS, "results": results}, indent=2, default=str))
    print(f"\n[saved] {out.name}")


if __name__ == "__main__":
    run()
