# AI Content System

A 4-agent AI pipeline built on the **WAT framework** (Workflows → Agents → Tools).  
Scrapes viral content → validates what's working → writes your script → generates hooks.  
Total daily run time: **~3 minutes**.

---

## The 4 Agents

| Agent | Tool | What it does |
|-------|------|-------------|
| **01 — Content Scraper** | `tools/content_scraper.py` | Pulls viral posts from Instagram, YouTube & Twitter via Apify. Transcribes top videos with Whisper. |
| **02 — Validation Agent** | `tools/content_validator.py` | Scores posts (views 40%, ER 35%, comments 25%), filters low performers, clusters by topic, ranks what's working. |
| **03 — Voice Writer** | `tools/voice_writer.py` | Writes your reel script in your exact tone using Claude. Beat 1 → Beat 2 → Beat 3 → CTA. |
| **04 — Hook Generator** | `tools/hook_generator.py` | Generates 5 hook variations (aspirational, pain point, insider, claim, curiosity) with confidence scores. |

---

## Quick Start

### Step 1 — Install dependencies
```bash
pip install -r tools/requirements.txt
```

### Step 2 — Fill in `.env`
Open `.env` and add:
- `APIFY_API_KEY` → [console.apify.com](https://console.apify.com/account/integrations)
- `OPENAI_API_KEY` → [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- `ANTHROPIC_API_KEY` → [console.anthropic.com](https://console.anthropic.com/)
- Your competitor handles for Instagram, YouTube, Twitter

### Step 3 — Fill in your voice profile
Edit `config/voice_profile.json`:
- Add 20–30 of your past reel scripts to `past_scripts[]`
- Set your vocabulary, Hinglish pattern, CTA examples

### Step 4 — Run the full pipeline
```bash
# Full run (scrape + validate + write + hooks):
python tools/run_pipeline.py

# With a specific topic:
python tools/run_pipeline.py "Claude Code automation for beginners"

# Skip scraping, reuse yesterday's data (saves ~90s):
python tools/run_pipeline.py --skip-scrape
```

---

## Run Agents Individually

```bash
python tools/content_scraper.py          # Agent 01 — scrape
python tools/content_validator.py        # Agent 02 — validate
python tools/voice_writer.py             # Agent 03 — write script (auto topic)
python tools/voice_writer.py "my topic"  # Agent 03 — write script (custom topic)
python tools/hook_generator.py           # Agent 04 — generate hooks
```

---

## Directory Layout

```
AI Content System/
├── CLAUDE.md                       # Agent operating instructions (WAT framework)
├── README.md                       # This file
├── .env                            # ALL credentials go here (never commit)
├── .gitignore
│
├── config/
│   └── voice_profile.json          # Your tone, vocabulary, past scripts
│
├── tools/                          # Python scripts (deterministic execution)
│   ├── content_scraper.py          # Agent 01
│   ├── content_validator.py        # Agent 02
│   ├── voice_writer.py             # Agent 03
│   ├── hook_generator.py           # Agent 04
│   ├── run_pipeline.py             # Full orchestrator
│   └── requirements.txt
│
├── workflows/                      # Markdown SOPs (what to do and how)
│   ├── content_scraper.md
│   ├── content_validator.md
│   ├── voice_writer.md
│   ├── hook_generator.md
│   └── full_pipeline.md
│
└── .tmp/                           # Intermediate outputs (auto-generated, disposable)
    ├── scraped_content_latest.json
    ├── validated_content_latest.json
    ├── script_latest.json
    └── hooks_latest.json
```

---

## Credentials Reference

| Variable | Where to get it | Used by |
|----------|----------------|---------|
| `APIFY_API_KEY` | [console.apify.com](https://console.apify.com/account/integrations) | Agent 01 (scraping) |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com/api-keys) | Agent 01 (Whisper transcription) |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) | Agent 03 & 04 (script + hooks) |

---

## WAT Framework Rules
1. **Check `tools/` first** — reuse before building anything new
2. **Secrets in `.env` only** — never hardcode credentials
3. **Workflows are living docs** — update them when you discover better methods
4. **Deliverables go to cloud** — local `.tmp/` files are just processing intermediates
