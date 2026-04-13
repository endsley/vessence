"""
Stage 1 v2 — embedding-based intent classifier.

Replaces gemma_stage1.py. No LLM involved — pure vector similarity.

  classify(message) → {"classification": "SEND_MESSAGE", "confidence": 0.80, "margin": 0.40}

On low confidence returns {"classification": "DELEGATE_OPUS", "confidence": ..., "margin": ...}.
Metadata extraction (RECIPIENT, BODY, FILTER, etc.) is handled downstream by Stage 2.
"""

from __future__ import annotations

import importlib
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
_HERE       = Path(__file__).resolve().parent
CLASSES_DIR = _HERE / "classes"
CHROMA_PATH = Path(os.environ.get(
    "VESSENCE_DATA_HOME", Path.home() / "ambient/vessence-data"
)) / "memory/v1/vector_db/intent_classifier_v2"

# ── Thresholds ─────────────────────────────────────────────────────────────────
CONFIDENCE_THRESHOLD = float(os.environ.get("JANE_V2_CONFIDENCE",    "0.60"))  # min vote fraction (3/5 votes)
MARGIN_THRESHOLD     = float(os.environ.get("JANE_V2_MARGIN",        "0.20"))  # min vote gap (1 vote spread)
MAX_DISTANCE         = float(os.environ.get("JANE_V2_MAX_DISTANCE",  "0.30"))  # max cosine distance for nearest neighbor
TOP_K = 5

# ── Module-level singletons (loaded once on first classify() call) ─────────────
_registry   = None   # {CLASS_NAME: module}
_embed_fn   = None   # callable: list[str] → list[vector]
_collection = None   # chromadb collection


def _load():
    global _registry, _embed_fn, _collection
    if _collection is not None:
        # Verify the collection still exists AND matches the current exemplar count.
        # If an external process (test script, CLI) rebuilt the collection with
        # different exemplars, the stale cached reference must be discarded.
        try:
            cached_count = _collection.count()
            # Quick-check: re-scan class files for expected count
            expected = 0
            for f in sorted(CLASSES_DIR.glob("*.py")):
                if f.name.startswith("_"):
                    continue
                mod = importlib.import_module(f"intent_classifier.v2.classes.{f.stem}")
                importlib.reload(mod)  # pick up file changes without full restart
                expected += len(mod.EXAMPLES)
            if cached_count == expected:
                return
            logger.info("[v2] Exemplar count changed (%d → %d), forcing reload", cached_count, expected)
        except Exception:
            logger.warning("[v2] Cached collection invalid, reloading")
        _collection = None
        _registry = None

    t0 = time.time()

    # Registry
    _registry = {}
    for f in sorted(CLASSES_DIR.glob("*.py")):
        if f.name.startswith("_"):
            continue
        mod = importlib.import_module(f"intent_classifier.v2.classes.{f.stem}")
        _registry[mod.CLASS_NAME] = mod

    # Embedding model
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("BAAI/bge-small-en-v1.5")
        _embed_fn = lambda texts: _model.encode(texts, normalize_embeddings=True).tolist()
    except Exception as e:
        logger.warning("SentenceTransformer unavailable (%s), falling back to ONNX", e)
        import chromadb.utils.embedding_functions as ef
        _onnx = ef.ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])
        _embed_fn = lambda texts: _onnx(texts)

    # Warm up
    _embed_fn(["warmup"])

    # ChromaDB collection — rebuild if stale or missing
    import chromadb
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))

    existing = {c.name for c in client.list_collections()}
    needs_build = "intent_v2" not in existing

    if not needs_build:
        col = client.get_collection("intent_v2")
        # Rebuild if example count changed — exclude DELEGATE_OPUS since it's not trained
        expected = sum(
            len(m.EXAMPLES) for cls, m in _registry.items()
        )
        if col.count() != expected:
            logger.info("[v2] Example count changed (%d → %d), rebuilding", col.count(), expected)
            client.delete_collection("intent_v2")
            needs_build = True

    if needs_build:
        logger.info("[v2] Building ChromaDB collection from %d classes…", len(_registry))
        col = client.create_collection("intent_v2", metadata={"hnsw:space": "cosine"})
        ids, docs, metas = [], [], []
        for cls_name, mod in _registry.items():
            for i, ex in enumerate(mod.EXAMPLES):
                ids.append(f"{cls_name}_{i}")
                docs.append(ex)
                metas.append({"class": cls_name})
        embeddings = _embed_fn(docs)
        col.add(ids=ids, documents=docs, embeddings=embeddings, metadatas=metas)
        logger.info("[v2] Collection ready: %d vectors", col.count())

    _collection = col
    logger.info("[v2] Classifier ready in %.2fs", time.time() - t0)


# Messages longer than this are almost certainly conversational, not commands.
# Skip the vector lookup entirely and send straight to Opus.
MAX_COMMAND_WORDS = int(os.environ.get("JANE_V2_MAX_COMMAND_WORDS", "20"))


def classify(message: str) -> dict:
    """
    Classify message using top-5 majority vote over ChromaDB.

    Returns dict with keys: classification, confidence, margin, latency_ms.
    """
    global _collection

    # Word-count gate: long prompts are conversation, not commands
    word_count = len(message.split())
    if word_count > MAX_COMMAND_WORDS:
        logger.debug(
            "[v2] %r → DELEGATE_OPUS (word_count=%d > MAX=%d) 0ms",
            message[:60], word_count, MAX_COMMAND_WORDS,
        )
        return {
            "classification": "DELEGATE_OPUS",
            "confidence":     0.0,
            "margin":         0.0,
            "latency_ms":     0.0,
        }

    _load()

    t0 = time.time()
    vec = _embed_fn([message])[0]
    try:
        results = _collection.query(
            query_embeddings=[vec],
            n_results=min(TOP_K, _collection.count()),
            include=["metadatas", "distances"],
        )
    except Exception as e:
        if "does not exist" in str(e).lower() or "invalid collection" in str(e).lower():
            # Collection was deleted externally (e.g. manual rebuild) — reset and retry once
            logger.warning("[v2] Stale collection reference, resetting and retrying: %s", e)
            _collection = None
            _load()
            results = _collection.query(
                query_embeddings=[vec],
                n_results=min(TOP_K, _collection.count()),
                include=["metadatas", "distances"],
            )
        else:
            raise
    elapsed_ms = (time.time() - t0) * 1000

    distances = results["distances"][0]
    min_dist  = min(distances)

    # Reject if the closest neighbour is too far away — the input doesn't
    # resemble any training example, so any majority vote is noise.
    if min_dist > MAX_DISTANCE:
        logger.debug(
            "[v2] %r → DELEGATE_OPUS (min_dist=%.4f > MAX_DISTANCE=%.2f) %.0fms",
            message[:60], min_dist, MAX_DISTANCE, elapsed_ms,
        )
        return {
            "classification": "DELEGATE_OPUS",
            "confidence":     0.0,
            "margin":         0.0,
            "latency_ms":     round(elapsed_ms, 1),
        }

    metas = results["metadatas"][0]
    votes: dict[str, int] = {}
    for meta in metas:
        cls = meta["class"]
        votes[cls] = votes.get(cls, 0) + 1

    sorted_votes  = sorted(votes.items(), key=lambda x: -x[1])
    top_cls       = sorted_votes[0][0]
    top_votes     = sorted_votes[0][1]
    second_votes  = sorted_votes[1][1] if len(sorted_votes) > 1 else 0
    vote_fraction = top_votes / TOP_K
    margin        = (top_votes - second_votes) / TOP_K

    high_conf = vote_fraction >= CONFIDENCE_THRESHOLD and margin >= MARGIN_THRESHOLD
    final_cls = top_cls if high_conf else "DELEGATE_OPUS"

    logger.debug(
        "[v2] %r → %s (votes=%s frac=%.2f margin=%.2f conf=%s min_dist=%.4f) %.0fms",
        message[:60], final_cls, dict(sorted_votes), vote_fraction, margin, high_conf, min_dist, elapsed_ms,
    )

    return {
        "classification": final_cls,
        "confidence":     round(vote_fraction, 4),
        "margin":         round(margin, 4),
        "latency_ms":     round(elapsed_ms, 1),
    }


async def stage1_classify(message: str, session_id: str = "") -> dict:
    """Async wrapper — drop-in replacement for gemma_stage1.stage1_classify."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, classify, message)
