"""Turn work/{Name}_{closed,half,open}.png into choir/assets/sprites/{Name}.png:
a 3-frame strip (closed, half, open) of true low-res pixels, where only the mouth changes."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

WORK = Path(__file__).parent / "work"
OUT = Path(__file__).resolve().parents[2] / "choir" / "assets" / "sprites"
N = 96  # sprite size in pixels
NAMES = ["Merge", "Rebase", "Deploy", "Lint", "Docs", "Patch", "Grep"]

def small(p):
    return Image.open(p).convert("RGB").resize((N, N), Image.BOX)

def bake(name):
    fr = [small(WORK / f"{name}_{t}.png") for t in ("closed", "half", "open")]
    # one shared palette so unchanged pixels stay identical
    pal = Image.new("RGB", (N * 3, N)); [pal.paste(f, (i * N, 0)) for i, f in enumerate(fr)]
    pal = pal.quantize(40, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert("RGB")
    fr = [np.array(pal.crop((i * N, 0, (i + 1) * N, N))) for i in range(3)]
    base = fr[0]
    out = [base]
    for v in fr[1:]:
        diff = (np.abs(v.astype(int) - base.astype(int)).sum(2) > 60)
        zone = np.zeros_like(diff); zone[int(N*.38):int(N*.72), int(N*.28):int(N*.72)] = True  # mouth area
        d = diff & zone
        if d.sum() < 4:
            out.append(v); continue
        ys, xs = np.nonzero(d)
        y0, y1, x0, x1 = max(ys.min()-2, 0), min(ys.max()+3, N), max(xs.min()-2, 0), min(xs.max()+3, N)
        f = base.copy(); f[y0:y1, x0:x1] = v[y0:y1, x0:x1]
        out.append(f)
    OUT.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.concatenate(out, 1)).save(OUT / f"{name}.png", optimize=True)

if __name__ == "__main__":
    for n in NAMES: bake(n)
    sheet = Image.new("RGB", (N * 3 * 7 // 2 * 2, N * 4))
    big = [Image.open(OUT / f"{n}.png").resize((N * 3 * 2, N * 2), Image.NEAREST) for n in NAMES]
    c = Image.new("RGB", (N * 6 * 2, N * 2 * 4), (15, 31, 23))
    for i, b in enumerate(big): c.paste(b, ((i % 2) * N * 6, (i // 2) * N * 2))
    c.save(WORK / "baked.png")
