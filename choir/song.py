"""The song: what the lyricist writes and every provider renders from."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from choir.cast import CAST, by_name

SECTION_KINDS = ("intro", "verse", "pre-chorus", "chorus", "bridge", "outro")

# The friend's reference is a 1937 Disney song that is still under copyright.
# The bit is the idea (a work crew singing a cappella about their job),
# never the song. A take containing any of these is rejected.
BANNED = (
    "whistle while you work",
    "heigh-ho",
    "heigh ho",
    "hi-ho",
    "hi ho",
    "off to work we go",
    "snow white",
    "dwarf",
    "dwarves",
    "dwarfs",
    "disney",
)

# Shared style for every provider. The a cappella part is the whole point,
# so it is said three ways.
STYLE = (
    "a cappella vocal ensemble, seven voices, no instruments at all, "
    "barbershop and doo-wop harmonies, beatboxed vocal percussion, "
    "upbeat marching work song, call and response, playful and warm, "
    "about 116 BPM, major key"
)
NEGATIVE = ["instruments", "guitar", "piano", "drums", "synth", "bass guitar", "strings", "electronic"]


@dataclass
class Section:
    kind: str
    singers: list[str]
    lines: list[str]

    @property
    def label(self) -> str:
        return self.kind.replace("-", " ").title()


@dataclass
class Song:
    title: str
    sections: list[Section]
    # singer name -> "project: what they did" (for the video credits)
    credits: dict[str, str] = field(default_factory=dict)
    style: str = STYLE

    # --- validation -----------------------------------------------------

    def problems(self) -> list[str]:
        out = []
        names = {s.name for s in CAST}
        if not self.sections:
            out.append("no sections")
        if not any(s.kind == "chorus" for s in self.sections):
            out.append("no chorus")
        for i, s in enumerate(self.sections):
            if s.kind not in SECTION_KINDS:
                out.append(f"section {i}: unknown kind {s.kind!r}")
            if not s.lines:
                out.append(f"section {i}: no lines")
            for n in s.singers:
                if n not in names and n != "All":
                    out.append(f"section {i}: unknown singer {n!r}")
            for line in s.lines:
                if len(line) > 200:
                    out.append(f"section {i}: line over 200 chars")
        text = self.lyrics_text().lower()
        for b in BANNED:
            if re.search(rf"\b{re.escape(b)}\b", text):
                out.append(f"banned phrase {b!r} (keep it original)")
        if len(self.lyrics_text(tags=True)) > 3000:
            out.append("lyrics too long (keep under ~3000 chars)")
        return out

    # --- rendering helpers ---------------------------------------------

    def lyrics_text(self, tags: bool = False, lower_tags: bool = False) -> str:
        parts = []
        for s in self.sections:
            if tags:
                tag = s.label.lower() if lower_tags else s.label
                parts.append(f"[{tag}]")
            parts.extend(s.lines)
            parts.append("")
        return "\n".join(parts).strip()

    def line_count(self) -> int:
        return sum(len(s.lines) for s in self.sections)

    def voices_for(self, section: Section) -> str:
        if not section.singers or "All" in section.singers:
            return "full seven-voice ensemble in tight harmony"
        vs = [by_name(n).voice for n in section.singers]
        return " and ".join(vs) + " solo, ensemble humming underneath"

    # --- io -------------------------------------------------------------

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Song":
        return cls(
            title=d["title"],
            sections=[Section(kind=s["kind"], singers=list(s.get("singers", [])), lines=list(s["lines"])) for s in d["sections"]],
            credits=dict(d.get("credits", {})),
            style=d.get("style", STYLE),
        )

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n")

    @classmethod
    def load(cls, path: Path) -> "Song":
        return cls.from_dict(json.loads(path.read_text()))

    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "-", self.title.lower()).strip("-")[:48] or "song"
