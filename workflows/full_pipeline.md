# Workflow: Full Pipeline (All 4 Agents)

## Objective
Run the entire content pipeline in one command — from raw scraping to a camera-ready script with 5 hooks. Total time: ~3 minutes.

## Required Inputs
All credentials set in `.env`:
- `APIFY_API_KEY`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`

Config filled in:
- `config/voice_profile.json` — creator tone + past scripts

## Commands

```bash
# Full run (scrape + validate + write + hooks):
python tools/run_pipeline.py

# Full run with a specific topic:
python tools/run_pipeline.py "How I automated my Instagram with Claude Code"

# Skip scraping (reuse yesterday's data, saves ~90s):
python tools/run_pipeline.py --skip-scrape

# Skip scraping + custom topic:
python tools/run_pipeline.py --skip-scrape "AI tools that save 3 hours a day"
```

## Pipeline Flow

```
Agent 01 (Scraper)
    ↓ .tmp/scraped_content_latest.json
Agent 02 (Validator)
    ↓ .tmp/validated_content_latest.json
Agent 03 (Voice Writer)
    ↓ .tmp/script_latest.json
Agent 04 (Hook Generator)
    ↓ .tmp/hooks_latest.json
```

## What You Get at the End

1. **Validated topic** — top ranked topic with avg view count + reason
2. **Full script** — Beat 1 → Beat 2 → Beat 3 → CTA, in your voice
3. **5 hooks** — one per pattern, with confidence scores
4. **Recommended hook** — which one to use today and why

## Daily Usage (Recommended)

Run every morning before filming:
```bash
python tools/run_pipeline.py
```
This takes ~3 minutes. You will never wonder what to post again.

On days when you already know your topic:
```bash
python tools/run_pipeline.py --skip-scrape "your topic here"
```
This takes ~30 seconds.

## Edge Cases

| Problem | Fix |
|---------|-----|
| Agent 01 fails | Check `APIFY_API_KEY`. Run `python tools/content_scraper.py` alone to debug. |
| Agent 02 filters everything out | Lower `MIN_VIEWS_FILTER` in `.env` |
| Agent 03 / 04 fail | Check `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` in `.env` |
| Pipeline exits early | Each agent prints its error. Check that agent's workflow doc. |

## Output Files

| File | Contents |
|------|---------|
| `.tmp/scraped_content_latest.json` | All scraped posts sorted by views |
| `.tmp/validated_content_latest.json` | Filtered + scored + clustered posts + recommendation |
| `.tmp/script_latest.json` | Full script in creator's voice |
| `.tmp/hooks_latest.json` | 5 hooks with confidence scores |

All files are also saved with timestamps for historical reference.

## Notes
- `.tmp/` files are disposable — they are regenerated each run
- Timestamped backups persist indefinitely in `.tmp/`
- Never store credentials anywhere except `.env`
