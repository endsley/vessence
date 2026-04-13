#!/usr/bin/env python3
"""
Stage 1 Classifier Experiment — v2 embedding-based design vs current gemma4:e2b.

Architecture under test:
  1. Embed user message with BAAI/bge-small-en-v1.5
  2. Query dedicated ChromaDB collection (50 examples/class stored)
  3. High confidence  → return class (~10ms total)
     + needs metadata → small focused LLM call with class context
  4. Low confidence   → DELEGATE_OPUS (don't burn an LLM on ambiguity)

Baseline:
  Current gemma4:e2b approach — full 1900-token system prompt per call

LLM backends compared for metadata extraction:
  - gemma4:e2b  (current, 5.1B)
  - gemma3:1b   (new candidate, genuinely small)

Output: results/experiment_<timestamp>.json + printed summary
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from statistics import median, quantiles
from typing import Optional

# ── Path setup ────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
sys.path.insert(0, str(_REPO))

CLASSES_DIR = _HERE / "classes"
RESULTS_DIR = _HERE / "results"
RESULTS_DIR.mkdir(exist_ok=True)

CHROMA_PATH = Path(os.environ.get(
    "VESSENCE_DATA_HOME", Path.home() / "ambient/vessence-data"
)) / "memory/v1/vector_db/intent_classifier_experiment"

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
CONFIDENCE_THRESHOLD = 0.60   # vote fraction: 3/5 = 0.60 minimum majority
MARGIN_THRESHOLD     = 0.20   # vote margin: at least 1 more vote than runner-up

# ── Load class registry ───────────────────────────────────────────────────────

def load_registry() -> dict:
    """Import all class definition modules and return {class_name: module}."""
    registry = {}
    for f in sorted(CLASSES_DIR.glob("*.py")):
        if f.name.startswith("_"):
            continue
        mod = importlib.import_module(f"intent_classifier.v2.classes.{f.stem}")
        registry[mod.CLASS_NAME] = mod
    return registry


# ── Embedding helpers ─────────────────────────────────────────────────────────

def get_embedding_fn():
    """Return a callable that embeds a list of strings → list of vectors."""
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("BAAI/bge-small-en-v1.5")
        return lambda texts: model.encode(texts, normalize_embeddings=True).tolist()
    except Exception as e:
        print(f"[warn] SentenceTransformer unavailable ({e}), falling back to ONNX")
        import chromadb.utils.embedding_functions as ef
        onnx = ef.ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])
        return lambda texts: onnx(texts)


# ── ChromaDB setup ────────────────────────────────────────────────────────────

def build_chroma_collection(registry: dict, embed_fn) -> object:
    """Create (or recreate) the experiment ChromaDB collection."""
    import chromadb

    print(f"\n[setup] Building ChromaDB collection at {CHROMA_PATH}")
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))

    # Always start fresh for a clean experiment
    try:
        client.delete_collection("intent_v2_experiment")
    except Exception:
        pass

    collection = client.create_collection(
        name="intent_v2_experiment",
        metadata={"hnsw:space": "cosine"},
    )

    ids, docs, metas = [], [], []
    for cls_name, mod in registry.items():
        for i, example in enumerate(mod.EXAMPLES):
            ids.append(f"{cls_name}_{i}")
            docs.append(example)
            metas.append({"class": cls_name})

    print(f"[setup] Embedding {len(docs)} examples across {len(registry)} classes…")
    t0 = time.time()
    embeddings = embed_fn(docs)
    elapsed = time.time() - t0
    print(f"[setup] Embedded in {elapsed:.1f}s ({len(docs)/elapsed:.0f} docs/s)")

    collection.add(ids=ids, documents=docs, embeddings=embeddings, metadatas=metas)
    print(f"[setup] Collection ready: {collection.count()} vectors stored")
    return collection


# ── Embedding-based classifier ────────────────────────────────────────────────

TOP_K = 5  # number of nearest vectors to retrieve for majority vote

def classify_by_embedding(
    message: str,
    collection,
    embed_fn,
    registry: dict,
) -> tuple[str, float, float, float]:
    """
    Retrieve TOP_K nearest vectors, majority-vote on their class labels.

    Returns (predicted_class, vote_fraction, margin, elapsed_seconds).
      vote_fraction  = winning_votes / TOP_K  (e.g. 4/5 = 0.80)
      margin         = (winning_votes - runner_up_votes) / TOP_K
    """
    t0 = time.time()
    vec = embed_fn([message])[0]
    results = collection.query(
        query_embeddings=[vec],
        n_results=min(TOP_K, collection.count()),
        include=["metadatas", "distances"],
    )
    elapsed = time.time() - t0

    metas = results["metadatas"][0]

    # Tally votes
    votes: dict[str, int] = {}
    for meta in metas:
        cls = meta["class"]
        votes[cls] = votes.get(cls, 0) + 1

    sorted_votes = sorted(votes.items(), key=lambda x: -x[1])
    top_cls,    top_votes    = sorted_votes[0]
    second_votes = sorted_votes[1][1] if len(sorted_votes) > 1 else 0

    vote_fraction = top_votes / TOP_K
    margin        = (top_votes - second_votes) / TOP_K

    return top_cls, vote_fraction, margin, elapsed


# ── LLM metadata extraction ───────────────────────────────────────────────────

def llm_extract_metadata(
    message: str,
    class_context: str,
    model: str,
    timeout: float = 12.0,
) -> tuple[Optional[str], float]:
    """
    Call ollama with a focused single-class context.
    Returns (raw_response_text, elapsed_seconds).
    """
    prompt = f"{class_context}\n\nUser: {message}"
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        raw = urllib.request.urlopen(req, timeout=timeout).read()
        elapsed = time.time() - t0
        data = json.loads(raw)
        return data.get("response", "").strip(), elapsed
    except Exception as e:
        return None, time.time() - t0


# ── Baseline: current gemma4:e2b full-prompt approach ────────────────────────

def classify_baseline_llm(message: str, system_prompt: str, model: str, timeout: float = 20.0):
    """Run the current Stage 1 approach: full system prompt + user message."""
    prompt = system_prompt.strip() + "\n---\nuser: " + message
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        raw = urllib.request.urlopen(req, timeout=timeout).read()
        elapsed = time.time() - t0
        data = json.loads(raw)
        return data.get("response", "").strip(), elapsed
    except Exception as e:
        return None, time.time() - t0


def parse_baseline_class(raw: str) -> Optional[str]:
    """Extract CLASSIFICATION: X from baseline response."""
    import re
    m = re.search(r"CLASSIFICATION:\s*(\w+)", raw or "")
    return m.group(1).upper() if m else None


# ── Test prompt generation ────────────────────────────────────────────────────

# Hand-written test prompts — 30 per class, DIFFERENT from the 50 training examples.
# Intentionally varied phrasing, STT-style errors, and edge cases.

TEST_PROMPTS: dict[str, list[str]] = {
    "GREETING": [
        "hey there", "hi!", "hello there", "good morning to you",
        "good evening jane", "morning!", "evening!", "hi hey",
        "yo what's up", "sup?", "heyyy", "hola!", "hey hey hey",
        "hello hello", "greetings!", "what's up?", "hey jane hi",
        "good afternoon!", "hi good morning", "hey jane what's up",
        "morning morning", "yo jane", "hi there!", "hey you",
        "hello jane good morning", "good night", "night night",
        "hey is that you", "heyy jane", "hi jane good morning",
    ],
    "SELF_HANDLE": [
        "what time is it now", "what's today", "today's date please",
        "is it going to snow", "what's the forecast tomorrow",
        "calculate 88 times 7", "what's 2024 plus 300",
        "how many seconds in a day", "what's the speed of sound",
        "who invented email", "when did the internet start",
        "how tall is the eiffel tower", "what's the population of China",
        "how do you spell occurrence", "what's another word for happy",
        "tell me something interesting", "what's 15 percent of 200",
        "what language do they speak in Brazil", "when is Easter this year",
        "how long does it take to fly to Japan", "what's the distance to Mars",
        "define entropy", "what's the biggest country in the world",
        "how many planets are there", "what's a limerick",
        "who painted the Mona Lisa", "what year was Einstein born",
        "are you there", "do you understand", "can you hear me okay",
    ],
    "MUSIC_PLAY": [
        "play some music please", "can you play jazz",
        "throw on some hip hop for me", "shuffle my songs",
        "i want to hear some classical", "put on the weeknd",
        "play something chill", "can I hear some country",
        "play post malone", "throw on some EDM",
        "play some workout music", "put on a good song",
        "play some old school rap", "i want to hear fleetwood mac",
        "can you play something relaxing", "play some ambient music",
        "throw on bob marley", "put on some soul music",
        "play me some jazz please", "shuffle some rock songs",
        "play some focus music", "put on the rolling stones",
        "play some dinner music", "can you queue up some songs",
        "throw on some 90s music", "play some indie pop",
        "put on michael jackson", "play some house music",
        "play dua lipa", "shuffle everything please",
    ],
    "SHOPPING_LIST": [
        "add tomatoes", "I need to get milk", "put oranges on the list",
        "can you add coffee to my list", "add toilet paper",
        "I need bread", "put chicken on the grocery list",
        "add some fruit please", "remove the eggs I got them",
        "take milk off the list already bought it",
        "what's left on my shopping list", "read me my grocery list",
        "add dish soap and sponges", "put butter on the list",
        "I need to buy shampoo", "add olive oil",
        "put sparkling water on the list", "add peanut butter",
        "I need to pick up some cheese", "add garlic and onions",
        "put rice and beans on the list", "show me what I need to buy",
        "add a bottle of wine", "put cereal on the list",
        "I need paper towels please add them", "add some vegetables",
        "remove bread from the list", "add frozen vegetables",
        "put some snacks on the list", "add two dozen eggs",
    ],
    "READ_MESSAGES": [
        "check my texts please", "do I have any new texts",
        "what did my wife text", "read texts from kathia",
        "any messages from john lately", "did bob send me anything",
        "show me my unread texts", "read my incoming messages",
        "check if mom texted me", "what did sarah message me",
        "any texts from the family", "read the last text I got",
        "check messages from my sister", "did anyone text me today",
        "pull up my texts", "read new SMS",
        "any messages from my boss", "what texts came in while I was busy",
        "check texts from work", "did kathia message me recently",
        "show me texts from john", "any unread SMS",
        "read message from dad", "check my text inbox",
        "what did she say in her text", "any texts today",
        "check SMS from mom", "did my wife text back",
        "read all new messages", "show incoming texts",
    ],
    "READ_EMAIL": [
        "check my emails please", "do I have new email",
        "what's in my inbox today", "any important emails",
        "check email from john", "did amazon email me",
        "any emails from my bank", "check for shipping updates",
        "did the doctor's office email me", "show my unread emails",
        "read latest email from sarah", "any work emails",
        "check my gmail please", "any emails this morning",
        "pull up my inbox", "did anyone reply to my email",
        "check email from school", "any newsletters today",
        "read email from my boss", "check for order confirmation emails",
        "did the airline email me", "any emails from government",
        "check inbox for anything urgent", "read unread mail",
        "any replies in my email", "show emails from the last hour",
        "did the hotel email a confirmation", "check for spam",
        "any emails about the meeting", "read email from HR",
    ],
    "SYNC_MESSAGES": [
        "can you sync my messages", "please resync my texts",
        "refresh my SMS", "do a message sync",
        "update my text messages", "pull in new messages",
        "force sync my messages", "sync up messages",
        "reload my messages please", "run a sync",
        "get new texts loaded", "refresh text messages",
        "sync SMS now", "update my message list",
        "resync my inbox", "fetch latest texts",
        "sync the messages please", "pull latest SMS",
        "do a resync", "update messages",
        "can you refresh the messages", "reload texts please",
        "force a sync on my messages", "get messages updated",
        "sync my text inbox", "refresh and sync messages",
        "pull new texts", "do message refresh",
        "sync texts now please", "update my SMS inbox",
    ],
    "SEND_MESSAGE": [
        "text my mom I'll call her later", "tell john I'm on my way",
        "message my boss that I'll be late", "let sarah know dinner is at 7",
        "send my wife a text", "tell kathia good night",
        "message bob that the deal is done", "let my dad know I'm safe",
        "text my sister happy birthday today", "tell john to call me",
        "message my wife that I left work", "let mom know I got here fine",
        "text my coworker the meeting is at 3", "send john a quick message",
        "tell sarah I got her voicemail", "message my wife I love you",
        "let bob know the project is done", "text my dad to call me back",
        "tell kathia I'm thinking of her", "message my friend I'm running late",
        "let my wife know kids are picked up", "text john I'm outside",
        "tell mom I miss her", "message sarah the party is on",
        "let my boss know I submitted it", "text my wife good night",
        "tell john the game is on tonight", "message bob happy new year",
        "let kathia know I'll be there soon", "text my wife I'm coming home",
    ],
    "END_CONVERSATION": [
        "actually cancel that", "no don't send it",
        "forget it never mind", "stop don't do that",
        "nope that's wrong", "actually no thanks",
        "please don't", "abort", "wait cancel",
        "no forget it", "stop that please",
        "leave it", "never mind that",
        "actually don't worry about it", "ok I'm done",
        "that's all I need", "goodbye for now",
        "ok bye", "see you", "later jane",
        "thanks that's all", "that'll do",
        "cool i'm good", "all done thanks",
        "we're finished", "no more for now",
        "ok I'm good thanks", "thanks bye",
        "i don't need anything else", "we're done here",
    ],
    "DELEGATE_OPUS": [
        "call my sister", "phone the doctor",
        "set an alarm for 7am tomorrow", "set a timer for 20 minutes",
        "what should I cook for dinner tonight",
        "help me write a resignation letter",
        "what's the traffic on my commute",
        "add a meeting to my calendar for Thursday",
        "look up the nearest pharmacy",
        "why is my wifi slow", "debug the app crash",
        "book a flight to Chicago", "find a hotel in Boston",
        "read me the top news stories", "what stocks should I buy",
        "write me a poem about autumn", "summarize this article",
        "translate this to Mandarin", "help me plan a birthday party",
        "what's a good recipe for chicken soup",
        "navigate me home", "turn off the living room lights",
        "open youtube", "search for the latest iphone",
        "what's on my calendar tomorrow", "remind me at 3pm",
        "research machine learning papers", "explain quantum computing",
        "what movies are playing tonight", "order me a pizza",
    ],
}


# ── Main experiment ───────────────────────────────────────────────────────────

def run_experiment(
    test_models: list[str] = ["gemma4:e2b", "gemma3:1b"],
    run_baseline: bool = True,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
    margin_threshold: float = MARGIN_THRESHOLD,
):
    registry = load_registry()
    print(f"[info] Loaded {len(registry)} classes: {', '.join(sorted(registry))}")

    print("[info] Loading embedding model…")
    embed_fn = get_embedding_fn()
    # Warm-up
    embed_fn(["warmup"])
    print("[info] Embedding model ready")

    collection = build_chroma_collection(registry, embed_fn)

    # Pull missing models
    for model in test_models:
        try:
            resp = urllib.request.urlopen(
                f"{OLLAMA_URL}/api/show",
                data=json.dumps({"name": model}).encode(),
                timeout=5,
            )
        except Exception:
            print(f"[setup] Pulling {model}…")
            os.system(f"ollama pull {model}")

    # Load baseline system prompt
    if run_baseline:
        from intent_classifier.v1.gemma_stage1 import SYSTEM_PROMPT as _sys_prompt
        baseline_system_prompt = _sys_prompt
    else:
        baseline_system_prompt = None

    # ── Run tests ──────────────────────────────────────────────────────────────
    results = {
        "config": {
            "confidence_threshold": confidence_threshold,
            "margin_threshold": margin_threshold,
            "test_models": test_models,
            "n_train_per_class": {cls: len(mod.EXAMPLES) for cls, mod in registry.items()},
            "n_test_per_class": {cls: len(prompts) for cls, prompts in TEST_PROMPTS.items()},
        },
        "per_prompt": [],
        "summary": {},
    }

    all_classes = sorted(registry.keys())
    total = sum(len(p) for p in TEST_PROMPTS.values())
    done = 0

    print(f"\n[run] Testing {total} prompts…\n")

    for true_class, prompts in TEST_PROMPTS.items():
        for prompt in prompts:
            row = {"prompt": prompt, "true_class": true_class}

            # ── Embedding classifier ──────────────────────────────────────────
            pred_emb, top_sim, margin, emb_time = classify_by_embedding(
                prompt, collection, embed_fn, registry
            )
            high_conf = (top_sim >= confidence_threshold and margin >= margin_threshold)
            final_class = pred_emb if high_conf else "DELEGATE_OPUS"

            row["embedding"] = {
                "predicted":    pred_emb,
                "final":        final_class,
                "similarity":   round(top_sim, 4),
                "margin":       round(margin, 4),
                "high_conf":    high_conf,
                "correct":      final_class == true_class,
                "latency_ms":   round(emb_time * 1000, 1),
            }

            # ── Metadata extraction (only when high-conf + class needs LLM) ──
            needs_llm = high_conf and registry.get(pred_emb, object).NEEDS_LLM
            ctx = registry[pred_emb].CONTEXT if (high_conf and pred_emb in registry) else None

            for model in test_models:
                key = f"meta_{model.replace(':', '_').replace('.', '_')}"
                if needs_llm and ctx:
                    raw, llm_time = llm_extract_metadata(prompt, ctx, model)
                    row[key] = {
                        "ran": True,
                        "response": (raw or "")[:200],
                        "latency_ms": round(llm_time * 1000, 1),
                    }
                else:
                    row[key] = {"ran": False, "reason": "no_llm_needed" if not needs_llm else "no_ctx"}

            # ── Baseline: full system prompt through gemma4:e2b ───────────────
            if run_baseline and baseline_system_prompt:
                b_raw, b_time = classify_baseline_llm(
                    prompt, baseline_system_prompt, "gemma4:e2b", timeout=20.0
                )
                b_pred = parse_baseline_class(b_raw or "")
                row["baseline_llm"] = {
                    "raw":        (b_raw or "")[:200],
                    "predicted":  b_pred,
                    "correct":    b_pred == true_class if b_pred else False,
                    "latency_ms": round(b_time * 1000, 1),
                }

            results["per_prompt"].append(row)
            done += 1
            if done % 10 == 0 or done == total:
                pct = done / total * 100
                print(f"  {done}/{total} ({pct:.0f}%) — last: [{true_class}] {prompt[:50]!r}")

    # ── Compute summary ────────────────────────────────────────────────────────
    _summarize(results, all_classes)

    ts = time.strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"experiment_{ts}.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\n[done] Results saved to {out_path}")
    _print_summary(results)
    return results


def _summarize(results: dict, all_classes: list[str]):
    pp = results["per_prompt"]

    def stats(times):
        if not times:
            return {}
        times = sorted(times)
        return {
            "median_ms": round(median(times), 1),
            "p95_ms":    round(quantiles(times, n=20)[18], 1) if len(times) >= 20 else round(max(times), 1),
            "min_ms":    round(min(times), 1),
            "max_ms":    round(max(times), 1),
            "n":         len(times),
        }

    # Embedding classifier
    emb_correct = [r for r in pp if r["embedding"]["correct"]]
    emb_times   = [r["embedding"]["latency_ms"] for r in pp]
    results["summary"]["embedding"] = {
        "accuracy":      round(len(emb_correct) / len(pp), 4),
        "correct":       len(emb_correct),
        "total":         len(pp),
        "latency":       stats(emb_times),
        "high_conf_pct": round(sum(1 for r in pp if r["embedding"]["high_conf"]) / len(pp), 4),
        "per_class": {
            cls: {
                "correct": sum(1 for r in pp if r["true_class"] == cls and r["embedding"]["correct"]),
                "total":   sum(1 for r in pp if r["true_class"] == cls),
            }
            for cls in all_classes
        },
    }

    # Baseline LLM
    if any("baseline_llm" in r for r in pp):
        b_correct = [r for r in pp if r.get("baseline_llm", {}).get("correct")]
        b_times   = [r["baseline_llm"]["latency_ms"] for r in pp if "baseline_llm" in r]
        results["summary"]["baseline_llm"] = {
            "accuracy": round(len(b_correct) / len(pp), 4),
            "correct":  len(b_correct),
            "total":    len(pp),
            "latency":  stats(b_times),
            "per_class": {
                cls: {
                    "correct": sum(1 for r in pp if r["true_class"] == cls and r.get("baseline_llm", {}).get("correct")),
                    "total":   sum(1 for r in pp if r["true_class"] == cls),
                }
                for cls in all_classes
            },
        }

    # Metadata LLM latency (per model)
    for key in [k for k in pp[0] if k.startswith("meta_")]:
        ran = [r[key] for r in pp if r[key].get("ran")]
        if ran:
            results["summary"][key] = {"latency": stats([r["latency_ms"] for r in ran]), "n_ran": len(ran)}


def _print_summary(results: dict):
    s = results["summary"]
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)

    if "embedding" in s:
        e = s["embedding"]
        print(f"\n[Embedding classifier]")
        print(f"  Accuracy:     {e['accuracy']*100:.1f}%  ({e['correct']}/{e['total']})")
        print(f"  High-conf:    {e['high_conf_pct']*100:.1f}% of prompts got a confident answer")
        print(f"  Latency:      median {e['latency']['median_ms']}ms  p95 {e['latency']['p95_ms']}ms")
        print(f"  Per-class accuracy:")
        for cls, v in sorted(e["per_class"].items()):
            pct = v["correct"] / v["total"] * 100 if v["total"] else 0
            bar = "█" * int(pct / 5)
            print(f"    {cls:<20} {pct:5.1f}%  {bar}")

    if "baseline_llm" in s:
        b = s["baseline_llm"]
        print(f"\n[Baseline: gemma4:e2b full prompt]")
        print(f"  Accuracy:     {b['accuracy']*100:.1f}%  ({b['correct']}/{b['total']})")
        print(f"  Latency:      median {b['latency']['median_ms']}ms  p95 {b['latency']['p95_ms']}ms")

    for key in [k for k in s if k.startswith("meta_")]:
        model = key.replace("meta_", "").replace("_", ":")
        m = s[key]
        print(f"\n[Metadata extraction: {model}]")
        print(f"  Ran on {m['n_ran']} prompts (classes needing metadata + high-conf)")
        print(f"  Latency: median {m['latency']['median_ms']}ms  p95 {m['latency']['p95_ms']}ms")

    print("\n" + "=" * 70)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stage 1 embedding classifier experiment")
    parser.add_argument("--no-baseline", action="store_true",
                        help="Skip the slow gemma4:e2b baseline (embedding-only run)")
    parser.add_argument("--models", nargs="+", default=["gemma4:e2b", "gemma3:1b"],
                        help="Ollama models to test for metadata extraction")
    parser.add_argument("--threshold", type=float, default=CONFIDENCE_THRESHOLD,
                        help=f"Cosine similarity threshold (default {CONFIDENCE_THRESHOLD})")
    parser.add_argument("--margin", type=float, default=MARGIN_THRESHOLD,
                        help=f"Margin between 1st and 2nd class (default {MARGIN_THRESHOLD})")
    args = parser.parse_args()

    run_experiment(
        test_models=args.models,
        run_baseline=not args.no_baseline,
        confidence_threshold=args.threshold,
        margin_threshold=args.margin,
    )
