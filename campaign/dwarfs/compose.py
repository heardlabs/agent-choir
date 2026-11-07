"""2x2 terminal-grid reel: each pane is a dwarf; they sing in turns, a pane glows while its dwarf sings."""
import subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, "/home/kelly/projects/agent-choir")
from choir import audio
from gen import CLIP

HERE = Path(__file__).parent
W = H = 1080
HEAD, GAP, M = 96, 18, 22
PW = (W - 2 * M - GAP) // 2
PH = (H - HEAD - M - GAP) // 2
BAR = 40
VH = PH - BAR
ORDER = [("Merge", "billing-api", (250, 196, 80)), ("Rebase", "website", (110, 160, 250)),
         ("Deploy", "docs", (245, 120, 165)), ("Lint", "desktop-app", (130, 210, 140))]
PART = {"Merge": "lead tenor", "Rebase": "bass", "Deploy": "soprano", "Lint": "baritone"}
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
F = lambda s: ImageFont.truetype(MONO, s)


def pos(i):
    return M + (i % 2) * (PW + GAP), HEAD + (i // 2) * (PH + GAP)


def wrap(d, text, font, width):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= width: cur = t
        else: lines.append(cur); cur = w
    return lines + [cur]


def layers(out: Path, title: str):
    out.mkdir(parents=True, exist_ok=True)
    bg = Image.new("RGB", (W, H), (14, 13, 22)); d = ImageDraw.Draw(bg)
    d.text((M + 8, 26), "agent-choir", font=F(44), fill=(235, 235, 245))
    d.text((M + 340, 40), title, font=F(22), fill=(130, 128, 150))
    for i, (s, proj, col) in enumerate(ORDER):
        x, y = pos(i)
        d.rounded_rectangle([x, y, x + PW, y + PH], 14, fill=(28, 27, 40))
        for j, c in enumerate([(255, 95, 87), (254, 188, 46), (40, 200, 64)]):
            d.ellipse([x + 16 + j * 22, y + 14, x + 28 + j * 22, y + 26], fill=c)
        d.text((x + 92, y + 10), proj, font=F(20), fill=(200, 200, 215))
        d.text((x + PW - 16, y + 10), f"{s} · {PART[s]}", font=F(18), fill=col, anchor="ra")
    bg.save(out / "bg.png")
    for i, (s, proj, col) in enumerate(ORDER):
        # glow border
        g = Image.new("RGBA", (PW + 24, PH + 24), (0, 0, 0, 0)); gd = ImageDraw.Draw(g)
        gd.rounded_rectangle([6, 6, PW + 18, PH + 18], 18, outline=col + (255,), width=6)
        g = Image.alpha_composite(g.filter(ImageFilter.GaussianBlur(6)), g)
        g.save(out / f"glow{i}.png")
        # caption strip
        c = Image.new("RGBA", (PW, 130), (0, 0, 0, 0)); cd = ImageDraw.Draw(c)
        for yy in range(130): cd.line([(0, yy), (PW, yy)], fill=(10, 10, 16, int(215 * yy / 130)))
        lines = wrap(cd, "♪ " + CLIP[s][1], F(24), PW - 36)
        for k, ln in enumerate(lines[-3:]):
            cd.text((18, 130 - 14 - (len(lines[-3:]) - k) * 31), ln, font=F(24), fill=(255, 255, 255))
        c.save(out / f"cap{i}.png")


WIN = {"Merge": (2.8, 10.8), "Rebase": (0.0, 7.0), "Deploy": (3.6, 10.3), "Lint": (1.0, 7.0)}  # where Lyria sings the line


def render(direction: str, title: str, out_mp4: Path, overlap: float = 0.6, src=None, win=None):
    win = {**WIN, **(win or {})}
    src = src or {s: HERE / direction / f"{s}.mp4" for s, _, _ in ORDER}
    L = HERE / "layers" / direction; layers(L, title)
    durs = {s: win[s][1] - win[s][0] for s, _, _ in ORDER}
    starts, t = {}, 0.6
    for s, _, _ in ORDER:
        starts[s] = t; t += durs[s] - overlap
    total = t + overlap + 1.2
    ff = [audio.ffmpeg(), "-nostdin", "-y", "-loglevel", "error", "-loop", "1", "-t", f"{total:.2f}", "-i", str(L / "bg.png")]
    for s, _, _ in ORDER: ff += ["-i", str(src[s])]
    for i in range(4): ff += ["-loop", "1", "-t", f"{total:.2f}", "-i", str(L / f"glow{i}.png")]
    for i in range(4): ff += ["-loop", "1", "-t", f"{total:.2f}", "-i", str(L / f"cap{i}.png")]
    fc, last = [], "0:v"
    for i, (s, _, _) in enumerate(ORDER):
        st, du = starts[s], durs[s]
        fc.append(f"[{i+1}:v]trim={win[s][0]:.2f}:{win[s][1]:.2f},setpts=PTS-STARTPTS,fps=30,scale={PW}:{VH}:force_original_aspect_ratio=increase,"
                  f"crop={PW}:{VH}:(iw-{PW})/2:(ih-{VH})/5,format=yuv420p,"
                  f"tpad=start_duration={st:.2f}:start_mode=clone:stop_mode=clone:stop_duration={total:.2f},trim=0:{total:.2f}[v{i}]")
        x, y = pos(i)
        on = f"between(t,{st:.2f},{st+du:.2f})"
        fc.append(f"[{last}][{5+i}:v]overlay={x-12}:{y-12}:enable='{on}'[g{i}]")
        fc.append(f"[g{i}][v{i}]overlay={x}:{y+BAR}[p{i}]")
        fc.append(f"[p{i}][{9+i}:v]overlay={x}:{y+PH-130}:enable='{on}',drawbox=x={x}:y={y+BAR}:w={PW}:h={VH}:color=black@0.5:t=fill:enable='not({on})'[c{i}]")
        last = f"c{i}"
    fc.append(f"[{last}]format=yuv420p[vout]")
    for i, (s, _, _) in enumerate(ORDER):
        d = int(starts[s] * 1000)
        fc.append(f"[{i+1}:a]atrim={win[s][0]:.2f}:{win[s][1]:.2f},asetpts=PTS-STARTPTS,afade=t=in:d=0.15,afade=t=out:st={durs[s]-0.5:.2f}:d=0.5,aformat=channel_layouts=stereo:sample_rates=44100,adelay={d}|{d}[a{i}]")
    fc.append("[a0][a1][a2][a3]amix=inputs=4:normalize=0,loudnorm=I=-15:TP=-1.5,apad[aout]")
    ff += ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.2f}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+faststart", str(out_mp4)]
    r = subprocess.run(ff, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if r.returncode: raise RuntimeError(r.stderr[-1500:])
    return out_mp4, total


if __name__ == "__main__":
    (HERE / "out").mkdir(exist_ok=True)
    titles = {"clay": "the claymation mine crew", "cinematic": "the forge-hall choir", "pixel": "the 16-bit crew", "felt": "the puppet show"}
    for k in sys.argv[1:] or titles:
        print(render(k, titles[k], HERE / "out" / f"{k}-grid.mp4", win={"Deploy": (0.0, 10.2)} if k == "felt" else None))
