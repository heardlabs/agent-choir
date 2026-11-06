"""Clean a take up and play it.

Every take goes through one ffmpeg pass: drop leading silence, trim to
``max_seconds`` with a fade, level the loudness, and pan to the singer's seat.
Playback uses whatever the OS has (afplay, ffplay, paplay, aplay). Clips take
turns through a lock unless ``overlap`` is on.
"""

from __future__ import annotations

import fcntl
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

from choir import config


def ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def seconds(path: Path) -> float:
    r = subprocess.run([ffmpeg(), "-nostdin", "-hide_banner", "-i", str(path)], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr)
    if not m:
        raise RuntimeError(f"could not read duration of {path}")
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def pan_gains(pan: float) -> tuple[float, float]:
    """Constant-power pan: -1 hard left, 0 centre, +1 hard right."""
    a = (pan + 1) * math.pi / 4
    return math.cos(a) * math.sqrt(2), math.sin(a) * math.sqrt(2)


def finish(src: Path, dest: Path, pan: float = 0.0, max_s: float = 12.0, volume: float = 0.9) -> Path:
    total = min(seconds(src), max_s + 3)  # +3: allow for trimmed leading silence
    fade_at = max(0.0, max_s - 0.8)
    left, right = pan_gains(pan)
    chain = ",".join([
        "silenceremove=start_periods=1:start_threshold=-40dB:start_silence=0.05",
        f"atrim=0:{max_s:.2f}",
        f"afade=t=out:st={fade_at:.2f}:d=0.8",
        "loudnorm=I=-16:TP=-1.5:LRA=11",
        f"volume={volume:.2f}",
        "aformat=channel_layouts=stereo:sample_rates=44100",
        f"pan=stereo|c0={left:.3f}*c0|c1={right:.3f}*c1",
    ])
    cmd = [ffmpeg(), "-nostdin", "-y", "-hide_banner", "-loglevel", "error", "-t", f"{total:.2f}", "-i", str(src),
           "-af", chain, "-c:a", "pcm_s16le", str(dest)]
    r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg: {r.stderr[-400:]}")
    return dest


def player() -> list[str] | None:
    if sys.platform == "darwin" and shutil.which("afplay"):
        return ["afplay"]
    for cmd in (["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"], ["paplay"], ["pw-play"], ["aplay", "-q"]):
        if shutil.which(cmd[0]):
            return cmd
    return None


def play(path: Path, overlap: bool = False) -> bool:
    cmd = player()
    if not cmd:
        return False
    if overlap:
        subprocess.run([*cmd, str(path)], check=False, stdin=subprocess.DEVNULL)
        return True
    lock = config.STATE_DIR / "play.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)  # take turns
        try:
            subprocess.run([*cmd, str(path)], check=False, stdin=subprocess.DEVNULL)
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)
    return True
