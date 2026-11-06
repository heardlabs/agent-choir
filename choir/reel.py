"""Campaign video: a grid of terminals, each lighting up as its agent sings.

Takes clips from the ledger (what your agents actually sang) and renders a
1080x1080 MP4 for X / TikTok / RedNote. ``stagger`` controls the choir:
  - stagger >= clip length: agents take turns (default: 0.3 s gap)
  - small stagger (e.g. 1.5): they come in one after another and overlap,
    like a round.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from choir import audio, ledger
from choir.cast import by_name

SIZE = 1080
BG = (14, 12, 22)
PANE = (28, 26, 40)
BAR = (40, 37, 56)
FG = (236, 232, 245)
DIM = (120, 114, 140)
_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Monaco.ttf",
]


def _font(size: int):
    for p in _FONTS:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


@dataclass
class Cue:
    pane: int
    start: float
    end: float
    entry: dict


def _wrap(d, text, font, width):
    out, cur = [], ""
    for w in text.split():
        t = f"{cur} {w}".strip()
        if d.textlength(t, font=font) <= width:
            cur = t
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return out


def layout(n: int) -> list[tuple[int, int, int, int]]:
    cols = 1 if n == 1 else 2 if n <= 4 else 3
    rows = -(-n // cols)
    top, pad = 110, 24
    w = (SIZE - pad * (cols + 1)) // cols
    h = (SIZE - top - pad * (rows + 1)) // rows
    boxes = []
    for i in range(n):
        r, c = divmod(i, cols)
        x = pad + c * (w + pad)
        y = top + pad + r * (h + pad)
        boxes.append((x, y, x + w, y + h))
    return boxes


def frame(panes: list[dict], active: dict[int, dict], sung: dict[int, list[str]]) -> Image.Image:
    img = Image.new("RGB", (SIZE, SIZE), BG)
    d = ImageDraw.Draw(img)
    d.text((32, 34), "agent-choir", font=_font(40), fill=FG)
    d.text((340, 46), "your agents, singing about their work", font=_font(22), fill=DIM)
    boxes = layout(len(panes))
    fsize = 30 if len(panes) <= 2 else 24 if len(panes) <= 4 else 19
    f, fb = _font(fsize), _font(fsize - 2)
    for i, (pane, box) in enumerate(zip(panes, boxes)):
        singer = by_name(pane["singer"])
        on = i in active
        x0, y0, x1, y1 = box
        if on:
            d.rounded_rectangle([x0 - 5, y0 - 5, x1 + 5, y1 + 5], 18, fill=singer.color)
        d.rounded_rectangle(box, 14, fill=PANE)
        d.rounded_rectangle([x0, y0, x1, y0 + 44], 14, fill=BAR)
        d.rectangle([x0, y0 + 30, x1, y0 + 44], fill=BAR)
        for k, col in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
            d.ellipse([x0 + 16 + k * 22, y0 + 15, x0 + 30 + k * 22, y0 + 29], fill=col)
        d.text((x0 + 90, y0 + 11), f"{pane['project']}", font=fb, fill=FG if on else DIM)
        tag = f"{singer.name} · {singer.part}"
        d.text((x0 + 18, y0 + 60), tag, font=fb, fill=singer.color)
        y = y0 + 60 + fsize + 18
        for line in sung.get(i, [])[-2:]:
            col = FG if (on and line == active[i]["line"]) else DIM
            for wl in _wrap(d, ("♪ " if col == FG else "  ") + line, f, x1 - x0 - 36):
                if y > y1 - fsize - 10:
                    break
                d.text((x0 + 18, y), wl, font=f, fill=col)
                y += int(fsize * 1.3)
            y += 8
        if not on and not sung.get(i):
            d.text((x0 + 18, y), "▍ working…", font=f, fill=DIM)
    return img


def render(entries: list[dict], out: Path, stagger: float | None = None, gap: float = 0.3) -> Path:
    if not entries:
        raise RuntimeError("no clips to put in the reel; let your agents sing first (or `choir demo`)")
    panes: list[dict] = []
    index: dict[str, int] = {}
    for e in entries:
        if e["agent"] not in index:
            index[e["agent"]] = len(panes)
            panes.append({"project": e["project"], "singer": e["singer"]})
    cues, t = [], 0.6
    for e in entries:
        clip = ledger.clips_dir() / e["clip"]
        dur = audio.seconds(clip)
        cues.append(Cue(index[e["agent"]], t, t + dur, e))
        t = t + (stagger if stagger is not None else dur + gap)
    total = max(c.end for c in cues) + 1.2

    # Timeline: a new frame every time someone starts or stops.
    marks = sorted({0.0, total, *[c.start for c in cues], *[c.end for c in cues]})
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        concat = []
        for k, (a, b) in enumerate(zip(marks, marks[1:])):
            if b - a < 0.01:
                continue
            mid = (a + b) / 2
            active = {c.pane: c.entry for c in cues if c.start <= mid < c.end}
            sung: dict[int, list[str]] = {}
            for c in cues:
                if c.start <= mid:
                    sung.setdefault(c.pane, []).append(c.entry["line"])
            name = f"f{k:04d}.png"
            frame(panes, active, sung).save(tdp / name)
            concat.append((name, b - a))
        lst = "".join(f"file '{n}'\nduration {d:.3f}\n" for n, d in concat) + f"file '{concat[-1][0]}'\n"
        (tdp / "list.txt").write_text(lst)

        inputs, filters = [], []
        for i, c in enumerate(cues):
            inputs += ["-i", str((ledger.clips_dir() / c.entry["clip"]).resolve())]
            ms = int(c.start * 1000)
            filters.append(f"[{i + 1}:a]adelay={ms}|{ms}[a{i}]")
        mix = "".join(f"[a{i}]" for i in range(len(cues)))
        filters.append(f"{mix}amix=inputs={len(cues)}:normalize=0:duration=longest,apad,atrim=0:{total:.3f}[aout]")
        cmd = [audio.ffmpeg(), "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
               "-f", "concat", "-safe", "0", "-i", str(tdp / "list.txt"), *inputs,
               "-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[aout]",
               "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-crf", "20", "-preset", "medium",
               "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", "-movflags", "+faststart",
               str(out.resolve())]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=td, stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg: {r.stderr[-600:]}")
    return out
