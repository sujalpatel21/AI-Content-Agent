# Workflow: Hook Generator (Agent 04)

## Objective
Generate 5 hook variations for today's reel topic using proven content patterns. Each hook is max 2 lines, speakable in under 4 seconds, in Hinglish. Includes confidence scoring and a recommended hook.

## Required Inputs
- `ANTHROPIC_API_KEY` in `.env`
- `ANTHROPIC_MODEL` in `.env`
- `.tmp/script_latest.json` (output from Agent 03)
- `config/voice_profile.json` (for tone reference)

## Tool
```
# Auto (uses script_latest.json topic):
python tools/hook_generator.py

# Custom topic:
python tools/hook_generator.py "How I automated my content with Claude"
```

## Steps
1. Load script context from `.tmp/script_latest.json` (Beat 1 + Beat 2 + topic)
2. Load voice profile from `config/voice_profile.json`
3. Build prompt with all 5 hook patterns and creator context
4. Send to Claude API
5. Parse 5 hooks, each with:
   - Hook text (max 2 lines)
   - Pattern used
   - Matched past reel style
   - Confidence score (1–10)
   - Confidence reason
6. Output recommended hook with reason
7. Save to `.tmp/hooks_latest.json`

## The 5 Hook Patterns

| # | Pattern | Formula |
|---|---------|---------|
| 1 | Aspirational | "Aisi honi chahiye X" — show the better version |
| 2 | Pain Point | Name a frustration the viewer feels RIGHT NOW |
| 3 | Insider | "Log nahi jaante" — exclusivity/insider feel |
| 4 | Time or Money Claim | Specific number + specific result |
| 5 | Curiosity Gap | Ask something they can't answer without watching |

## Hook Rules (enforced in prompt)
- MAX 2 lines
- Speakable in under 4 seconds
- Must be Hinglish — natural, not forced
- NEVER start with "Aaj main" or "Is video mein"
- Each hook = different pattern (no repeats)

## Expected Output
```
Hook 1 [Aspirational]   — hook text — 8/10
Hook 2 [Pain Point]     — hook text — 7/10
Hook 3 [Insider]        — hook text — 9/10  ⭐ RECOMMENDED
Hook 4 [Claim]          — hook text — 8/10
Hook 5 [Curiosity Gap]  — hook text — 7/10
```

## Edge Cases
| Problem | Fix |
|---------|-----|
| Hooks sound generic | Add more past scripts to `voice_profile.json` |
| JSON parse error | Raw output saved as fallback |
| Claude API error | Check `ANTHROPIC_API_KEY` in `.env` |

## Notes
- Recommended hook is based on confidence score + niche trend data from the validator
- Always test 2–3 hooks across different reels to find your top performer
