#!/usr/bin/env python3
"""
Full Pipeline Orchestrator
Chains all 4 agents: Scraper → Validator → Voice Writer → Hook Generator
Usage:
  python tools/run_pipeline.py                          # auto topic from validator
  python tools/run_pipeline.py "Claude Code for beginners"  # custom topic
  python tools/run_pipeline.py --skip-scrape "topic"    # skip scraping (reuse latest data)
"""

import sys
import time
from datetime import datetime
from pathlib import Path

# ── Optional topic from CLI ───────────────────────────────────
args   = [a for a in sys.argv[1:] if not a.startswith("--")]
flags  = [a for a in sys.argv[1:] if a.startswith("--")]
TOPIC  = " ".join(args) if args else None
SKIP_SCRAPE = "--skip-scrape" in flags


def separator(label: str):
    print(f"\n{'█'*70}")
    print(f"  {label}")
    print(f"{'█'*70}\n")


def elapsed(start: float) -> str:
    secs = int(time.time() - start)
    return f"{secs // 60}m {secs % 60}s"


def run():
    print(f"\n{'='*70}")
    print(f"  🤖  AI CONTENT PIPELINE — Full Run")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")
    if TOPIC:
        print(f"  📌  Topic override: {TOPIC}")
    if SKIP_SCRAPE:
        print(f"  ⚡  Skipping scrape — reusing latest data")
    print()

    total_start = time.time()
    scraper_out   = None
    validator_out = None
    script_out    = None
    hooks_out     = None

    # ── Agent 01: Content Scraper ─────────────────────────────
    if not SKIP_SCRAPE:
        separator("AGENT 01 — Content Scraper")
        t = time.time()
        from tools.content_scraper import run as scrape
        scraper_out = scrape()
        print(f"⏱️  Agent 01 done in {elapsed(t)}")
    else:
        latest = Path(".tmp/scraped_content_latest.json")
        if latest.exists():
            scraper_out = str(latest)
            print(f"⚡  Using cached scraper data: {latest}")
        else:
            print("❌  No cached scrape data found. Remove --skip-scrape flag.")
            sys.exit(1)

    # ── Agent 02: Content Validator ───────────────────────────
    separator("AGENT 02 — Content Validator")
    t = time.time()
    from tools.content_validator import run as validate
    validator_out = validate(input_path=scraper_out)
    print(f"⏱️  Agent 02 done in {elapsed(t)}")

    if not validator_out:
        print("❌  Validation failed. Check .tmp/scraped_content_latest.json")
        sys.exit(1)

    # ── Agent 03: Voice Writer ────────────────────────────────
    separator("AGENT 03 — Voice Writer")
    t = time.time()
    from tools.voice_writer import run as write_script
    script_out = write_script(topic=TOPIC, validator_path=validator_out)
    print(f"⏱️  Agent 03 done in {elapsed(t)}")

    if not script_out:
        print("❌  Script writing failed. Check OPENAI_API_KEY in .env")
        sys.exit(1)

    # ── Agent 04: Hook Generator ──────────────────────────────
    separator("AGENT 04 — Hook Generator")
    t = time.time()
    from tools.hook_generator import run as gen_hooks
    hooks_out = gen_hooks(topic=TOPIC, script_path=script_out)
    print(f"⏱️  Agent 04 done in {elapsed(t)}")

    # ── Final Summary ─────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  ✅  PIPELINE COMPLETE — {elapsed(total_start)} total")
    print(f"{'='*70}")
    print(f"  📁  Scrape data  → .tmp/scraped_content_latest.json")
    print(f"  📁  Validation   → .tmp/validated_content_latest.json")
    print(f"  📁  Script       → .tmp/script_latest.json")
    print(f"  📁  Hooks        → .tmp/hooks_latest.json")
    print()
    print("  Your reel is ready. Pick a hook, attach the script, and film.")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    run()
