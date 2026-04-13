# v2 3-Stage Prompt Pipeline

**Last updated:** 2026-04-12

---

## Overview

When a user sends a message to Jane (web or Android), the v2 pipeline processes it through 3 stages. Each stage is a gate — if the current stage can handle the request, it responds immediately. If not, it escalates to the next stage.

```
User prompt
    │
    ▼
┌──────────────────────────────────────────────┐
│  STAGE 1 — Classify (ChromaDB, ~25ms)        │
│  Pure vector similarity, no LLM              │
│  Returns: class name + confidence (High/Low) │
└──────────┬───────────────────────────────────┘
           │
     ┌─────┴─────┐
     │ High conf │──────────────────────────┐
     │ + known   │                          │
     │ class     │                          ▼
     └─────┬─────┘              ┌───────────────────────┐
           │                    │  STAGE 2 — Class       │
     Low conf                   │  Handler (~0.5-2s)     │
     or "others"                │  Per-class specialist  │
           │                    │  (local LLM or code)   │
           │                    └───────────┬────────────┘
           │                          ┌─────┴─────┐
           │                          │ Handled?  │
           │                     Yes──┤           ├──No (returns None)
           │                     │    └───────────┘    │
           │                     ▼                     │
           │              [Return to user]             │
           │                                           │
           ▼                                           ▼
┌──────────────────────────────────────────────────────────┐
│  STAGE 3 — Opus / Standing Brain (~3-30s)                │
│  Full context: memory, FIFO, tools, conversation history │
│  Handles everything Stage 2 can't                        │
└──────────────────────────────────────────────────────────┘
```

## Stage 1 — Classify

**What:** Determines which class (intent) the user's prompt belongs to.

**How:** ChromaDB vector similarity with BAAI/bge-small-en-v1.5 embeddings (384 dimensions). No LLM involved.

**Algorithm:**
1. Embed the user's message
2. Find the 5 nearest neighbors in ChromaDB (cosine distance)
3. If nearest neighbor distance > 0.30 → `DELEGATE_OPUS` (too far from any trained class)
4. Majority vote across the 5 neighbors
5. If vote fraction ≥ 0.80 AND margin ≥ 0.40 → return winning class with High confidence
6. Otherwise → `DELEGATE_OPUS` with Low confidence

**Speed:** ~25-50ms (embedding + ChromaDB lookup)

**Key files:**
- Classifier engine: `intent_classifier/v2/classifier.py`
- Class exemplar files: `intent_classifier/v2/classes/*.py`
- ChromaDB storage: `$VESSENCE_DATA_HOME/memory/v1/vector_db/intent_classifier_v2/`
- Pipeline wrapper: `jane_web/jane_v2/stage1_classifier.py` (maps ChromaDB names → pipeline names)

**Tuning env vars:**
- `JANE_V2_CONFIDENCE` — min vote fraction (default 0.80)
- `JANE_V2_MARGIN` — min vote gap (default 0.40)
- `JANE_V2_MAX_DISTANCE` — max cosine distance (default 0.30)

### Current Classes (11)

| ChromaDB Name | Pipeline Name | Exemplars | Stage 2 Handler? |
|---|---|---|---|
| WEATHER | weather | ~60 | Yes — gemma4:e2b + cached weather.json |
| MUSIC_PLAY | music play | ~75 | Yes — qwen2.5:7b + playlist DB |
| GREETING | greeting | ~130 | Yes — qwen2.5:7b, 1-sentence contextual reply |
| READ_MESSAGES | read messages | ~78 | No → Stage 3 |
| SEND_MESSAGE | send message | ~78 | Yes — qwen2.5:7b extracts recipient+body, resolves contact, fast-path sends |
| SYNC_MESSAGES | sync messages | ~68 | No → Stage 3 |
| SELF_HANDLE | self handle | ~110 | No → Stage 3 |
| SHOPPING_LIST | shopping list | ~51 | Yes — qwen2.5:7b extracts action+items, reads/writes JSON store |
| READ_EMAIL | read email | ~49 | No → Stage 3 |
| END_CONVERSATION | end conversation | ~88 | No → Stage 3 |
| DELEGATE_OPUS | others | ~130 | No → Stage 3 (catch-all) |

### Adding a New Class

1. Create `intent_classifier/v2/classes/my_class.py` with `CLASS_NAME` and `EXAMPLES` list
2. Create `jane_web/jane_v2/classes/my_class/metadata.py` with `METADATA` dict (name, ack, etc.)
3. Optionally create `jane_web/jane_v2/classes/my_class/handler.py` with `async def handle(prompt)`
4. Add the mapping in `jane_web/jane_v2/stage1_classifier.py` `_CLASS_MAP`
5. The ChromaDB collection auto-rebuilds when it detects the exemplar count changed

### Fixing a Misclassification

**Preferred method** — edit ChromaDB directly (no full rebuild):
```python
import chromadb
from intent_classifier.v2.classifier import CHROMA_PATH, _embed_fn, _load

_load()  # ensure embedding model is ready
client = chromadb.PersistentClient(path=str(CHROMA_PATH))
col = client.get_collection("intent_v2")

# Add a new exemplar
text = "the phrase that was misclassified"
vec = _embed_fn([text])[0]
col.add(
    ids=["CORRECT_CLASS_999"],
    documents=[text],
    embeddings=[vec],
    metadatas=[{"class": "CORRECT_CLASS"}],
)
```

**Bulk rebuild** — when adding many exemplars across multiple classes:
1. Edit the `.py` files in `intent_classifier/v2/classes/`
2. Delete `$VESSENCE_DATA_HOME/memory/v1/vector_db/intent_classifier_v2/`
3. Next `classify()` call rebuilds from all class files

---

## Stage 2 — Per-Class Handler

**What:** A lightweight, task-specific handler that can resolve the request without the full Opus brain.

**How:** Each class pack lives in `jane_web/jane_v2/classes/<name>/`. If `handler.py` exists and has `async def handle(prompt) -> dict | None`, it gets called. Returning `None` means "I can't handle this" → escalate to Stage 3.

**Classification Confirmation:** Every Stage 2 handler includes a WRONG_CLASS check. The LLM prompt starts with "The classifier thinks the user wants to [X]. First, confirm: is this actually [X]?" If the LLM says WRONG_CLASS, the handler returns None and Stage 3 takes over. This prevents misclassified prompts from being handled incorrectly by Stage 2.

**FIFO Context:** Stage 2 handlers receive the last 2 conversation turns from the FIFO, helping the LLM understand context for ambiguous prompts.

**Word Count Gate:** Prompts longer than 20 words skip Stage 1 entirely and go to Stage 3 — long prompts are almost always conversational, not commands.

**Key files:**
- Dispatcher: `jane_web/jane_v2/stage2_dispatcher.py`
- Class packs: `jane_web/jane_v2/classes/<name>/metadata.py` + optional `handler.py`
- Class registry: `jane_web/jane_v2/classes/__init__.py`

### Current Stage 2 Handlers

**Weather** (`jane_web/jane_v2/classes/weather/handler.py`):
- Reads cached `weather.json` from disk
- Sends weather data + user prompt to gemma4:e2b
- Returns 1-2 sentence spoken answer
- Escalates on: other cities, past weather, unsupported fields

**Greeting** (`jane_web/jane_v2/classes/greeting/handler.py`):
- Uses qwen2.5:7b with FIFO recent-turn context
- Returns 1-sentence warm, casual reply
- No ack shown (fast enough to respond directly)
- Escalates to Stage 3 if LLM call fails

**Send Message** (`jane_web/jane_v2/classes/send_message/handler.py`):
- Uses qwen2.5:7b to extract RECIPIENT, BODY, COHERENT from prompt
- Resolves recipient via `sms_helpers.resolve_recipient()` (aliases → contacts)
- Fast path (coherent + resolved): emits `[[CLIENT_TOOL:contacts.sms_send_direct:...]]` → "msg sent"
- Escalates to Stage 3 when: recipient unresolved, body garbled, no body specified

**Shopping List** (`jane_web/jane_v2/classes/shopping_list/handler.py`):
- Uses qwen2.5:7b to extract ACTION (add/remove/view/clear) and ITEMS
- Reads/writes `$VESSENCE_DATA_HOME/shopping_lists.json` directly
- No Opus needed for any list operation

**Music Play** (`jane_web/jane_v2/classes/music_play/handler.py`):
- Queries playlist DB via qwen2.5:7b
- Creates temporary playlists, resolves song/artist/genre
- Returns playlist_id that Android client picks up for playback

### Handler Return Format
```python
{"text": "Spoken response to user"}                              # simple
{"text": "Playing...", "playlist_id": "abc123", "playlist_name": "Coldplay"}  # with extras
None                                                              # escalate to Stage 3
```

---

## Stage 3 — Opus / Standing Brain

**What:** The full Jane brain — Claude Opus with conversation history, ChromaDB memory, tool access, and all capabilities.

**How:** Falls through from Stage 1 (low confidence / "others") or Stage 2 (handler returned None). Before Stage 3 runs, a contextual ack is generated via v1's `classify_prompt` so the user sees something while Opus thinks.

**Key files:**
- Escalation logic: `jane_web/jane_v2/stage3_escalate.py`
- Pipeline orchestrator: `jane_web/jane_v2/pipeline.py`
- v1 brain: `jane_web/main.py` (`_handle_jane_chat` / `stream_message`)

### Ack Generation

When escalating to Stage 3, the pipeline generates a contextual ack (e.g., "Checking the playlist — one sec.") using v1's gemma4-based `classify_prompt` with FIFO recent-turn summaries as context. This adds ~700ms but the ack arrives well before Opus's first token.

---

## Pipeline Entry Points

- **Non-streaming:** `jane_web/jane_v2/pipeline.py → handle_chat(body, request)` → returns JSONResponse
- **Streaming:** `jane_web/jane_v2/pipeline.py → handle_chat_stream(body, request)` → returns StreamingResponse (NDJSON)
- **Activation:** Set `JANE_PIPELINE=v2` and `JANE_USE_V2_PIPELINE=1` in `.env`

Both entry points share `_classify_and_try_stage2()` for Stages 1-2. Only Stage 3 differs (streaming vs. non-streaming v1 call).

---

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `JANE_PIPELINE` | `v2` | Selects pipeline version |
| `JANE_USE_V2_PIPELINE` | `1` | Enables v2 routing in main.py |
| `JANE_V2_CONFIDENCE` | `0.80` | Stage 1: min vote fraction for High confidence |
| `JANE_V2_MARGIN` | `0.40` | Stage 1: min vote gap for High confidence |
| `JANE_V2_MAX_DISTANCE` | `0.30` | Stage 1: max cosine distance before auto-reject |
| `JANE_STAGE1_TIMEOUT` | `10` | Stage 1 timeout (seconds) |
| `JANE_STAGE2_TIMEOUT` | `8` | Stage 2 timeout (seconds) |
| `INTENT_CLASSIFIER_MODEL` | `gemma4:e4b` | Model for Stage 2 weather handler |

---

## Test & Validation

- Test script: `test_code/test_stage1_100.py` — runs 100 historical prompts through the ChromaDB classifier
- Reports: `$VESSENCE_DATA_HOME/logs/jane_v2_3stage_stage1_100_*.jsonl`
- As of 2026-04-12: **100/100 accuracy** on the 100-prompt benchmark
