# Workflow: Content Scraper (Agent 01)

## Objective
Pull viral posts from Instagram Reels, YouTube Shorts, and Twitter/X for a defined niche and keyword set. Flag high-performing posts and transcribe top videos.

## Required Inputs
- `APIFY_API_KEY` in `.env`
- `CONTENT_KEYWORDS` in `.env` (comma-separated)
- `COMPETITOR_HANDLES_INSTAGRAM/YOUTUBE/TWITTER` in `.env`
- `SCRAPE_DAYS_BACK` (default: 7)

## Tool
```
python tools/content_scraper.py
```

## Steps
1. Load keywords and competitor handles from `.env`
2. Run Apify actor for Instagram Reels (hashtag + profile scrape)
3. Run Apify actor for YouTube Shorts (keyword search, duration filter)
4. Run Apify actor for Twitter/X (keyword search, last N days)
5. For each post: collect hook text, full caption, views, likes, comments, ER, post date, URL
6. Transcribe videos with ≥50K views using OpenAI Whisper
7. Flag any post with ER ≥ 5% OR views ≥ 100K as `🔥 VIRAL`
8. Sort all posts by views (highest first)
9. Save to `.tmp/scraped_content_latest.json` and timestamped backup

## Expected Output
- `.tmp/scraped_content_latest.json` — all posts sorted by views
- Console table showing top 20 posts with viral flags

## Edge Cases
| Problem | Fix |
|---------|-----|
| Apify actor fails | Check actor ID in `.env`. Visit console.apify.com to verify the actor is still active. |
| No posts returned | Lower `SCRAPE_DAYS_BACK` or broaden keywords |
| Whisper fails | Check `OPENAI_API_KEY`. Transcription is non-blocking — script continues without it. |
| Rate limit from Apify | Add `time.sleep(2)` between actor calls. Document here. |

## Notes
- Transcription is only triggered for posts with ≥50K views to manage OpenAI costs
- Always run this before the validator
