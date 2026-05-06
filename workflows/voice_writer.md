# Workflow: Voice Writer (Agent 03)

## Objective
Generate a reel script for today's validated topic in the creator's exact tone, vocabulary, and Hinglish pattern — using Claude.

## Required Inputs
- `ANTHROPIC_API_KEY` in `.env`
- `ANTHROPIC_MODEL` in `.env` (default: claude-opus-4-5)
- `.tmp/validated_content_latest.json` (output from Agent 02)
- `config/voice_profile.json` — creator's voice profile (MUST be filled in)

## Tool
```
# Auto topic (from validator):
python tools/voice_writer.py

# Custom topic:
python tools/voice_writer.py "Claude Code for absolute beginners"
```

## Steps
1. Load voice profile from `config/voice_profile.json`
2. Load validated topic recommendation from `.tmp/validated_content_latest.json`
3. Use topic from CLI arg if provided; otherwise auto-select top ranked topic
4. Build a detailed prompt embedding:
   - Creator's vocabulary (words used/avoided)
   - Hinglish pattern and energy level
   - Script structure: BEAT 1 → BEAT 2 → BEAT 3 → CTA
   - Past scripts for tone learning
   - Avg view data for the topic
5. Send to Claude API (`claude-opus-4-5` by default)
6. Parse JSON response and save

## Expected Output Format
```
[BEAT 1] Setup — what the viewer is missing or getting wrong
[BEAT 2] Revelation — the insight or tool
[BEAT 3] Proof — quick result or example
[CTA]    Comment trigger
```

## Voice Profile Setup (DO THIS FIRST)
Edit `config/voice_profile.json`:
- Add 20–30 past scripts in `past_scripts[]`
- Fill in `vocabulary.words_i_use_often`
- Set your `hinglish_pattern` description
- Add real CTA examples

The more detail you provide, the more accurate the voice match.

## Edge Cases
| Problem | Fix |
|---------|-----|
| Script sounds too formal | Add more past scripts to `voice_profile.json` |
| Wrong topic generated | Pass topic as CLI arg |
| Claude API error | Check `ANTHROPIC_API_KEY` and model name in `.env` |
| JSON parse error | Script saves raw output as fallback |

## Notes
- This agent does NOT write hooks — that is handled by Agent 04
- Target: 30–40 seconds spoken at the creator's pace
- Never start a beat with "So", "Now", or "Today"
