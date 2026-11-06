"""Singing back-ends. Each turns a Song into a request for one music model.

All of them run through fal.ai today (one key, one queue API, per-call
billing), which covers MiniMax, Google Lyria, ElevenLabs Music and ACE-Step.
Add a provider by writing a ``Provider`` and listing it in ``PROVIDERS``.

Prices are from fal's model pages on 2026-11-06; re-check before big runs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from choir.song import NEGATIVE, Song

SECONDS_PER_LINE = 2.8  # a sung 4-10 word line at ~116 BPM, with breaths


def est_seconds(song: Song) -> float:
    return max(30.0, song.line_count() * SECONDS_PER_LINE)


@dataclass(frozen=True)
class Provider:
    key: str
    model: str  # fal endpoint id
    blurb: str
    build: Callable[[Song], dict]
    cost: Callable[[Song], float]  # USD estimate for one take
    # Section start/end seconds when the request pins them (used for captions)
    timings: Callable[[Song], list[float] | None] = lambda song: None


# --- MiniMax Music: lyrics with [Verse]/[Chorus] tags + a style prompt -----

def _minimax(song: Song) -> dict:
    return {
        "prompt": song.style[:2000],
        "lyrics": song.lyrics_text(tags=True)[:3500],
        "is_instrumental": False,
    }


# --- Lyria 3: lyrics go inside the prompt ----------------------------------

def _lyria(song: Song) -> dict:
    voices = "; ".join(
        f"{s.label}: {song.voices_for(s)}" for s in song.sections if s.kind == "verse"
    )
    prompt = (
        f"{song.style}. Strictly voices only, no instruments. "
        f"Each verse is a different solo voice: {voices}. "
        f"Sing these exact lyrics:\n\n{song.lyrics_text(tags=True)}"
    )
    return {"prompt": prompt[:5000]}


# --- ElevenLabs Music: a composition plan, one section per song section -----

def _section_ms(song: Song) -> list[int]:
    return [int(min(120_000, max(3_000, len(s.lines) * SECONDS_PER_LINE * 1000))) for s in song.sections]


def _eleven(song: Song) -> dict:
    sections = []
    for s, ms in zip(song.sections, _section_ms(song)):
        sections.append({
            "section_name": f"{s.label} ({', '.join(s.singers) or 'All'})"[:100],
            "positive_local_styles": [song.voices_for(s), "a cappella"],
            "negative_local_styles": NEGATIVE,
            "duration_ms": ms,
            "lines": [l[:200] for l in s.lines],
        })
    return {
        "composition_plan": {
            "positive_global_styles": [p.strip() for p in song.style.split(",")],
            "negative_global_styles": NEGATIVE,
            "sections": sections,
        },
        "respect_sections_durations": True,
        "output_format": "mp3_44100_192",
    }


def _eleven_cost(song: Song) -> float:
    return 0.80 * math.ceil(sum(_section_ms(song)) / 60_000)


def _eleven_timings(song: Song) -> list[float]:
    t, out = 0.0, [0.0]
    for ms in _section_ms(song):
        t += ms / 1000
        out.append(t)
    return out


# --- ACE-Step (open model): comma tags + lowercase [verse] tags ------------

def _ace(song: Song) -> dict:
    return {
        "tags": "a cappella, vocal harmony, barbershop, doo-wop, beatbox, choir, male and female vocals, upbeat, 116 bpm, no instruments",
        "lyrics": song.lyrics_text(tags=True, lower_tags=True),
        "duration": round(min(240.0, est_seconds(song) + 8)),
    }


PROVIDERS: dict[str, Provider] = {p.key: p for p in [
    Provider("minimax-2.6", "fal-ai/minimax-music/v2.6",
             "MiniMax Music 2.6: lyrics-led, strong vocals, your exact lyrics with section tags",
             _minimax, lambda s: 0.15),
    Provider("minimax-2.0", "fal-ai/minimax-music/v2",
             "MiniMax Music 2.0: legacy, cheapest MiniMax, worth one take for comparison",
             _minimax, lambda s: 0.03),
    Provider("lyria3-pro", "fal-ai/lyria3/pro",
             "Google Lyria 3 Pro: full songs up to ~3 min, lyrics via prompt, SynthID watermark",
             _lyria, lambda s: 0.08),
    Provider("lyria3", "fal-ai/lyria3",
             "Google Lyria 3: cheaper/shorter Lyria",
             _lyria, lambda s: 0.04),
    Provider("elevenlabs", "fal-ai/elevenlabs/music",
             "ElevenLabs Music: per-section voice direction and exact timing (best for captions), priciest",
             _eleven, _eleven_cost, _eleven_timings),
    Provider("ace-step", "fal-ai/ace-step",
             "ACE-Step: open model, pennies per take, rougher vocals",
             _ace, lambda s: 0.0002 * (est_seconds(s) + 8)),
]}

DEFAULT = ["minimax-2.6", "lyria3-pro", "elevenlabs", "ace-step"]


def get(keys: list[str]) -> list[Provider]:
    unknown = [k for k in keys if k not in PROVIDERS]
    if unknown:
        raise KeyError(f"unknown provider(s) {unknown}; known: {sorted(PROVIDERS)}")
    return [PROVIDERS[k] for k in keys]
