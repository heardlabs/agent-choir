# agent-choir

**Your coding agents sing what they just did.**

When a Claude Code or Codex agent finishes a turn, agent-choir boils its reply down to one plain line ("I fixed the login test, all two hundred pass") and *sings* it, a cappella, through the music model of your choice. Every terminal gets its own singer and its own place in the stereo field. Run five agents and you get a choir.

- **Drop-in.** One hook. The agent never waits: the hook hands off and returns in about 0.1 s.
- **Bring your own key.** fal.ai (one key for Google Lyria, ElevenLabs Music, ACE-Step and MiniMax) or ElevenLabs direct. No account with us; nothing leaves your machine except the line being sung (and the reply, if you turn on the Claude summarizer).
- **Seven singers, the 16-bit crew.** Merge (lead tenor), Rebase (bass), Deploy (soprano), Lint (baritone), Docs (alto), Patch (second tenor), Grep (falsetto). Each is an original pixel-art dwarf. A terminal keeps its singer until it has been quiet for 6 hours.
- **A spending cap.** $3 a day by default. Repeat lines are cached and free.
- **A reel.** `choir reel` turns the last hour of singing into a square (X) or 9:16 (TikTok, RedNote, Reels) video: a grid of terminals, each with a 16-bit dwarf whose mouth moves with its own voice. Ready to post, no extra API calls.

MIT licensed. macOS and Linux.

## Install

```bash
pipx install git+https://github.com/heardlabs/agent-choir      # or: uv tool install git+...
mkdir -p ~/.config/agent-choir
echo 'FAL_KEY=your-fal-key' >> ~/.config/agent-choir/env       # https://fal.ai/dashboard/keys
choir install claude      # adds an async Stop hook to ~/.claude/settings.json (backs it up first)
choir install codex       # adds notify to ~/.codex/config.toml
choir doctor
```

Keys can also come from your shell environment. The `env` file exists because Codex and some terminals do not pass your environment to hook programs.

Try it without an agent:

```bash
choir say "I merged the docs branch and every link is green" --raw
choir demo        # four pretend terminals sing in turn (4 clips), then writes choir-demo.mp4
```

## Pick a singer model

```bash
choir providers
```

| Provider | Key | Measured (one 11-word line) | Cost per clip |
|---|---|---|---|
| `fal:lyria3` (default) | `FAL_KEY` | 16–26 s to render, words clear, adds doo-wop backing | $0.04 |
| `fal:lyria3-pro` | `FAL_KEY` | fuller sound | $0.08 |
| `fal:elevenlabs` | `FAL_KEY` | 8 s to render, exact length, clearest | $0.80 (fal bills per minute, rounded up) |
| `elevenlabs` | `ELEVENLABS_API_KEY` | same model, direct | your ElevenLabs plan credits |
| `fal:ace-step` | `FAL_KEY` | 16 s, words slur, each singer keeps a fixed seed | ~$0.002 |
| `fal:minimax-2.6` | `FAL_KEY` | 2.5 min to render, long "oh-oh" intros | $0.15 |
| `fal:minimax-2.0` | `FAL_KEY` | 4.5 min to render | $0.03 |

Suno is not listed: it has no public API yet (an invite-only partner program opened in July 2026), and the unofficial wrappers drive someone's Suno account against its terms. It will be added when real keys exist.

Measured 2026-11-06 on fal; "words clear" means Whisper transcribed the line back. MiniMax writes full songs, so the line is buried and it is too slow to follow an agent turn by turn. It is listed for completeness. Music models re-imagine the voice every time, so a singer sounds *similar* clip to clip, not identical.

Set it in `~/.config/agent-choir/config.toml` (`choir init` writes an example):

```toml
provider = "fal:elevenlabs"
summarizer = "auto"          # auto | anthropic | claude-cli | plain
max_seconds = 12             # longer takes are trimmed with a fade
daily_budget_usd = 3.0
overlap = false              # true: terminals sing over each other
style = "a cappella, doo-wop, no instruments, upbeat, short jingle"

[voices]                     # pin a singer to a project folder
billing-api = "Rebase"
```

## What gets sung

- `summarizer = "anthropic"` (or `auto` with `ANTHROPIC_API_KEY` set): Claude rewrites the reply as one first-person line of 6 to 14 words, with no code, paths, URLs or names.
- `claude-cli`: the same, through your local `claude` login (slower).
- `plain`: no LLM. The first short sentence of the reply, or the first sentence cut at a clause break.

Replies shorter than 4 words ("Done.") are skipped. `choir mute` / `choir unmute` (or `CHOIR_MUTE=1`) silences everything.

## The reel (for posting)

```bash
choir reel --since 60 -o reel.mp4                 # agents take turns
choir reel --since 60 --stagger 2.5 -o round.mp4  # they come in one after another and overlap, like a round
choir reel --since 60 --vertical -o tall.mp4      # 1080x1920 for TikTok, RedNote, Reels, Shorts
choir demo --singers 7 --stagger 4 --vertical      # no agents yet? seven fake terminals, the whole crew
```

1080x1080 (or 1080x1920 with `--vertical`) H.264 + AAC at 15 fps. The vertical cut leaves the bottom strip clear for the platform's caption UI. The sprites have a closed, half-open and open mouth (`choir/assets/sprites/`), picked frame by frame from the loudness of each singer's clip, so rendering is local and free. Clips live in `~/.local/state/agent-choir/clips/`, and every sung line is logged with its cost in `ledger.jsonl` next to them.

## How it works

```
Stop hook / Codex notify ──> choir hook (returns at once)
   └─ background: reply ─> one line ─> singer for this terminal ─> music model
                 ─> trim silence, cap length, level, pan to the singer's seat ─> play (taking turns)
```

The terminal is identified from `TMUX_PANE`, `HERDR_PANE_ID`, `WEZTERM_PANE`, `KITTY_WINDOW_ID`, `ITERM_SESSION_ID`, `TERM_SESSION_ID`, `WT_SESSION` or `ZELLIJ_PANE_ID`, falling back to the agent's session id.

Adding a model means writing one `Provider` in `choir/providers/__init__.py`: a request builder and a cost function.

## Not affiliated

The idea is a work crew singing on the job. The lines are original. The tool strips a short list of phrases from a certain 1937 film's song, so nobody's agents accidentally sing it.

## Dev

```bash
uv venv && uv pip install -e '.[dev]' && pytest -q
```

The tests use a fake singer and never call a paid API.
