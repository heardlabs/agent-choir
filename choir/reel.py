"""Campaign video: a grid of terminals, each with a 16-bit dwarf who sings.

Takes clips from the ledger (what your agents actually sang) and renders a
1080x1080 MP4 for X / TikTok / RedNote. Each singer is a pixel sprite with a
closed, half-open and open mouth; the mouth follows the loudness of that
singer's own clip, so it costs nothing beyond the clips themselves.
``stagger`` controls the choir:
  - default: agents take turns (0.3 s gap)
  - small stagger (e.g. 1.5): they come in one after another and overlap,
    like a round.
"""

from __future__ import annotations

import array
import math
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from choir import audio, ledger
from choir.cast import by_name

SIZE = 1080
FPS = 15  # pixel art reads best at a low, steady frame rate
BG = (14, 12, 22)
PANE = (28, 26, 40)
BAR = (40, 37, 56)
FG = (236, 232, 245)
DIM = (120, 114, 140)
SPRITES = Path(__file__).parent / "assets" / "sprites"
SPRITE_PX = 96
_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Monaco.ttf",
]


@lru_cache(maxsize=None)
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
    levels: list[int]  # mouth frame (0 closed, 1 half, 2 open) per video frame


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


@lru_cache(maxsize=None)
def sprite(name: str, mouth: int, scale: int, dim: bool) -> Image.Image:
    """One frame of a singer's sprite, scaled up with hard pixel edges."""
    path = SPRITES / f"{name}.png"
    if not path.exists():
        return Image.new("RGB", (SPRITE_PX * scale, SPRITE_PX * scale), PANE)
    strip = Image.open(path).convert("RGB")
    f = strip.crop((mouth * SPRITE_PX, 0, (mouth + 1) * SPRITE_PX, SPRITE_PX))
    if dim:
        f = Image.blend(f, Image.new("RGB", f.size, PANE), 0.55)
    return f.resize((SPRITE_PX * scale, SPRITE_PX * scale), Image.NEAREST)


def mouth_levels(clip: Path, fps: int = FPS) -> list[int]:
    """Loudness per video frame, mapped to a mouth shape (0, 1, 2)."""
    rate = 8000
    raw = subprocess.run([audio.ffmpeg(), "-nostdin", "-loglevel", "error", "-i", str(clip), "-ac", "1",
                          "-ar", str(rate), "-f", "s16le", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout
    s = array.array("h")
    s.frombytes(raw[: len(raw) // 2 * 2])
    hop = rate // fps
    rms = [math.sqrt(sum(x * x for x in s[i:i + hop]) / max(1, len(s[i:i + hop]))) for i in range(0, len(s), hop)]
    if not rms:
        return []
    ref = sorted(rms)[int(len(rms) * 0.95)] or 1.0
    out = [0 if r < 0.3 * ref else 1 if r < 0.72 * ref else 2 for r in rms]
    # A held note looks frozen with the mouth stuck open: close it a little every few frames.
    run = 0
    for i, m in enumerate(out):
        run = run + 1 if m == 2 else 0
        if run and run % 4 == 0:
            out[i] = 1
    return out


def frame(panes: list[dict], active: dict[int, tuple[dict, int]], last: dict[int, str], blink: bool = False) -> Image.Image:
    """``active`` maps pane -> (entry, mouth); ``last`` is the last line each pane sang."""
    img = Image.new("RGB", (SIZE, SIZE), BG)
    d = ImageDraw.Draw(img)
    d.text((32, 34), "agent-choir", font=_font(40), fill=FG)
    d.text((340, 46), "your agents, singing about their work", font=_font(22), fill=DIM)
    boxes = layout(len(panes))
    fsize = 30 if len(panes) <= 2 else 22 if len(panes) <= 4 else 17
    f, fb = _font(fsize), _font(fsize - 2)
    for i, (pane, box) in enumerate(zip(panes, boxes)):
        singer = by_name(pane["singer"])
        on = i in active
        x0, y0, x1, y1 = box
        w, h = x1 - x0, y1 - y0
        if on:
            d.rounded_rectangle([x0 - 5, y0 - 5, x1 + 5, y1 + 5], 18, fill=singer.color)
        d.rounded_rectangle(box, 14, fill=PANE)
        d.rounded_rectangle([x0, y0, x1, y0 + 44], 14, fill=BAR)
        d.rectangle([x0, y0 + 30, x1, y0 + 44], fill=BAR)
        for k, col in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
            d.ellipse([x0 + 16 + k * 22, y0 + 15, x0 + 30 + k * 22, y0 + 29], fill=col)
        d.text((x0 + 90, y0 + 11), pane["project"], font=fb, fill=FG if on else DIM)
        d.text((x1 - 16, y0 + 11), f"{singer.name} · {singer.part}", font=fb, fill=singer.color, anchor="ra")

        # sprite: as big as fits (whole-number scale keeps the pixels square)
        text_h = int(fsize * 1.3) * 2 + 18
        scale = max(1, min((w - 40) // SPRITE_PX, (h - 44 - text_h - 16) // SPRITE_PX))
        mouth = active[i][1] if on else 0
        sp = sprite(singer.name, mouth, scale, dim=not on)
        bob = -scale * 2 if on and mouth == 2 else 0
        sx = x0 + (w - sp.width) // 2
        sy = y0 + 52 + bob
        img.paste(sp, (sx, sy))

        ty = y0 + 52 + sp.height + 10
        line = active[i][0]["line"] if on else last.get(i)
        if line:
            for wl in _wrap(d, ("♪ " if on else "  ") + line, f, w - 36)[:2]:
                d.text((x0 + 18, ty), wl, font=f, fill=FG if on else DIM)
                ty += int(fsize * 1.3)
        else:
            d.text((x0 + 18, ty), "▍ working…" if not blink else "  working…", font=f, fill=DIM)
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
        cues.append(Cue(index[e["agent"]], t, t + dur, e, mouth_levels(clip)))
        t = t + (stagger if stagger is not None else dur + gap)
    total = max(c.end for c in cues) + 1.2

    inputs, filters = [], []
    for i, c in enumerate(cues):
        inputs += ["-i", str((ledger.clips_dir() / c.entry["clip"]).resolve())]
        ms = int(c.start * 1000)
        filters.append(f"[{i + 1}:a]adelay={ms}|{ms}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(cues)))
    filters.append(f"{mix}amix=inputs={len(cues)}:normalize=0:duration=longest,apad=whole_dur={total:.3f},atrim=0:{total:.3f}[aout]")
    # (a bare `apad` is endless; with a stdin video input ffmpeg could then spin forever)
    cmd = [audio.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{SIZE}x{SIZE}", "-r", str(FPS), "-i", "-", *inputs,
           "-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[aout]",
           "-vf", "format=yuv420p", "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-tune", "animation",
           "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(out.resolve())]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    prev_key, prev_bytes = None, b""
    try:
        for n in range(int(total * FPS) + 1):
            now = n / FPS
            active, last = {}, {}
            for c in cues:
                if c.start <= now < c.end:
                    k = int((now - c.start) * FPS)
                    active[c.pane] = (c.entry, c.levels[k] if k < len(c.levels) else 0)
                elif c.end <= now:
                    last[c.pane] = c.entry["line"]
            blink = int(now * 2) % 2 == 1
            key = (tuple(sorted((k, v[0]["clip"], v[1]) for k, v in active.items())), tuple(sorted(last.items())), blink)
            if key != prev_key:  # most frames repeat; only redraw on change
                prev_bytes = frame(panes, active, last, blink).tobytes()
                prev_key = key
            p.stdin.write(prev_bytes)
        p.stdin.close()
    except BrokenPipeError:
        pass
    err = p.stderr.read().decode(errors="replace")
    if p.wait() != 0:
        raise RuntimeError(f"ffmpeg: {err[-600:]}")
    return out
