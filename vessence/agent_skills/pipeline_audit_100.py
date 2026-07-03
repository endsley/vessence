"""pipeline_audit_100.py — end-to-end audit of the 3-stage pipeline on real prompts.

Pulls the last N (default 100) user prompts from the prompt dump log,
runs each through the live pipeline, and uses qwen2.5:7b as a judge to
evaluate each stage:
  - Stage 1: was the classification correct?
  - Stage 2: did the handler do the right thing? (or correctly escalate?)
  - Stage 3: did Opus's response actually answer the user?

By default this is report-only: it does not mutate classifier training
data. With --apply-fixes, Stage 1 misclassifications with a clear correct
class are added as exemplars to the correct ChromaDB class.

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
import sys
from collections import Counter, defaultdict
from pathlib import Path

import httpx
from agent_skills.pipeline_audit_helpers import (
    build_judge_prompt as _build_judge_prompt,
    build_pipeline_audit_report_markdown as _build_pipeline_audit_report_markdown,
    parse_judge_response as _parse_judge_response,
    recent_prompt_rows_from_jsonl as _recent_prompt_rows_from_jsonl,
    strip_system_context as _strip_system_context,
    summarize_pipeline_events as _summarize_pipeline_events,
)

VESSENCE_HOME = Path(os.environ.get("VESSENCE_HOME", str(Path(__file__).resolve().parents[1])))
VESSENCE_DATA_HOME = Path(os.environ.get("VESSENCE_DATA_HOME", str(Path.home() / "ambient/vessence-data")))
PROMPT_DUMP = VESSENCE_DATA_HOME / "logs" / "jane_prompt_dump.jsonl"
REPORT_PATH = VESSENCE_HOME / "configs" / "pipeline_audit_report.md"
try:
    sys.path.insert(0, str(VESSENCE_HOME))
    from jane_web.jane_v2.models import AUDIT_JUDGE_MODEL as JUDGE_MODEL, OLLAMA_URL
except Exception:
    JUDGE_MODEL = (
        os.environ.get("JANE_AUDIT_JUDGE_MODEL")
        or os.environ.get("JANE_LOCAL_LLM")
        or os.environ.get("JANE_STAGE2_MODEL")
    )
    if not JUDGE_MODEL:
        raise RuntimeError(
            "Cannot resolve audit judge model: models.py import failed AND "
            "no JANE_AUDIT_JUDGE_MODEL / JANE_LOCAL_LLM env var is set"
        )
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
    with PROMPT_DUMP.open() as f:
        return _recent_prompt_rows_from_jsonl(f, n)


# ── Live pipeline runner ────────────────────────────────────────────────────


async def classify_only(prompt: str) -> str:
    """Fast classify-only path — uses the same wrapper the pipeline uses."""
    try:
        sys.path.insert(0, str(VESSENCE_HOME)) if str(VESSENCE_HOME) not in sys.path else None
        from jane_web.jane_v2.stage1_classifier import classify
        cls, conf, dist = await classify(prompt)
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

    return _summarize_pipeline_events(events)


# ── LLM judge ───────────────────────────────────────────────────────────────


async def judge(prompt: str, result: dict) -> dict:
    """Ask qwen to evaluate the pipeline output. Returns a verdict dict."""
    judge_prompt = _build_judge_prompt(prompt, result, KNOWN_CLASSES)
    # MUST match every other local-LLM caller's num_ctx. Divergent num_ctx
    # forces Ollama to evict/reload the runner on each caller swap.
    try:
        from jane_web.jane_v2.models import LOCAL_LLM_NUM_CTX as _NUM_CTX
    except Exception:
        _NUM_CTX = int(os.environ.get("JANE_LOCAL_LLM_NUM_CTX", "8192"))
    body = {
        "model": JUDGE_MODEL,
        "prompt": judge_prompt,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 80, "num_ctx": _NUM_CTX},
        "keep_alive": "1h",
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(OLLAMA_URL, json=body)
            r.raise_for_status()
            raw = (r.json().get("response") or "").strip()
    except Exception as e:
        return {"error": str(e)}

    return _parse_judge_response(raw)


# ── Self-correct: add prompt to correct class in ChromaDB ───────────────────


def add_exemplar(prompt: str, target_class: str) -> bool:
    """Add prompt as an exemplar to the named class in ChromaDB."""
    # DISABLED per user request (2026-04-21). Nightly Chroma writes are
    # ephemeral (wiped on next source-edit rebuild) and the judge's
    # verdict is not reliable enough to auto-mutate the corpus. Re-enable
    # by removing this early return.
    cls_upper = target_class.upper().replace(" ", "_")
    if cls_upper == "OTHERS":
        cls_upper = "DELEGATE_OPUS"
    logger.info(
        "add_exemplar DISABLED: would have added %r → %s",
        prompt[:60], cls_upper,
    )
    return False
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


async def main(n: int = 100, apply_fixes: bool = False) -> int:
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
            # Highest-leverage auto-fix: prompt that SHOULD have been a real class
            # but ended up in "others"/DELEGATE_OPUS — add it as an exemplar to
            # the correct class so Stage 1 catches it next time. Skip the
            # opposite case (real class but should be others) since adding to
            # DELEGATE_OPUS could over-train it.
            should_autofix = (
                apply_fixes
                and (actual_class == "others" or not actual_class)
                and correct_class != "others"
            )
            if should_autofix:
                if add_exemplar(prompt, correct_class):
                    fixes_applied += 1
                    fixes_by_class[correct_class] += 1
                    logger.info(
                        "AUTO-FIX: added %r to %s (was: %s)",
                        prompt[:60], correct_class, actual_class or "others",
                    )

        if not resp_ok:
            response_failures.append({
                "prompt": prompt,
                "classification": actual_class,
                "stage": stage,
                "response": result.get("response", "")[:200],
            })

    # Write report
    elapsed = (datetime.datetime.now() - started).total_seconds()
    report_markdown = _build_pipeline_audit_report_markdown(
        started=started,
        prompt_count=len(prompts),
        elapsed_seconds=elapsed,
        stage_counts=stage_counts,
        class_counts=class_counts,
        classification_failures=classification_failures,
        response_failures=response_failures,
        fixes_applied=fixes_applied,
        fixes_by_class=fixes_by_class,
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report_markdown)
    logger.info("Report written to %s", REPORT_PATH)
    return 0


if __name__ == "__main__":
    n = 100
    apply = False
    if "--n" in sys.argv:
        n = int(sys.argv[sys.argv.index("--n") + 1])
    if "--apply-fixes" in sys.argv:
        apply = True
    if "--no-fixes" in sys.argv:
        apply = False
    sys.exit(asyncio.run(main(n=n, apply_fixes=apply)))
