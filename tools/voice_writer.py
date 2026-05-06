#!/usr/bin/env python3
"""
Agent 03 — Voice Writer
Reads the validated topic recommendation + the creator's voice profile,
then generates a reel script in the creator's exact tone using Gemini.
Output saved to .tmp/script_latest.json
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OPENAI_KEY   = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

VALIDATOR_FILE    = Path(".tmp/validated_content_latest.json")
VOICE_PROFILE     = Path("config/voice_profile.json")
OUTPUT_DIR        = Path(".tmp")


# ── Load context ──────────────────────────────────────────────
def load_voice_profile() -> dict:
    if not VOICE_PROFILE.exists():
        print("⚠️  config/voice_profile.json not found — using defaults.")
        return {}
    with open(VOICE_PROFILE) as f:
        return json.load(f)


def load_validated_topic(validator_path: str | None = None) -> dict:
    src = Path(validator_path) if validator_path else VALIDATOR_FILE
    if not src.exists():
        return {}
    with open(src) as f:
        return json.load(f)


# ── Prompt builder ────────────────────────────────────────────
def build_prompt(topic: str, voice: dict, validated: dict) -> str:
    avg_views    = ""
    recommendation = validated.get("recommendation", "")
    top_topics   = validated.get("top_topics", [])
    if top_topics:
        match = next((t for t in top_topics if topic.lower() in t.get("topic_cluster","").lower()), top_topics[0])
        avg_views = f"{match.get('avg_views', 0):,}"

    vocab_good   = ", ".join(voice.get("vocabulary", {}).get("words_i_use_often", []))
    vocab_bad    = ", ".join(voice.get("vocabulary", {}).get("words_i_never_use", []))
    hinglish     = voice.get("hinglish_pattern", "Mix Hindi and English naturally")
    structure    = voice.get("script_structure", {})
    cta_examples = "\n".join(f"  - {c}" for c in voice.get("cta_examples", []))
    past_scripts = "\n\n---\n\n".join(voice.get("past_scripts", []))
    energy       = voice.get("sentence_style", {}).get("energy", "excited but authoritative")
    sentence_len = voice.get("sentence_style", {}).get("length", "short and punchy")

    prompt = f"""You are a professional social media script writer. Your job is to write a reel script for this creator in their EXACT voice — not yours.

## CREATOR VOICE PROFILE

**Language style:** {voice.get('language_style', 'Hinglish')}
**Energy:** {energy}
**Sentence length:** {sentence_len}
**Hinglish pattern:** {hinglish}

**Words I use often:** {vocab_good}
**Words I NEVER use:** {vocab_bad}

**Script structure:**
- BEAT 1: {structure.get('beat_1', 'Setup — what the viewer is missing')}
- BEAT 2: {structure.get('beat_2', 'Revelation — the insight or tool')}
- BEAT 3: {structure.get('beat_3', 'Proof — quick result or example')}
- CTA: {structure.get('cta', 'Comment trigger')}

**CTA examples (use these as inspiration, not verbatim):**
{cta_examples}

## PAST SCRIPTS (learn my voice from these)

{past_scripts if past_scripts.strip() and past_scripts != "PASTE YOUR SCRIPT 1 HERE" else "No past scripts provided — write in a punchy Hinglish style."}

## TODAY'S ASSIGNMENT

**Topic:** {topic}
**Data:** This topic averages {avg_views} views. It has been validated as the top recommended topic.

## RULES

1. Write ONLY the script body — NO hook (that's handled separately)
2. Follow exactly: [BEAT 1] → [BEAT 2] → [BEAT 3] → [CTA]
3. Each beat = 2-3 sentences MAX. Keep it tight.
4. CTA must be a comment trigger (e.g. "word comment karo, main bhej dunga")
5. Do NOT start any beat with "So", "Now", or "Today"
6. Do NOT use formal English. Write how the creator speaks — casual, real.
7. Total script should be speakable in 30-40 seconds at a fast pace.

## OUTPUT FORMAT

Return ONLY this JSON (no markdown, no explanation):
{{
  "topic": "{topic}",
  "beat_1": "...",
  "beat_2": "...",
  "beat_3": "...",
  "cta": "...",
  "full_script": "BEAT 1:\\n...\\n\\nBEAT 2:\\n...\\n\\nBEAT 3:\\n...\\n\\nCTA:\\n...",
  "estimated_seconds": 35
}}"""
    return prompt


# ── Main ──────────────────────────────────────────────────────
def run(topic: str | None = None, validator_path: str | None = None) -> str | None:
    if not OPENAI_KEY:
        print("❌  OPENAI_API_KEY not set in .env")
        return None

    validated = load_validated_topic(validator_path)
    voice     = load_voice_profile()

    if not topic:
        top_topics = validated.get("top_topics", [])
        if top_topics:
            topic = top_topics[0].get("topic_cluster", "AI Automation with Claude Code")
        else:
            topic = "AI Automation with Claude Code"
        print(f"📌  Auto-selected topic: {topic}")
    else:
        print(f"📌  Topic: {topic}")

    print(f"\n🚀  Agent 03 — Voice Writer\n" + "─"*50)
    print(f"🤖  Model: {OPENAI_MODEL}")
    print(f"✍️   Writing script...")

    client = OpenAI(api_key=OPENAI_KEY)
    prompt = build_prompt(topic, voice, validated)

    # ── Retry loop for rate limits ────────────────────────────
    max_retries = 3
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

    # Parse JSON from response
    try:
        # Strip markdown code fences if present
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip()
        script_data = json.loads(raw)
    except json.JSONDecodeError:
        script_data = {"topic": topic, "full_script": raw, "raw": True}

    # Save
    ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
    latest = OUTPUT_DIR / "script_latest.json"
    with open(latest, "w") as f:
        json.dump(script_data, f, indent=2, ensure_ascii=False)
    with open(OUTPUT_DIR / f"script_{ts}.json", "w") as f:
        json.dump(script_data, f, indent=2, ensure_ascii=False)

    # Print
    print(f"\n{'='*70}")
    print(f"📝  SCRIPT — {topic}")
    print(f"{'='*70}\n")
    if "full_script" in script_data:
        print(script_data["full_script"])
    else:
        print(raw)
    print(f"\n⏱️   Est. duration: {script_data.get('estimated_seconds', '?')}s")
    print(f"💾  Saved → {latest}\n")

    return str(latest)


if __name__ == "__main__":
    import sys
    topic_arg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    run(topic=topic_arg)
