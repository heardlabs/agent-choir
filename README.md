# agent-choir

Your coding agents, as an a cappella group, singing about the work they just did.

A Twitter/X campaign toy, separate from the Heard product. It reads what your
agents actually did (Claude Code transcripts, git commits, or a hand-written
file), has Claude write an original song where each agent gets a verse, sends
it to a singing music model, and renders a square video with lyric cards and
a row of seven voices that light up as each one sings.

```
collect ──> write ──> sing (one or many models) ──> video ──> post
work.json   song.json  takes/<slug>/*.mp3 + index.html   *.mp4
```

## The ensemble

Seven original singers, named after git verbs. Each agent is assigned one, busiest first.

| Singer | Part |
|---|---|
| Merge | lead tenor |
| Rebase | bass |
| Deploy | soprano |
| Lint | baritone |
| Docs | alto |
| Patch | second tenor |
| Grep | vocal percussion (beatbox only, never gets a verse) |

**Keep it original.** The inspiration was the seven-dwarves work song, which is
still under copyright. The idea is free to use; the song, its title, its
lyrics, its tune and the characters are not. `song.problems()` rejects any take
containing the reference phrases (see `BANNED` in `choir/song.py`), and the
lyricist prompt forbids quoting or parodying any existing song.

## Setup

```bash
uv venv && uv pip install -e '.[dev]'     # or: python -m venv .venv && pip install -e '.[dev]'
export FAL_KEY=...                         # https://fal.ai/dashboard/keys (singing)
export ANTHROPIC_API_KEY=...               # optional: lyrics; falls back to the `claude` CLI
```

The ffmpeg binary comes from `imageio-ffmpeg`, so no system install is needed.

## Use

```bash
choir collect --claude --since 24h -o work.json     # or --git ~/code/a ~/code/b, or --json examples/work.json
$EDITOR work.json                                   # READ IT: this text goes into a public song
choir write work.json -o song.json                  # Claude writes it; --no-llm for an offline template
choir sing song.json                                # prints the cost estimate, spends nothing
choir sing song.json --yes                          # renders on every provider in parallel
open takes/<slug>/index.html                        # listen side by side
choir video song.json takes/<slug>/minimax-2.6.mp3 -o tweet.mp4
```

Or all at once with one model: `choir run --json examples/work.json --providers minimax-2.6 --yes`.

`work.py` scrubs emails, URLs, long tokens and home paths, but transcripts can still hold
things you would not tweet (the agent's own summaries, customer names in prompts). Read
`work.json` and `song.json` before `sing`.

## Singing models

All of these run through fal.ai: one key, one queue API, pay per take. Prices are fal list prices on 2026-11-06.

| Key | fal endpoint | ~Cost per take | What it is |
|---|---|---|---|
| `minimax-2.6` | `fal-ai/minimax-music/v2.6` | $0.15 | Lyrics-led: sings your exact lyrics with `[Verse]`/`[Chorus]` tags. Default pick. |
| `minimax-2.0` | `fal-ai/minimax-music/v2` | $0.03 | Legacy MiniMax, cheap comparison take. |
| `lyria3-pro` | `fal-ai/lyria3/pro` | $0.08 | Google Lyria 3 Pro, songs up to ~3 min, lyrics go in the prompt. SynthID watermark. |
| `lyria3` | `fal-ai/lyria3` | $0.04 | Shorter, cheaper Lyria. |
| `elevenlabs` | `fal-ai/elevenlabs/music` | $0.80/min | Composition plan: per-section voice direction and exact section timing, so captions line up. Priciest. |
| `ace-step` | `fal-ai/ace-step` | ~$0.02 | Open model, pennies, rougher vocals. Good for fast iteration. |

`choir providers` lists them. A full bake-off on the defaults is about $1.85.

What we did not wire in, and why:
- **Suno / Udio**: the best vocals, but no official API. The resellers are against their terms, which is a bad look for a public campaign.
- **MiniMax direct** (platform.minimax.io): reports in Aug 2026 said its paid music API was closed to new sign-ups and pointed people to fal or MiniMax Audio. fal covers the same models.
- **Mureka** (lyrics-first, V9): next candidate if MiniMax's vocals disappoint. It has its own API; add a `Provider` for it.
- **Lyria 2, Stable Audio, CassetteAI**: instrumental only.

Nobody guarantees "a cappella". Every request says no instruments three ways (style text, negative styles where supported, ACE tags). Expect some takes to sneak in a bass line; that is what the bake-off is for.

## Posting

X takes MP4 (H.264 + AAC) up to 2:20; `video.py` renders 1080x1080 and caps at 140 s.
Caption timing is exact for `elevenlabs` (the request pins section lengths) and
estimated from line counts for the rest. Posting is manual on purpose.

## Dev

```bash
pytest -q
```

Tests cover payload shapes for every provider, transcript parsing, scrubbing, the banned-phrase check and a real (sine-wave) video render. They never call fal or Claude.
