"""Singing back-ends, bring your own key.

``fal:*`` runs through fal.ai (one FAL_KEY covers MiniMax, Google Lyria,
ElevenLabs Music and ACE-Step). ``elevenlabs`` calls ElevenLabs directly with
your ELEVENLABS_API_KEY (billed against your ElevenLabs plan credits).

Measured on 2026-11-06 with one 11-word line (render time / clip / words
recognisable by Whisper):

  fal:elevenlabs  8s  /  8s  / yes        $0.80 a clip (fal bills per minute, rounded up)
  fal:lyria3      16s / 25s  / yes, slow  $0.04
  fal:ace-step    16s / 10s  / slurred    ~$0.002
  fal:minimax-2.6 153s / 90s / buried in "oh-oh" runs   $0.15
  fal:minimax-2.0 277s / 183s / same      $0.03

Add a back-end by writing a ``Provider`` and listing it in ``PROVIDERS``.
"""

from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from choir.cast import Singer
from choir.providers import fal


def clip_seconds(line: str, cap: float) -> float:
    """How long to ask for: ~0.5 s a word plus a breath either side."""
    return max(4.0, min(cap, 0.5 * len(line.split()) + 2.5))


def style_for(singer: Singer, style: str) -> str:
    return f"{style}, solo {singer.voice}"


@dataclass(frozen=True)
class Provider:
    key: str
    needs: str  # env var holding the key
    blurb: str
    request: Callable[[str, Singer, str, float], dict]  # line, singer, style, seconds -> payload
    cost: Callable[[float], float]  # seconds -> USD
    model: str = ""  # fal endpoint id, for fal providers

    def available(self) -> bool:
        return bool(os.environ.get(self.needs))

    def sing(self, line: str, singer: Singer, style: str, seconds: float, dest: Path, log=lambda *_: None) -> Path:
        payload = self.request(line, singer, style, seconds)
        if self.key == "elevenlabs":
            return _elevenlabs_direct(payload, dest)
        result = fal.run(self.model, payload, log=log)
        audio = result.get("audio") or {}
        url = audio.get("url") if isinstance(audio, dict) else None
        if not url:
            raise RuntimeError(f"{self.key}: no audio in response {json.dumps(result)[:300]}")
        return fal.download(url, dest)


# --- request builders -----------------------------------------------------

def _minimax_26(line, singer, style, seconds):
    return {"prompt": style_for(singer, style), "lyrics": f"[Verse]\n{line}"}


def _minimax_20(line, singer, style, seconds):
    return {"prompt": style_for(singer, style), "lyrics_prompt": f"[verse]\n{line}"}


def _lyria(line, singer, style, seconds):
    return {"prompt": f"{style_for(singer, style)}. Sing exactly this one line once, then stop: \"{line}\""}


def _eleven(line, singer, style, seconds):
    return {"prompt": f"{style_for(singer, style)}. Lyrics, sung once: {line}",
            "music_length_ms": int(seconds * 1000)}


def _ace(line, singer, style, seconds):
    return {"tags": f"a cappella, {singer.tags}, doo-wop, no instruments",
            "lyrics": f"[verse]\n{line}", "duration": round(seconds), "seed": singer.seed}


def _elevenlabs_direct(payload: dict, dest: Path) -> Path:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/music?output_format=mp3_44100_128",
        data=json.dumps(payload).encode(), method="POST",
        headers={"xi-api-key": key, "Content-Type": "application/json", "User-Agent": fal.UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            dest.write_bytes(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"elevenlabs -> {e.code}: {e.read().decode(errors='replace')[:400]}") from None
    return dest


PROVIDERS: dict[str, Provider] = {p.key: p for p in [
    Provider("fal:lyria3", "FAL_KEY", "Google Lyria 3 via fal: clear words, ~16s to render, $0.04",
             _lyria, lambda s: 0.04, "fal-ai/lyria3"),
    Provider("fal:lyria3-pro", "FAL_KEY", "Google Lyria 3 Pro via fal: fuller sound, $0.08",
             _lyria, lambda s: 0.08, "fal-ai/lyria3/pro"),
    Provider("fal:elevenlabs", "FAL_KEY", "ElevenLabs Music via fal: best and fastest (~8s), exact length, $0.80 a clip",
             _eleven, lambda s: 0.80 * math.ceil(s / 60), "fal-ai/elevenlabs/music"),
    Provider("elevenlabs", "ELEVENLABS_API_KEY", "ElevenLabs Music direct, on your ElevenLabs plan credits",
             _eleven, lambda s: 0.0),
    Provider("fal:ace-step", "FAL_KEY", "ACE-Step (open model) via fal: pennies, keeps each singer's seed, words slur",
             _ace, lambda s: 0.0002 * s, "fal-ai/ace-step"),
    Provider("fal:minimax-2.6", "FAL_KEY", "MiniMax Music 2.6 via fal: minutes to render, long intros; recaps only",
             _minimax_26, lambda s: 0.15, "fal-ai/minimax-music/v2.6"),
    Provider("fal:minimax-2.0", "FAL_KEY", "MiniMax Music 2.0 via fal: slowest, cheapest MiniMax",
             _minimax_20, lambda s: 0.03, "fal-ai/minimax-music/v2"),
]}


def get(key: str) -> Provider:
    if key not in PROVIDERS:
        raise KeyError(f"unknown provider {key!r}; known: {', '.join(PROVIDERS)}")
    return PROVIDERS[key]
