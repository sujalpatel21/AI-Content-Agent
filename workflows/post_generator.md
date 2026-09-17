# Workflow: Post Generator (Agent 05)

## Objective
Turn a single piece of content a human hands over — a link, an image, a video, or raw text — into a platform-formatted draft post, in the creator's voice. This is the piece that lets Benji (the WhatsApp/Telegram assistant, running separately on its own VPS) say "send me a link and a platform, get a draft back."

This agent never publishes. It returns a draft for the caller to relay for human approval.

## Required Inputs
- `OPENAI_API_KEY` in `.env` — used for text generation, image understanding (vision), and video transcription (Whisper)
- `config/voice_profile.json` filled in with the creator's actual voice — **as of this writing it is still the unfilled template**. Drafts generated before this is filled in will come back generic and will carry a `warnings` field saying so.
- Optional: `WEBHOOK_SECRET` in `.env` — if set, the `/api/generate-post` route requires it in an `X-Webhook-Secret` header. Set this before exposing the Flask app to anything outside localhost — the route has no other auth and calls a paid API per request.

## Tool
CLI:
```
python tools/post_generator.py <link|image|video|text> <source> <platform> [instruction]
```

Webhook (for Benji or n8n to call):
```
POST /api/generate-post
Headers: X-Webhook-Secret: <WEBHOOK_SECRET, if set>
Body: {
  "source_type": "link" | "image" | "video" | "text",
  "source": "<url, or raw text for source_type=text>",
  "platform": "linkedin" | "instagram" | "x" | "facebook" | "threads",
  "instruction": "optional free-text steering"
}
```
Returns `{"platform": ..., "draft": "..."}` for most platforms, or `{"platform": "x", "tweets": [...]}` for X threads.

## Steps
1. Extract usable text from the source:
   - `link` — fetches the page and strips it down to visible text (stdlib HTML parsing, not a full readability library — good enough for most article pages, may pull in boilerplate on complex sites)
   - `image` — described by a vision model (`OPENAI_VISION_MODEL`, default `gpt-4o-mini`); the image must be reachable at a public URL, not a local file path
   - `video` — audio track transcribed via Whisper; the API accepts mp4/mov/webm directly and extracts the audio itself. **This only captures spoken audio** — a visual-only or silent video comes back empty.
   - `text` — passed through as-is
2. Build a platform-specific prompt using the voice profile and the platform's format rules (character limits, hashtag conventions, thread-splitting for X)
3. Call OpenAI (`OPENAI_MODEL`, default `gpt-3.5-turbo`) to write the draft
4. Return the draft as JSON; flag with a `warnings` field if the voice profile is still unfilled

## Integration with Benji
This repo does not own the WhatsApp/Telegram side — Benji does, on its own VPS. The intended flow:
1. You send Benji a link/image/video + an instruction in chat
2. Benji resolves the media to a URL it can hand off (it already does this for WhatsApp/Telegram media) and POSTs to `/api/generate-post`
3. Benji relays the returned draft back to you in the same chat
4. You approve or edit in chat
5. Only on approval does anything move to Postiz for scheduling — this agent does not schedule or publish anything itself

**Open item**: this Flask app needs to be deployed somewhere Benji's VPS can reach it, with `WEBHOOK_SECRET` set. That deployment decision (same VPS as Benji vs. separate host) is not something this repo can decide on its own.

## Edge Cases
| Problem | Fix |
|---------|-----|
| Image URL isn't publicly reachable | Vision model call fails — Benji must upload/host the media somewhere fetchable before calling this, not pass a WhatsApp-internal media ID directly |
| Video has no spoken audio | Transcript comes back empty, generation fails loudly rather than silently producing a caption based on nothing |
| Voice profile still template placeholders | Draft is generated anyway (better than blocking), but flagged in `warnings` — don't publish these without a human editing pass until the profile is filled in |
| Unsupported platform requested | Route returns 400 with the supported list, no OpenAI call made |
| No `WEBHOOK_SECRET` set | Route accepts unauthenticated requests — fine for local-only testing, not for anything internet-reachable |

## Notes
- Uses OpenAI for both text and vision — no Anthropic/Gemini dependency here despite older docs elsewhere referencing them.
- Does not yet handle multi-image posts (e.g. an Instagram carousel) — one image in, one caption out.
