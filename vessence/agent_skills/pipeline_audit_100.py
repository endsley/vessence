"""pipeline_audit_100.py — end-to-end audit of the 3-stage pipeline on real prompts.

Pulls the last N (default 100) user prompts from the prompt dump log,
runs each through the live pipeline, and uses qwen2.5:7b as a judge to
evaluate each stage:
  - Stage 1: was the classification correct?
  - Stage 2: did the handler do the right thing? (or correctly escalate?)
  - Stage 3: did Opus's response actually answer the user?

For Stage 1 misclassifications with a clear correct class, automatically
adds the prompt as an exemplar to the correct ChromaDB class (the same
self-correct mechanism already in stage2_dispatcher).

Stage 2 and Stage 3 issues get logged to configs/pipeline_audit_report.md
for human review — these usually require code changes, not data fixes.

Run manually:
  python agent_skills/pipeline_audit_100.py [--n 100] [--apply-fixes]

Run as part of nightly self-improvement:
  Cron: 0 4 * * *  (4 AM, in sleep window)
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import httpx

VESSENCE_HOME = Path(os.environ.get("VESSENCE_HOME", str(Path(__file__).resolve().parents[1])))
VESSENCE_DATA_HOME = Path(os.environ.get("VESSENCE_DATA_HOME", str(Path.home() / "ambient/vessence-data")))
PROMPT_DUMP = VESSENCE_DATA_HOME / "logs" / "jane_prompt_dump.jsonl"
REPORT_PATH = VESSENCE_HOME / "configs" / "pipeline_audit_report.md"
JUDGE_MODEL = os.environ.get("JANE_AUDIT_JUDGE_MODEL", "qwen2.5:7b")
OLLAMA_URL = "http://localhost:11434/api/generate"
SERVER = os.environ.get("JANE_AUDIT_SERVER", "http://localhost:8080")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pipeline_audit")

KNOWN_CLASSES = [
    "weather", "music play", "greeting", "read messages", "send message",
    "sync messages", "shopping list", "read email", "end conversation",
    "get time", "others",
]


# ── Data collection ─────────────────────────────────────────────────────────


def load_recent_prompts(n: int = 100) -> list[dict]:
    """Pull the last n meaningful user prompts from the dump."""
    if not PROMPT_DUMP.exists():
        return []
    rows = []
    with PROMPT_DUMP.open() as f:
        for line in f:
            try:
                d = json.loads(line)
                msg = (d.get("message") or "").strip()
                # Skip system prefixes — we want the user's actual words
                if not msg or msg.startswith("[") or msg.startswith("("):
                    continue
                if len(msg) < 3:
                    continue
                rows.append({"prompt": msg, "ts": d.get("timestamp", "")})
            except Exception:
                continue
    # Dedupe consecutive duplicates
    seen = set()
    unique = []
    for r in rows:
        if r["prompt"] in seen:
            continue
        seen.add(r["prompt"])
        unique.append(r)
    return unique[-n:]


# ── Live pipeline runner ────────────────────────────────────────────────────


async def classify_only(prompt: str) -> str:
    """Fast classify-only path — uses the same wrapper the pipeline uses."""
    try:
        sys.path.insert(0, str(VESSENCE_HOME)) if str(VESSENCE_HOME) not in sys.path else None
        from jane_web.jane_v2.stage1_classifier import classify
        cls, conf = await classify(prompt)
        return f"{cls}:{conf}"
    except Exception as e:
        return f"error:{e}"


async def run_through_pipeline(prompt: str, session_id: str) -> dict:
    """POST to the streaming endpoint, parse all events, return summary."""
    events = []
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{SERVER}/api/jane/chat/stream",
                json={"message": prompt, "session_id": session_id},
            ) as r:
                async for line in r.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except Exception:
                        pass
    except Exception as e:
        return {"error": str(e), "events": events}

    # Summarize
    classification = None
    stage = None
    response_text = ""
    ack_text = None
    tool_calls = []
    for ev in events:
        t = ev.get("type")
        d = ev.get("data")
        if t == "ack":
            ack_text = d
        elif t == "client_tool_call":
            try:
                tc = json.loads(d) if isinstance(d, str) else d
                tool_calls.append(tc.get("tool", "?"))
            except Exception:
                pass
        elif t == "delta":
            response_text = d if isinstance(d, str) else response_text
        elif t == "done":
            response_text = d if isinstance(d, str) else response_text
        # Pull classification + stage from the response object if available
        if "classification" in ev:
            classification = ev["classification"]
        if "stage" in ev:
            stage = ev["stage"]

    # Heuristic stage detection if not in events
    if not stage:
        if any(ev.get("type") == "start" for ev in events):
            stage = "stage3"
        elif tool_calls or response_text:
            stage = "stage2"

    return {
        "classification": classification,
        "stage": stage,
        "response": response_text[:500],
        "ack": ack_text,
        "tool_calls": tool_calls,
        "events": events,
    }


# ── LLM judge ───────────────────────────────────────────────────────────────


async def judge(prompt: str, result: dict) -> dict:
    """Ask qwen to evaluate the pipeline output. Returns a verdict dict."""
    judge_prompt = f"""You are auditing Jane's 3-stage pipeline. Decide if the pipeline handled this prompt correctly.

USER PROMPT: {prompt}

PIPELINE OUTPUT:
- Classification: {result.get("classification", "?")}
- Stage: {result.get("stage", "?")}
- Ack to user: {result.get("ack") or "(none)"}
- Tool calls: {result.get("tool_calls") or "(none)"}
- Response text: {result.get("response", "")[:300]}

Evaluate:
1. Was the Stage 1 classification correct? Pick the ideal class from:
   {", ".join(KNOWN_CLASSES)}
2. Did Stage 2/3 produce a useful response that actually answers the prompt?

Output EXACTLY this format (3 lines, nothing else):
CORRECT_CLASS: <one of the classes above>
CLASSIFICATION_OK: yes | no
RESPONSE_OK: yes | no
"""
    body = {
        "model": JUDGE_MODEL,
        "prompt": judge_prompt,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 80},
        "keep_alive": "1h",
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(OLLAMA_URL, json=body)
            r.raise_for_status()
            raw = (r.json().get("response") or "").strip()
    except Exception as e:
        return {"error": str(e)}

    out = {"raw": raw}
    for line in raw.splitlines():
        m = re.match(r"CORRECT_CLASS:\s*(.+)", line, re.IGNORECASE)
        if m:
            out["correct_class"] = m.group(1).strip().lower()
        m = re.match(r"CLASSIFICATION_OK:\s*(yes|no)", line, re.IGNORECASE)
        if m:
            out["classification_ok"] = m.group(1).lower() == "yes"
        m = re.match(r"RESPONSE_OK:\s*(yes|no)", line, re.IGNORECASE)
        if m:
            out["response_ok"] = m.group(1).lower() == "yes"
    return out


# ── Self-correct: add prompt to correct class in ChromaDB ───────────────────


def add_exemplar(prompt: str, target_class: str) -> bool:
    """Add prompt as an exemplar to the named class in ChromaDB."""
    cls_upper = target_class.upper().replace(" ", "_")
    if cls_upper == "OTHERS":
        cls_upper = "DELEGATE_OPUS"
    try:
        # Ensure VESSENCE_HOME is on sys.path for intent_classifier import
        if str(VESSENCE_HOME) not in sys.path:
            sys.path.insert(0, str(VESSENCE_HOME))
        from intent_classifier.v2.classifier import CHROMA_PATH, _embed_fn, _load
        import chromadb
        import time
        _load()
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        col = client.get_collection("intent_v2")
        ts = int(time.time())
        doc_id = f"{cls_upper}_audit_{ts}"
        vec = _embed_fn([prompt])[0]
        col.add(
            ids=[doc_id], documents=[prompt], embeddings=[vec],
            metadatas=[{"class": cls_upper}],
        )
        logger.info("Added exemplar: %r → %s (%s)", prompt[:60], cls_upper, doc_id)
        return True
    except Exception as e:
        logger.warning("add_exemplar failed: %s", e)
        return False


# ── Main loop ───────────────────────────────────────────────────────────────


async def main(n: int = 100, apply_fixes: bool = True) -> int:
    started = datetime.datetime.now()
    logger.info("Loading last %d prompts from %s", n, PROMPT_DUMP)
    prompts = load_recent_prompts(n)
    logger.info("Loaded %d unique prompts", len(prompts))
    if not prompts:
        logger.warning("No prompts to audit. Exiting.")
        return 1

    # Aggregate counters
    stage_counts = Counter()
    class_counts = Counter()
    classification_failures = []
    response_failures = []
    fixes_applied = 0
    fixes_by_class = Counter()

    session_base = f"audit-{int(started.timestamp())}"
    for i, row in enumerate(prompts, 1):
        prompt = row["prompt"]
        sid = f"{session_base}-{i}"
        logger.info("[%d/%d] %r", i, len(prompts), prompt[:80])

        # Run through the live pipeline
        result = await run_through_pipeline(prompt, sid)
        if result.get("error"):
            logger.warning("Pipeline error: %s", result["error"])
            continue

        # Get the actual Stage 1 classification (events don't carry it reliably)
        if not result.get("classification"):
            result["classification"] = await classify_only(prompt)
        actual_class = (result.get("classification") or "").split(":")[0].strip()
        stage = result.get("stage") or "?"
        stage_counts[stage] += 1
        class_counts[actual_class] += 1

        # Judge with LLM
        verdict = await judge(prompt, result)
        if verdict.get("error"):
            logger.warning("Judge error: %s", verdict["error"])
            continue

        correct_class = verdict.get("correct_class", "")
        cls_ok = verdict.get("classification_ok", True)
        resp_ok = verdict.get("response_ok", True)

        if not cls_ok and correct_class and correct_class in KNOWN_CLASSES:
            classification_failures.append({
                "prompt": prompt,
                "got": actual_class,
                "should_be": correct_class,
            })
            if apply_fixes:
                if add_exemplar(prompt, correct_class):
                    fixes_applied += 1
                    fixes_by_class[correct_class] += 1

        if not resp_ok:
            response_failures.append({
                "prompt": prompt,
                "classification": actual_class,
                "stage": stage,
                "response": result.get("response", "")[:200],
            })

    # Write report
    elapsed = (datetime.datetime.now() - started).total_seconds()
    report_lines = [
        f"# Pipeline Audit Report — {started.strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"- Prompts audited: **{len(prompts)}**",
        f"- Elapsed: {elapsed:.0f}s",
        f"- Classification failures: **{len(classification_failures)}**",
        f"- Response failures: **{len(response_failures)}**",
        f"- Auto-fixes applied (exemplars added): **{fixes_applied}**",
        f"",
        f"## Stage breakdown",
    ]
    for stage, count in stage_counts.most_common():
        report_lines.append(f"- {stage}: {count}")
    report_lines.append("")
    report_lines.append("## Classification breakdown")
    for cls, count in class_counts.most_common():
        report_lines.append(f"- {cls}: {count}")
    report_lines.append("")
    if fixes_by_class:
        report_lines.append("## Self-correct fixes by class")
        for cls, count in fixes_by_class.most_common():
            report_lines.append(f"- {cls}: +{count} exemplars")
        report_lines.append("")
    if classification_failures:
        report_lines.append("## Classification failures (top 30)")
        report_lines.append("| Prompt | Got | Should be |")
        report_lines.append("|---|---|---|")
        for f in classification_failures[:30]:
            p = f["prompt"][:80].replace("|", "\\|")
            report_lines.append(f"| {p} | {f['got']} | {f['should_be']} |")
        report_lines.append("")
    if response_failures:
        report_lines.append("## Response failures (top 20) — usually need code changes")
        for f in response_failures[:20]:
            p = f["prompt"][:80].replace("|", "\\|")
            report_lines.append(f"- **{p}** ({f['classification']}/{f['stage']}): {f['response'][:150]}")
        report_lines.append("")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(report_lines))
    logger.info("Report written to %s", REPORT_PATH)
    return 0


if __name__ == "__main__":
    n = 100
    apply = True
    if "--n" in sys.argv:
        n = int(sys.argv[sys.argv.index("--n") + 1])
    if "--no-fixes" in sys.argv:
        apply = False
    sys.exit(asyncio.run(main(n=n, apply_fixes=apply)))
