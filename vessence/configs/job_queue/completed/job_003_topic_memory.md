---
Job: #3
Title: Topic-based short-term memory system
Priority: 1
Status: completed
Created: 2026-04-01
---

## Description
Replace the current per-turn short-term memory writes with topic-based rolling summaries across all platforms (CLI, web, Android).

## Requirements
1. Shared Python module () that handles:
   - Classify current turn's topic from user prompt + assistant response
   - Query existing short-term ChromaDB entries by embedding similarity
   - If match found (similarity > threshold) — merge new info into existing summary via Haiku, upsert
   - If no match — create new topic entry with initial summary
   - TTL still applies for auto-expiry

2. Use Haiku (claude-haiku-4-5-20251001) for:
   - Topic classification
   - Summary merging (given existing summary + new exchange, produce updated summary)

3. Integration points:
   - CLI: Fix context_summary_hook.sh path, call topic_memory module from Stop hook
   - Web: Replace per-turn writes in conversation_manager.py with topic_memory calls
   - Android: Uses same web pipeline, no separate work needed

4. Topic detection:
   - Compare new turn embedding against existing short-term entries
   - If closest match distance < threshold → same topic, update that entry
   - If all distances > threshold → new topic, create new entry
   - Haiku confirms/overrides the embedding-based classification

## Acceptance Criteria
- All 3 platforms write to short-term memory
- Topics auto-detected and auto-created
- Existing topic entries update in-place as conversation progresses
- Librarian retrieves topic-based entries correctly
- No cold-start latency issues (Haiku, not local LLM)

## Result
[ACK]Got it — working on this now.[/ACK]  Here's where we're at, Chieh. The MMD trigger word project is in Phase 2 of 5. Phase 1 is done — you've got 11 positive "hey jane" samples and 60 synthetic negatives collected, and the model is enrolled and saved. The threshold auto-calibration is working to
