"""Turn a take into a tweetable MP4: square video, lyric cards, who's singing.

X/Twitter has no audio-only posts, so every take becomes a 1080x1080 H.264 +
AAC video under 2:20. Cards are drawn with Pillow and stitched with the
ffmpeg binary that ships in ``imageio-ffmpeg`` (no system ffmpeg needed).
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from choir.cast import CAST, by_name
from choir.song import Section, Song

SIZE = 1080
MAX_TWEET_S = 140.0
BG = (24, 20, 38)
FG = (250, 244, 230)
DIM = (160, 150, 180)
ACCENT = (255, 196, 80)
PART_COLOR = {
    "Merge": (255, 196, 80), "Rebase": (120, 170, 255), "Deploy": (255, 130, 170),
    "Lint": (140, 220, 160), "Docs": (200, 160, 255), "Patch": (255, 160, 100),
    "Grep": (180, 180, 180),
}

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _font(size: int) -> ImageFont.FreeTypeFont:
    for p in _FONT_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def audio_seconds(path: Path) -> float:
    r = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr)
    if not m:
        raise RuntimeError(f"could not read duration of {path}")
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _choir_row(draw: ImageDraw.ImageDraw, singing: set[str]) -> None:
    """Seven dots along the bottom, lit when that voice is singing."""
    f = _font(26)
    n = len(CAST)
    gap = SIZE // (n + 1)
    for i, s in enumerate(CAST):
        x, y = gap * (i + 1), SIZE - 150
        on = "All" in singing or s.name in singing
        col = PART_COLOR[s.name] if on else (70, 64, 90)
        r = 34 if on else 26
        draw.ellipse([x - r, y - r, x + r, y + r], fill=col)
        tw = draw.textlength(s.name, font=f)
        draw.text((x - tw / 2, y + 44), s.name, font=f, fill=FG if on else DIM)


def card(song: Song, section: Section | None, title: bool = False) -> Image.Image:
    img = Image.new("RGB", (SIZE, SIZE), BG)
    d = ImageDraw.Draw(img)
    margin = 90
    if title or section is None:
        f = _font(78)
        y = 260
        for line in _wrap(d, song.title, f, SIZE - 2 * margin):
            d.text((margin, y), line, font=f, fill=ACCENT)
            y += 96
        sub = _font(36)
        d.text((margin, y + 30), "an a cappella group of AI agents", font=sub, fill=FG)
        d.text((margin, y + 80), "singing about the work they just did", font=sub, fill=DIM)
        _choir_row(d, {"All"})
        return img
    singers = section.singers or ["All"]
    who = "Everybody" if "All" in singers else " & ".join(singers)
    d.text((margin, 90), section.label.upper(), font=_font(30), fill=DIM)
    col = ACCENT if "All" in singers else PART_COLOR.get(singers[0], ACCENT)
    d.text((margin, 130), who, font=_font(60), fill=col)
    if "All" not in singers:
        credit = song.credits.get(singers[0])
        part = by_name(singers[0]).part
        sub = f"{part}" + (f"  ·  {credit}" if credit else "")
        for i, line in enumerate(_wrap(d, sub, _font(28), SIZE - 2 * margin)[:2]):
            d.text((margin, 205 + i * 36), line, font=_font(28), fill=DIM)
    # Largest lyric size that fits between the header and the choir row.
    top, bottom = 300, SIZE - 210
    for size in (56, 50, 44, 38, 34, 30):
        f, lh, gap = _font(size), int(size * 1.27), int(size * 0.35)
        blocks = [_wrap(d, line, f, SIZE - 2 * margin) for line in section.lines]
        if top + sum(len(b) * lh + gap for b in blocks) - gap <= bottom:
            break
    y = top
    for block in blocks:
        for wrapped in block:
            d.text((margin, y), wrapped, font=f, fill=FG)
            y += lh
        y += gap
    _choir_row(d, set(singers))
    return img


def section_times(song: Song, total: float, timings: list[float] | None) -> list[tuple[float, float]]:
    """(start, end) per section. Uses provider timings when the request pinned
    them; otherwise splits the track by line count after a short title card."""
    n = len(song.sections)
    if timings and len(timings) == n + 1 and timings[-1] > 0:
        scale = total / timings[-1]
        return [(timings[i] * scale, timings[i + 1] * scale) for i in range(n)]
    weights = [max(1, len(s.lines)) for s in song.sections]
    t, out = 0.0, []
    for w in weights:
        dur = total * w / sum(weights)
        out.append((t, t + dur))
        t += dur
    return out


def render(song: Song, audio: Path, out: Path, timings: list[float] | None = None) -> Path:
    total = min(audio_seconds(audio), MAX_TWEET_S)
    spans = section_times(song, total, timings)
    title_s = min(2.5, spans[0][1] * 0.5) if spans else 2.5
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        concat = []
        card(song, None, title=True).save(tdp / "c000.png")
        concat.append(("c000.png", title_s))
        for i, (sec, (a, b)) in enumerate(zip(song.sections, spans), start=1):
            if i == 1:
                a = title_s
            card(song, sec).save(tdp / f"c{i:03d}.png")
            concat.append((f"c{i:03d}.png", max(0.5, b - a)))
        lst = "".join(f"file '{name}'\nduration {dur:.3f}\n" for name, dur in concat)
        lst += f"file '{concat[-1][0]}'\n"  # concat demuxer needs the last frame repeated
        (tdp / "list.txt").write_text(lst)
        cmd = [
            ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(tdp / "list.txt"),
            "-i", str(audio.resolve()),
            "-t", f"{total:.3f}",
            "-vf", "fps=30,format=yuv420p",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
            "-movflags", "+faststart",
            str(out.resolve()),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=td)
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {r.stderr[-800:]}")
    return out
