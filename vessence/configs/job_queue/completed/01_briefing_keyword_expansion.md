# Job: Briefing Keyword Expansion — LLM-Powered Search Term Enrichment

Status: complete
Completed: 2026-03-23
Notes: Added expand_keywords() to news_fetcher.py with 7-day cache. Controlled by BRIEFING_EXPAND_KEYWORDS=1 env var (set locally). Code default is off (Docker users unaffected). Smoke tested with RA topic — expanded 3→11 keywords.
Priority: 2
Created: 2026-03-23

## Objective
Add an LLM-powered keyword expansion step to the Daily Briefing pipeline so that user-provided keywords are automatically enriched with related terms before querying Google News RSS. This catches articles that discuss the same concept using different terminology.

## Current Flow
```
User keywords → raw OR query → Google News RSS → articles
```

## Target Flow
```
User keywords → LLM expands to related terms → enriched OR query → Google News RSS → articles
```

## Design

### 1. Keyword Expansion Function
In `news_fetcher.py`, add `expand_keywords(topic_name, keywords)`:
- Takes the topic name and user keywords
- Calls the configured LLM (BRIEFING_SUMMARY_MODEL env var, deepseek-r1:32b locally)
- Prompt: "Given the topic '{name}' and these keywords: {keywords}, suggest 5-10 additional related search terms that would catch relevant articles using different terminology. Return only the terms, one per line."
- Cache the expanded keywords per topic (7-day TTL) to avoid calling the LLM on every fetch
- Store cache in `working_files/keyword_expansion_cache.json`

### 2. Integration Point
In `fetch_topic_articles()`, before building the Google News query:
1. Load cached expansion (if fresh)
2. If stale or missing, call `expand_keywords()`
3. Merge expanded terms with user keywords (deduplicated)
4. Build the OR query with all terms

### 3. Cache Structure
```json
{
  "rheumatoid_arthritis": {
    "expanded": ["joint inflammation", "TNF inhibitor", "methotrexate", "autoimmune joint disease", "RA biologics"],
    "last_expanded": "2026-03-23T12:00:00+00:00"
  }
}
```

### 4. Configurable
- `BRIEFING_EXPAND_KEYWORDS=1` env var (default: 0 for Docker, set to 1 locally)
- Uses same model as summarization (BRIEFING_SUMMARY_MODEL)
- Expansion is optional — if LLM fails, falls back to user keywords only

## Files Involved
- `essences/daily_briefing/functions/news_fetcher.py` — add expand_keywords(), integrate in fetch_topic_articles()
- `essences/daily_briefing/working_files/keyword_expansion_cache.json` — cache file
- `vessence-data/.env` — add BRIEFING_EXPAND_KEYWORDS=1 for local machine

## Notes
- Strip `<think>` tags from deepseek-r1 output (already handled by _strip_think_tags)
- Keep expanded terms reasonable (max 10 per topic to avoid overly broad queries)
- Log which expanded terms were used so we can evaluate quality
