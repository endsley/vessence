# Job #80: Hybrid Article Summarizer (WebView Extract + LLM Summarize)

Status: completed
Priority: medium
Created: 2026-04-21

## Problem

When sharing articles to Jane via Android, two paths exist:
1. **v1 (Summarize Now)**: Server fetches the URL with `requests.get()` and runs it through an LLM for summarization. Produces great summaries but fails on paywalled, Cloudflare-protected, or JS-rendered sites because the server has no cookies or JS engine.
2. **v2 (WebView)**: Android loads the page in a local WebView, extracts text with Readability.js, and sends it directly to TTS. Bypasses access issues since the phone's WebView has cookies and JS, but reads raw article text verbatim — no LLM summarization, so quality is poor.

## Solution

Use the phone's WebView to extract article text for **both** share paths — Summarize Now and Add to Briefing. The server should never need to fetch a URL itself.

### Summarize Now (upgrade v2)
1. Android WebView loads the article and extracts text via Readability.js (v2's existing extraction step)
2. POST the extracted text to a new server endpoint (e.g. `/api/briefing/articles/summarize_text`) with `{title, text, url}`
3. Server runs the text through the existing `summarize_full()` LLM pipeline
4. Returns `{title, summary}` back to Android
5. Android displays summary in SummaryReaderActivity and reads it via TTS

### Add to Briefing (same extraction, deferred summarization)
1. Android WebView loads the article and extracts text via Readability.js (same extraction step)
2. POST `{title, text, url}` to a new or updated briefing submit endpoint
3. Server stores the pre-extracted text alongside the URL so the briefing processor doesn't need to re-fetch
4. When briefing runs, it uses the stored text instead of calling `extract_article()` on the URL

## Files to Modify

- `android/app/src/main/java/com/vessences/android/ArticleReaderV2Activity.kt` — after Readability.js extraction, POST text to server instead of speaking raw text
- `jane_web/main.py` — add `/api/briefing/articles/summarize_text` endpoint that accepts `{title, text}` and returns `{title, summary}`
- `android/app/src/main/java/com/vessences/android/ShareReceiverActivity.kt` — both "Summarize Now" and "Add to Briefing" now go through WebView extraction first; remove the old v1 server-fetch path and the three-option dialog (simplify to two options)
- Briefing article storage/processor — accept pre-extracted text so it skips server-side fetch

## Summary Style

- Full comprehensive summary — same depth as the current v1 `summarize_full()` output
- No prompt changes needed; reuse the existing summarization pipeline as-is
- Optimized for listening (TTS) — clear, conversational phrasing

## Acceptance Criteria

- Sharing a paywalled/Cloudflare-blocked article produces an LLM-quality summary
- Summary is full comprehensive style — same depth as the current v1 `summarize_full()` output
- The share dialog is simplified (ideally "Summarize Now" and "Add to Briefing" — no v2 option needed since hybrid replaces it)
- Fallback: if server is unreachable, fall back to v2 behavior (raw TTS)
