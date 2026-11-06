"""The ensemble: seven original singers, one per vocal part.

Each coding agent gets one singer. The names are git verbs, so the joke works
for developers without leaning on anyone else's characters. When fewer than
seven agents worked, the spare singers sing backing and chorus only.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Singer:
    name: str
    part: str
    voice: str  # how a music model should hear this part


CAST: tuple[Singer, ...] = (
    Singer("Merge", "lead tenor", "bright confident lead tenor"),
    Singer("Rebase", "bass", "deep rumbling basso profundo"),
    Singer("Deploy", "soprano", "soaring clear soprano"),
    Singer("Lint", "baritone", "precise slightly fussy baritone"),
    Singer("Docs", "alto", "warm smooth alto"),
    Singer("Patch", "second tenor", "eager quick second tenor"),
    Singer("Grep", "vocal percussion", "beatboxer keeping the rhythm with mouth percussion"),
)

# Grep keeps the beat and never gets a verse of its own.
VERSE_SINGERS = tuple(s for s in CAST if s.part != "vocal percussion")
MAX_AGENTS = len(VERSE_SINGERS)


def by_name(name: str) -> Singer:
    for s in CAST:
        if s.name.lower() == name.lower():
            return s
    raise KeyError(name)


def assign(agent_ids: list[str]) -> dict[str, Singer]:
    """Agent id -> singer, in order. Agents past MAX_AGENTS are dropped by
    the caller (work.top_agents) before we get here."""
    if len(agent_ids) > MAX_AGENTS:
        raise ValueError(f"at most {MAX_AGENTS} agents can sing, got {len(agent_ids)}")
    return {aid: VERSE_SINGERS[i] for i, aid in enumerate(agent_ids)}
