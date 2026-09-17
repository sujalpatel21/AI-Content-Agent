# Workflow: Content Scraper (Agent 01)

## Objective
Detect what's trending right now — not what competitors already posted — from free, public feeds, so downstream agents can write content that rides a live trend instead of yesterday's news.

## Required Inputs
- `CONTENT_KEYWORDS` in `.env` (comma-separated) — used to search Reddit/Google News when no topic is passed in
- `SCRAPE_DAYS_BACK` (default: 7)
- `TRENDS_GEO` (default: `US`) — region code for the Google Trends feed
- No API key required. Every source here is a free/public feed.

## Tool
```
python tools/content_scraper.py
```

## Sources
| Source | Method | Notes |
|--------|--------|-------|
| Google Trends | `trending/rss` feed | Unofficial but public endpoint. No auth. Traffic count is approximate, not a real view count. |
| Reddit | `search.rss` feed | No API key needed — the paid Reddit API tier and the old Apify actor are no longer used. Upvote counts aren't exposed in RSS; comment count is scraped from the entry content and upvotes/views are estimated from it. |
| Google News | `news.google.com/rss/search` | Already free/RSS-based, unchanged. |
| Hacker News | Firebase API | Already free, unchanged. |

**Quora is intentionally not scraped.** Quora has no public API and no RSS feed — pulling from it would mean scraping pages directly, which violates their ToS. Revisit only if a compliant path (official API, licensed data partner) shows up.

## Steps
1. Load keywords/topic from `.env` or CLI arg
2. Pull Google Trends RSS for the configured region
3. Pull Reddit search RSS for each keyword/topic
4. Pull Google News RSS for each keyword/topic
5. Pull Hacker News top stories, filtered to AI-relevant titles
6. Flag any item with estimated views ≥ 100K OR engagement rate ≥ 5% as `🔥 VIRAL` (Trends/News/HN items get a fixed trending tag instead, since their metrics are already synthesized as high-signal)
7. Sort all items by (estimated) views, highest first
8. Save to `.tmp/scraped_content_latest.json` and a timestamped backup

## Expected Output
- `.tmp/scraped_content_latest.json` — all trend items sorted by estimated views
- Console table showing top 20 items with viral flags

## Edge Cases
| Problem | Fix |
|---------|-----|
| Google Trends returns empty | The public RSS endpoint occasionally rate-limits by IP. Retry after a short delay; don't hammer it in a tight loop. |
| Reddit RSS returns 429 | Reddit throttles by User-Agent/IP on unauthenticated requests. Space out calls; don't run this on every trend on every cycle. |
| No posts returned | Lower `SCRAPE_DAYS_BACK` or broaden `CONTENT_KEYWORDS` |
| A feed's XML structure changes | Reddit/Google can change their RSS/Atom schema without notice since these are public-but-unofficial endpoints, not versioned APIs. If a source silently returns 0 items, check the raw feed in a browser first. |

## Known Limitation — Synthesized Metrics
None of these free feeds expose real view/like/comment counts the way a platform API would. Views/likes/comments in the output are **estimates derived from proxy signals** (Google Trends' approx_traffic, Reddit's comment count, HN's score) — good enough for ranking relative trend strength, not a substitute for real analytics. Do not report these numbers to anyone as actual view counts.

## Notes
- This agent no longer scrapes competitor social profiles (Instagram/YouTube/Twitter via Apify) — the pivot is topical/trend detection, not competitor benchmarking.
- Always run this before the validator.
