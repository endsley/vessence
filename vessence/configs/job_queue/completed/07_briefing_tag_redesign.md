# Job: Daily Briefing Tag-Based Redesign

Status: complete
Priority: 2
Created: 2026-03-22

## Objective
Redesign the Daily Briefing from topic-based filtering to a tag + category system that scales to hundreds of topics.

## Current Design (problems)
- Topics are flat buttons in a horizontal row — breaks at 10+ topics
- Each article belongs to exactly one topic
- No concept of categories or relevance ranking

## New Design

### Data Model Changes

**Topics → Tags (keywords)**
- Each "topic" the user adds becomes a set of tags/keywords (already is — `keywords` field in `topics.json`)
- Flatten: every keyword across all topics becomes a tag
- Tags are grouped into user-defined **categories** (Tech, Politics, Health, Sports, etc.)

**Article tagging**
- When an article is fetched, it gets tagged with ALL matching keywords (not just the topic it was fetched for)
- An article about "NVIDIA using AI in healthcare" would get tags: `NVIDIA`, `GPU`, `AI`, `health` — spanning both Tech and Health categories
- Tag matching: check if any keyword appears in the article's title or summary text

**Relevance sorting**
- Articles sorted by number of matching tags (descending)
- More tags = more relevant to the user's interests = higher position
- Within same tag count, sort by recency

### UI Changes

**Category bar (replaces topic buttons)**
- Show broad categories as filter buttons: All | Tech | Politics | Health | Sports | etc.
- Categories are user-defined or auto-derived from topic groupings
- Clicking a category filters to articles that have at least one tag in that category

**Article cards**
- Each card shows its matched tags as small colored chips below the title
- Tags are color-coded by category
- A news article must have at least one matching tag to appear at all

**Topics.json schema change**
```json
{
  "categories": [
    {
      "name": "Tech",
      "tags": ["NVIDIA", "GPU", "AI", "Claude", "Anthropic", "OpenAI", "Gemini", "Google AI"]
    },
    {
      "name": "Politics",
      "tags": ["Iran war", "Iran conflict", "sanctions"]
    },
    {
      "name": "Health",
      "tags": ["anti-aging", "longevity", "senolytics"]
    }
  ]
}
```

Or keep backward compatible by adding a `category` field to each existing topic:
```json
{
  "topics": [
    {
      "name": "NVIDIA",
      "keywords": ["NVIDIA", "GPU", "CUDA"],
      "category": "Tech",
      "priority": "high"
    }
  ]
}
```

### Fetcher Changes
- When processing an article, scan its title + summary against ALL keywords across ALL topics
- Attach all matching keywords as tags on the article
- Store tags in the article JSON: `"tags": ["NVIDIA", "GPU", "AI"]`
- Derive category from which topics those tags belong to

### API Changes
- `GET /api/briefing/articles` — returns articles with `tags` field, sorted by tag count desc
- `GET /api/briefing/articles?category=Tech` — filter by category
- `GET /api/briefing/categories` — returns list of categories with tag counts

### Display Rules
- An article with 0 matching tags is never shown
- Default view: "All" category, sorted by tag count (most relevant first)
- Category filter narrows to articles with tags in that category
- Same tag-count sort within category

## Files Involved
- `essences/daily_briefing/user_data/topics.json` — add category field
- `essences/daily_briefing/functions/news_fetcher.py` — multi-tag matching
- `essences/daily_briefing/functions/custom_tools.py` — update add_topic to accept category
- `vault_web/templates/briefing.html` — category bar + tag chips + relevance sort
- `jane_web/main.py` — update briefing API endpoints
- `android/.../BriefingScreen.kt` — same UI changes
- `android/.../BriefingViewModel.kt` — category filtering + tag sort

## Notes
- Backward compatible: existing topics without `category` default to "General"
- Jane should be able to create categories and assign topics to them via conversation
- When user says "add NVIDIA to my briefing under Tech", Jane sets category="Tech"
- Categories with 0 articles in the current batch are hidden from the filter bar
