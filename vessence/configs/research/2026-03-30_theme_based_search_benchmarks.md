# Research: Theme-Based Memory Search (Gated Retrieval)

**Date:** 2026-03-30
**Status:** Deferred (Benchmark Failed to Justify Implementation)

## 1. The Idea
The core concept was to move from a **"Wide-Open"** parallel search (where all 16 memory categories are searched for every query) to a **"Theme-Gated"** search. 

In this new model, a high-speed local classifier would analyze the user's intent *first*, identify the relevant "Sweet 16" themes (e.g., *Identity Evolution*, *Debugging Wisdom*), and then restrict the ChromaDB query to only those specific categories using metadata filtering (`where={"topic": {"$in": [...]}}`).

## 2. Motivation
- **Noise Reduction**: Prevent irrelevant memories from "clogging" the context window.
- **Improved Synthesis**: Provide the Librarian model with higher-quality, more targeted inputs.
- **Scaling**: Prepare the system for a future where the vector database grows from 1,000 to 10,000+ entries, where wide-open search might become too noisy or slow.

## 3. Benchmarks (64-Sample Intent Test)
We ran a comprehensive benchmark across 64 varied prompts (approx. 4 per Sweet 16 category) using local and cloud-based models. We used descriptive theme prompts to help the models understand the categories.

| Model | Accuracy % | Avg Latency | Decision |
| :--- | :--- | :--- | :--- |
| **Gemma3:4b** | 45.0% | 0.68s | Rejected (Too inaccurate) |
| **Qwen2.5-Coder:14b** | 79.7% | **0.45s** | Rejected (Technically narrow) |
| **Gemma3:12b** | **89.1%** | 1.96s | Rejected (Accuracy/Speed trade-off) |
| **Claude 3.5 Haiku** | **95.0%** | 7.80s | Rejected (Too slow for pre-search) |

### Key Findings from Benchmarking:
- **Zero-Shot Complexity**: Categorizing intent into 16 abstract buckets is difficult for small models. Even with descriptions, the best local model (Gemma3:12b) missed ~11% of intents.
- **Latency Penalty**: Adding ~2 seconds of "thinking" time before even starting the memory search makes the overall user experience feel sluggish.
- **Critical Failure Risk**: If the classifier misses a theme (e.g., fails to link "Emily" to "Identity Evolution"), the memory is hidden from the agent entirely, leading to "hallucinated" forgetfulness.

## 4. Final Conclusion
**Decision: Retain Wide-Open Parallel Search.**

The benchmark demonstrated that the classifier's accuracy (max 89% locally) is not high enough to justify the 2-second latency penalty. Our current "Wide-Open" search is faster (sub-second) and safer because it allows the **Librarian** (Gemma3:4b) to filter noise *after* retrieval, which is more robust than gating retrieval *before* it happens.

This idea should only be revisited if:
1. Local model reasoning improves to 98%+ accuracy for this task.
2. The vector database size increases to a point where wide-open search results in unacceptable noise levels.

---
**Document Location:** `/home/chieh/ambient/vessence/configs/research/2026-03-30_theme_based_search_benchmarks.md`
