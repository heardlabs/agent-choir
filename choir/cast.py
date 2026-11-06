"""The choir: seven original singers. Each terminal gets one and keeps it.

A singer is a voice description (what the music model hears), a stereo seat
(so two terminals singing back to back sound like they're standing in
different places), a seed (ACE-Step reuses it, so a singer sounds more like
itself from clip to clip) and a colour for the reel video.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Singer:
    name: str
    part: str
    voice: str
    tags: str  # ACE-Step style tags
    pan: float  # -1 left .. +1 right
    seed: int
    color: tuple[int, int, int]


CAST: tuple[Singer, ...] = (
    Singer("Merge", "lead tenor", "bright confident male tenor lead vocal",
           "male tenor vocal, bright, confident", 0.0, 1101, (255, 196, 80)),
    Singer("Rebase", "bass", "deep rumbling male bass vocal, basso profundo",
           "male bass vocal, deep, low", -0.45, 2202, (120, 170, 255)),
    Singer("Deploy", "soprano", "soaring clear female soprano vocal",
           "female soprano vocal, high, clear", 0.45, 3303, (255, 130, 170)),
    Singer("Lint", "baritone", "precise slightly fussy male baritone vocal",
           "male baritone vocal, crisp", -0.25, 4404, (140, 220, 160)),
    Singer("Docs", "alto", "warm smooth female alto vocal",
           "female alto vocal, warm, smooth", 0.25, 5505, (200, 160, 255)),
    Singer("Patch", "second tenor", "eager quick male tenor vocal, slightly nasal",
           "male tenor vocal, quick, eager", -0.6, 6606, (255, 160, 100)),
    Singer("Grep", "falsetto", "playful male falsetto vocal",
           "male falsetto vocal, playful, airy", 0.6, 7707, (180, 200, 200)),
)

NAMES = tuple(s.name for s in CAST)


def by_name(name: str) -> Singer:
    for s in CAST:
        if s.name.lower() == name.lower():
            return s
    raise KeyError(f"no singer {name!r}; choose from {', '.join(NAMES)}")
