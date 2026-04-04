# Daily Briefing Essence — Spec

**Status:** Default essence (ships with Vessence)

## Overview
A news aggregation essence that fetches, summarizes, and presents news twice daily based on user-defined topics/keywords. Think Google News but personalized and AI-summarized.

## UI — Card Grid View (Google News style)
- Scrollable card layout, each card has:
  - **Headline** (from source)
  - **Downloaded image** (cached locally in essence folder)
  - **Brief AI-generated summary** (2-3 sentences) — shown by default
  - **Source + timestamp**
  - **"Expand" button** — fetches and displays a comprehensive summary of the full article
  - **"Read article" button** — opens original link in browser
  - **"Read to me" button** — TTS reads the summary aloud
- **"Read all" mode** — essence reads title + summary of every card sequentially via TTS
- Cards grouped by topic/category

## Two-Level Summary
- **Brief** (default on card): 2-3 sentence overview from headline + first paragraphs. Fast, cheap.
- **Comprehensive** (on demand): User taps "Expand" → essence fetches full article text, runs LLM to produce a detailed summary (key points, context, implications). Saved alongside the brief so it's instant on subsequent views.

## News Sources (multi-source, prioritized)
1. **Google News RSS** — free, unlimited, good topic coverage, returns headlines + links
2. **Free news APIs** (NewsAPI free tier, etc.) — structured data, images included
3. **Web scraping** — fallback for full article text when RSS/API only gives snippets
- For each article: try RSS/API for metadata first, then scrape full text for summarization

## Topic Management
- Essence provides a UI for the user to create/edit a keyword/theme list
- Examples: "AI research", "machine learning", "NBA", "tech industry", "kernel methods"
- Each topic is a saved search — the essence uses these to query news sources
- Topics stored in the essence's `user_data/topics.json`

## Data & Memory
- **Own ChromaDB collection** — each article gets:
  - Summary vectorized for semantic search
  - Metadata: title, source URL, publish date, topic
  - Points to saved summarized text file in the essence folder
- **Images downloaded** and cached in `essence_data/images/` — referenced by article ID
- **Article text saved** in `essence_data/articles/{id}_brief.md` and `{id}_full.md`
- **Conversational recall** — if the user mentions something from a past briefing in any chat (Jane or Amber), the memory retrieval layer searches this essence's ChromaDB and surfaces the relevant article context
- Memory persists across briefings — builds up a personal news archive

## Schedule
- Twice daily (configurable — morning and evening)
- Cron job triggers the fetch → summarize → store → notify pipeline
- User gets a notification when new briefing is ready

## Data Flow
1. Cron triggers fetch for each topic keyword (RSS → API → scrape)
2. For each article: download image, generate brief summary, store both
3. Index summary + metadata in ChromaDB
4. Push notification to user (Android/web) that briefing is ready
5. User opens essence → sees card grid of latest news
6. User taps "Expand" → comprehensive summary generated on demand (then cached)
