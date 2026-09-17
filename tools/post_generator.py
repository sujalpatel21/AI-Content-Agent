#!/usr/bin/env python3
"""
Agent 05 — Post Generator
Takes a link, image, video, or raw text + a target platform, and writes a
platform-formatted post in the creator's voice. Designed to be called from
a webhook (see app.py's /api/generate-post route) so an external bot like
Benji can hand it a piece of content and get a draft back.

Does NOT publish anything. Returns a draft for the caller to relay for approval.
"""

import os
import re
import json
import time
import tempfile
import urllib.request
from pathlib import Path
from html.parser import HTMLParser

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OPENAI_KEY    = os.getenv("OPENAI_API_KEY", "")
TEXT_MODEL    = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
VISION_MODEL  = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")

VOICE_PROFILE = Path("config/voice_profile.json")
BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

PLATFORM_SPECS = {
    "linkedin":   "A LinkedIn post. Plain text with natural line breaks, no hashtag spam (max 3 hashtags at the end). 900-1300 characters. Hook line first — LinkedIn truncates after ~3 lines, so the first line must earn the click to 'see more'.",
    "instagram":  "An Instagram caption. Short punchy opening line, then the body, then a line-broken block of 5-8 relevant hashtags at the end. Under 2200 characters.",
    "x":          "An X (Twitter) thread. Return each tweet as a separate string, each under 280 characters. First tweet is the hook and must work standalone. 3-7 tweets.",
    "facebook":   "A Facebook post. Conversational, slightly longer than an X post, no hashtag spam. Under 500 characters unless the source material genuinely needs more room.",
    "threads":    "A Threads post. Casual, conversational, under 500 characters.",
}


# ── Extraction ────────────────────────────────────────────────
class _TextExtractor(HTMLParser):
    """Minimal dependency-free HTML-to-text extractor. Good enough for article
    bodies; not a substitute for a real readability/boilerplate-removal library
    if extraction quality on complex pages turns out to matter."""

    def __init__(self):
        super().__init__()
        self._skip_stack = []
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "header", "footer", "noscript"):
            self._skip_stack.append(tag)

    def handle_endtag(self, tag):
        if self._skip_stack and self._skip_stack[-1] == tag:
            self._skip_stack.pop()

    def handle_data(self, data):
        if not self._skip_stack:
            s = data.strip()
            if s:
                self.chunks.append(s)


def extract_from_link(url: str) -> str:
    req = urllib.request.Request(url, headers=BROWSER_HEADERS)
    with urllib.request.urlopen(req, timeout=20) as response:
        html = response.read().decode("utf-8", errors="ignore")
    parser = _TextExtractor()
    parser.feed(html)
    text = " ".join(parser.chunks)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:8000]  # cap — this is source material for a prompt, not the whole page


def extract_from_image(image_url: str) -> str:
    if not OPENAI_KEY:
        raise RuntimeError("OPENAI_API_KEY not set — required for image understanding")
    client = OpenAI(api_key=OPENAI_KEY)
    response = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image in detail: what's shown, the mood/style, any text visible in it, and anything notable a social media caption should reference."},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        }],
    )
    return response.choices[0].message.content.strip()


def extract_from_video(video_url: str) -> str:
    """Downloads the video and transcribes its audio track with Whisper.
    Whisper's API accepts mp4/mov/webm directly — it extracts the audio itself,
    no local ffmpeg step needed. This only captures spoken audio, not on-screen
    visuals; a silent or visual-only video will come back with an empty transcript."""
    if not OPENAI_KEY:
        raise RuntimeError("OPENAI_API_KEY not set — required for video transcription")
    req = urllib.request.Request(video_url, headers=BROWSER_HEADERS)
    with urllib.request.urlopen(req, timeout=60) as response:
        suffix = Path(video_url.split("?")[0]).suffix or ".mp4"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(response.read())
            tmp = f.name
    try:
        client = OpenAI(api_key=OPENAI_KEY)
        with open(tmp, "rb") as media:
            result = client.audio.transcriptions.create(model="whisper-1", file=media)
        return result.text
    finally:
        os.unlink(tmp)


def extract_content(source_type: str, source: str) -> str:
    if source_type == "link":
        return extract_from_link(source)
    if source_type == "image":
        return extract_from_image(source)
    if source_type == "video":
        return extract_from_video(source)
    if source_type == "text":
        return source
    raise ValueError(f"Unknown source_type: {source_type}")


# ── Prompt + generation ───────────────────────────────────────
def load_voice_profile() -> dict:
    if not VOICE_PROFILE.exists():
        return {}
    with open(VOICE_PROFILE) as f:
        return json.load(f)


def _voice_is_unfilled(voice: dict) -> bool:
    scripts = voice.get("past_scripts", [])
    return (not voice) or any("PASTE YOUR SCRIPT" in s for s in scripts) or voice.get("creator_name") == "Your Name"


def build_prompt(content: str, platform: str, voice: dict, instruction: str | None) -> str:
    spec = PLATFORM_SPECS.get(platform)
    if not spec:
        raise ValueError(f"Unsupported platform: {platform}. Supported: {list(PLATFORM_SPECS)}")

    vocab_good = ", ".join(voice.get("vocabulary", {}).get("words_i_use_often", []))
    vocab_bad  = ", ".join(voice.get("vocabulary", {}).get("words_i_never_use", []))
    energy     = voice.get("sentence_style", {}).get("energy", "excited but authoritative")
    past       = "\n\n---\n\n".join(s for s in voice.get("past_scripts", []) if "PASTE YOUR SCRIPT" not in s)
    past_block = f"Past posts to learn tone from:\n{past}" if past.strip() else "No past posts on file — write in a natural, direct, non-corporate tone."

    return f"""You are writing a social media post for a creator, in their exact voice — not yours.

## VOICE
Energy: {energy}
Words used often: {vocab_good or "(not specified)"}
Words never used: {vocab_bad or "(not specified)"}
{past_block}

## PLATFORM FORMAT
{spec}

## SOURCE MATERIAL
{content[:6000]}

## INSTRUCTION FROM THE CREATOR
{instruction or "None given — use your judgement on angle."}

## OUTPUT
Return ONLY valid JSON, no markdown fences.
- For "x": {{"platform": "x", "tweets": ["tweet 1", "tweet 2", ...]}}
- For everything else: {{"platform": "{platform}", "draft": "the full post text"}}"""


def generate_post(source_type: str, source: str, platform: str, instruction: str | None = None) -> dict:
    if not OPENAI_KEY:
        raise RuntimeError("OPENAI_API_KEY not set in .env")

    content = extract_content(source_type, source)
    if not content or not content.strip():
        raise RuntimeError(f"No usable content extracted from {source_type}: {source}")

    voice = load_voice_profile()
    prompt = build_prompt(content, platform, voice, instruction)

    client = OpenAI(api_key=OPENAI_KEY)
    max_retries = 3
    raw = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content.strip()
            break
        except Exception as e:
            err = str(e)
            if attempt < max_retries and ("429" in err or "rate limit" in err.lower()):
                time.sleep(10)
            else:
                raise

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"platform": platform, "draft": raw}

    result["source_type"] = source_type
    result["source"] = source
    if _voice_is_unfilled(voice):
        result["warnings"] = result.get("warnings", []) + [
            "config/voice_profile.json is still the unfilled template — this draft used a generic tone, not the creator's actual voice."
        ]
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python tools/post_generator.py <link|image|video|text> <source> <platform> [instruction]")
        sys.exit(1)
    stype, src, plat = sys.argv[1], sys.argv[2], sys.argv[3]
    instr = " ".join(sys.argv[4:]) if len(sys.argv) > 4 else None
    print(json.dumps(generate_post(stype, src, plat, instr), indent=2, ensure_ascii=False))
