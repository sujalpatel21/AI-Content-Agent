# Workflow: Content Validator (Agent 02)

## Objective
Score, filter, and cluster scraped posts to find what's working right now. Output a ranked topic list with a clear recommendation for today's reel.

## Required Inputs
- `.tmp/scraped_content_latest.json` (output from Agent 01)
- `MIN_VIEWS_FILTER` in `.env` (default: 10000)
- `MIN_ER_FILTER` in `.env` (default: 2.0)
- `VIRAL_VIEWS_THRESHOLD` in `.env` (default: 100000)
- `VIRAL_ER_THRESHOLD` in `.env` (default: 5.0)

## Tool
```
python tools/content_validator.py
```

## Steps
1. Load scraper output from `.tmp/scraped_content_latest.json`
2. **Filter** — remove posts with:
   - Views < `MIN_VIEWS_FILTER`
   - Engagement rate < `MIN_ER_FILTER`
   - Posted more than 30 days ago
3. **Score** each post (0–100 composite):
   - Views: 40% weight (normalised to VIRAL_VIEWS_THRESHOLD)
   - Engagement Rate: 35% weight (normalised to VIRAL_ER_THRESHOLD)
   - Comment volume: 25% weight (normalised to 10K)
4. **Cluster** remaining posts by topic using TF-IDF + KMeans (6 clusters)
5. **Rank** topics by average views
6. **Detect trends:**
   - Flag topics appearing 3+ times in top results → "REPEAT VIRAL SIGNAL"
   - Flag formats in top 10 → "SUSTAINED TREND"
7. **Generate recommendation** — top topic + reason with avg view count
8. Save to `.tmp/validated_content_latest.json`

## Expected Output
- Console: bold recommendation, top 5 topic table, top 3 formats
- `.tmp/validated_content_latest.json` — full ranked data

## Scoring Formula
```
score = (views/100K × 0.40 + ER/5% × 0.35 + comments/10K × 0.25) × 100
```

## Edge Cases
| Problem | Fix |
|---------|-----|
| All posts filtered out | Lower `MIN_VIEWS_FILTER` or `MIN_ER_FILTER` in `.env` |
| Clustering fails (too few posts) | System falls back to "General AI Content" label |
| Input file missing | Run Agent 01 first |

## Notes
- Clustering accuracy improves with more posts (aim for 30+)
- Recommendation is based on average views — highest wins
