#!/usr/bin/env python3
"""
Agent 04 — Hook Generator
Generates 5 hook variations for a reel topic using proven patterns.
Each hook: max 2 lines, speakable in under 4 seconds, in Hinglish.
Output saved to .tmp/hooks_latest.json
"""

import os
import json
import re
import time
from pathlib import Path
from datetime import datetime

from openai import OpenAI
from dotenv import load_dotenv
from tabulate import tabulate

load_dotenv()

OPENAI_KEY   = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

SCRIPT_FILE  = Path(".tmp/script_latest.json")
OUTPUT_DIR   = Path(".tmp")

# The 5 proven hook patterns
HOOK_PATTERNS = {
    1: {
        "name": "Aspirational",
        "formula": '"Aisi honi chahiye X" — show the better version they want',
        "example": "Teri Instagram reach aise honi chahiye — har reel 1 lakh views.",
    },
    2: {
        "name": "Pain Point",
        "formula": "Name a frustration the viewer feels RIGHT NOW",
        "example": "Ghante ka content banate ho, 200 views aate hain. Iska solution hai.",
    },
    3: {
        "name": "Insider / Exclusivity",
        "formula": '"Log nahi jaante" — insider knowledge feel',
        "example": "90% creators yeh tool use nahi karte — isliye stuck hain.",
    },
    4: {
        "name": "Time or Money Claim",
        "formula": "Specific number + specific result. No vague promises.",
        "example": "Yeh ek tool se main 3 ghante ka kaam 8 minutes mein karta hoon.",
    },
    5: {
        "name": "Curiosity Gap",
        "formula": "Ask something they cannot answer without watching",
        "example": "Claude Code aur ChatGPT mein kya fark hai? Sab galat soch rahe hain.",
    },
}


def build_prompt(topic: str, script_beats: dict, voice_profile: dict) -> str:
    pattern_block = "\n".join([
        f"Hook {k}: [{v['name']}] — {v['formula']}\nExample: {v['example']}"
        for k, v in HOOK_PATTERNS.items()
    ])

    past_scripts = "\n".join(voice_profile.get("past_scripts", []))
    hinglish     = voice_profile.get("hinglish_pattern", "Mix Hindi and English naturally")
    top_reels    = voice_profile.get("notes", "")

    beat1 = script_beats.get("beat_1", "")
    beat2 = script_beats.get("beat_2", "")

    return f"""You are an expert short-form video hook writer specialising in Hinglish content for Indian creators.

## CONTEXT

**Topic:** {topic}
**Script Beat 1 (setup):** {beat1}
**Script Beat 2 (revelation):** {beat2}
**Hinglish style:** {hinglish}

## CREATOR'S PAST SCRIPTS (for tone reference)
{past_scripts if past_scripts.strip() and past_scripts != "PASTE YOUR SCRIPT 1 HERE" else "Not provided — use punchy, casual Hinglish."}

## THE 5 HOOK PATTERNS TO USE

{pattern_block}

## RULES FOR EVERY HOOK

1. MAXIMUM 2 lines — must be speakable in under 4 seconds
2. Must be in Hinglish — natural mix, not forced
3. NEVER start with "Aaj main" or "Is video mein"
4. Each hook must use a DIFFERENT pattern from the list above
5. Make it specific to the topic — not generic

## OUTPUT FORMAT

Return ONLY this JSON (no markdown, no explanation):
{{
  "topic": "{topic}",
  "hooks": [
    {{
      "number": 1,
      "pattern": "Aspirational",
      "hook_text": "...",
      "pattern_used": "Aisi honi chahiye X",
      "matched_reel": "description of which past reel style this matches",
      "confidence": 8,
      "confidence_reason": "why this score"
    }},
    {{
      "number": 2,
      "pattern": "Pain Point",
      "hook_text": "...",
      "pattern_used": "Name frustration",
      "matched_reel": "...",
      "confidence": 7,
      "confidence_reason": "..."
    }},
    {{
      "number": 3,
      "pattern": "Insider",
      "hook_text": "...",
      "pattern_used": "Log nahi jaante",
      "matched_reel": "...",
      "confidence": 9,
      "confidence_reason": "..."
    }},
    {{
      "number": 4,
      "pattern": "Time or Money Claim",
      "hook_text": "...",
      "pattern_used": "Specific number + result",
      "matched_reel": "...",
      "confidence": 8,
      "confidence_reason": "..."
    }},
    {{
      "number": 5,
      "pattern": "Curiosity Gap",
      "hook_text": "...",
      "pattern_used": "Curiosity question",
      "matched_reel": "...",
      "confidence": 7,
      "confidence_reason": "..."
    }}
  ],
  "recommended_hook": 3,
  "recommended_reason": "why this hook wins today"
}}"""


def run(topic: str | None = None, script_path: str | None = None) -> str | None:
    if not OPENAI_KEY:
        print("❌  OPENAI_API_KEY not set in .env")
        return None

    # Load script context
    src = Path(script_path) if script_path else SCRIPT_FILE
    script_data  = {}
    voice_profile = {}
    if src.exists():
        with open(src) as f:
            script_data = json.load(f)
        if not topic:
            topic = script_data.get("topic", "AI Automation with Claude Code")

    vp_path = Path("config/voice_profile.json")
    if vp_path.exists():
        with open(vp_path) as f:
            voice_profile = json.load(f)

    if not topic:
        topic = "AI Automation with Claude Code"

    print(f"\n🚀  Agent 04 — Hook Generator\n" + "─"*50)
    print(f"📌  Topic: {topic}")
    print(f"🤖  Model: {OPENAI_MODEL}")
    print(f"⚡  Generating 5 hooks...")

    client = OpenAI(api_key=OPENAI_KEY)
    prompt = build_prompt(topic, script_data, voice_profile)

    # ── Retry loop for rate limits ────────────────────────────
    max_retries = 3
    raw = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            raw = response.choices[0].message.content.strip()
            break
        except Exception as e:
            err = str(e)
            if attempt < max_retries and ('429' in err or 'quota' in err.lower() or 'Rate limit' in err):
                wait = 10
                print(f"\n⚠️  Rate limit hit. Waiting {wait}s before retry {attempt}/{max_retries-1}...")
                time.sleep(wait)
            else:
                print(f"\n❌  OpenAI API error: {e}")
                return None
    if raw is None:
        return None
    if "```" in raw:
        raw = raw.split("```")[1].lstrip("json").strip()

    try:
        hooks_data = json.loads(raw)
    except json.JSONDecodeError:
        hooks_data = {"topic": topic, "raw_output": raw}

    # Save
    ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
    latest = OUTPUT_DIR / "hooks_latest.json"
    with open(latest, "w") as f:
        json.dump(hooks_data, f, indent=2, ensure_ascii=False)
    with open(OUTPUT_DIR / f"hooks_{ts}.json", "w") as f:
        json.dump(hooks_data, f, indent=2, ensure_ascii=False)

    # Print
    print(f"\n{'='*70}")
    print(f"🪝  HOOKS — {topic}")
    print(f"{'='*70}\n")

    if "hooks" in hooks_data:
        rec_num = hooks_data.get("recommended_hook", 0)
        table_rows = []
        for h in hooks_data["hooks"]:
            star = "⭐ RECOMMENDED" if h["number"] == rec_num else ""
            table_rows.append([
                f"Hook {h['number']}",
                h["pattern"],
                h["hook_text"],
                f"{h['confidence']}/10",
                star,
            ])
        print(tabulate(table_rows,
                       headers=["#", "Pattern", "Hook", "Confidence", ""],
                       tablefmt="rounded_outline"))
        print(f"\n✅  Use Hook {rec_num}: {hooks_data.get('recommended_reason', '')}")
    else:
        print(raw)

    print(f"\n💾  Saved → {latest}\n")
    return str(latest)


if __name__ == "__main__":
    import sys
    topic_arg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    run(topic=topic_arg)
