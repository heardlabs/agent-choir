"""Send one song to several music models and lay the takes side by side."""

from __future__ import annotations

import html
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from choir.providers import Provider, fal
from choir.song import Song


def estimate(song: Song, providers: list[Provider]) -> tuple[list[tuple[str, float]], float]:
    rows = [(p.key, p.cost(song)) for p in providers]
    return rows, sum(c for _, c in rows)


def _ext(url: str, content_type: str | None) -> str:
    for e in (".mp3", ".wav", ".flac", ".ogg", ".m4a"):
        if url.lower().split("?")[0].endswith(e):
            return e
    return {"audio/wav": ".wav", "audio/x-wav": ".wav", "audio/flac": ".flac"}.get(content_type or "", ".mp3")


def take(song: Song, p: Provider, outdir: Path, log=print) -> dict:
    payload = p.build(song)
    (outdir / f"{p.key}.request.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    t0 = time.time()
    try:
        result = fal.run(p.model, payload, log=log)
    except Exception as e:  # one bad provider must not sink the bake-off
        log(f"  {p.key} failed: {e}")
        return {"provider": p.key, "error": str(e)}
    audio = result.get("audio") or {}
    url = audio.get("url") if isinstance(audio, dict) else None
    if not url:
        return {"provider": p.key, "error": f"no audio in response: {json.dumps(result)[:300]}"}
    path = fal.download(url, outdir / f"{p.key}{_ext(url, audio.get('content_type'))}")
    (outdir / f"{p.key}.response.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    secs = round(time.time() - t0)
    log(f"  {p.key}: done in {secs}s -> {path.name}")
    return {"provider": p.key, "file": path.name, "seconds": secs, "cost": p.cost(song), "timings": p.timings(song)}


def bakeoff(song: Song, providers: list[Provider], outdir: Path, log=print) -> list[dict]:
    outdir.mkdir(parents=True, exist_ok=True)
    song.save(outdir / "song.json")
    with ThreadPoolExecutor(max_workers=len(providers)) as pool:
        results = list(pool.map(lambda p: take(song, p, outdir, log), providers))
    (outdir / "takes.json").write_text(json.dumps(results, indent=2))
    write_index(song, providers, results, outdir)
    return results


def write_index(song: Song, providers: list[Provider], results: list[dict], outdir: Path) -> Path:
    """A plain local page to listen to every take next to the lyrics."""
    blurbs = {p.key: p.blurb for p in providers}
    rows = []
    for r in results:
        name = html.escape(r["provider"])
        if r.get("file"):
            body = f'<audio controls preload="none" src="{html.escape(r["file"])}"></audio><small>{r["seconds"]}s to render, ~${r["cost"]:.2f}</small>'
        else:
            body = f'<pre class="err">{html.escape(r.get("error", "failed"))}</pre>'
        rows.append(f"<section><h2>{name}</h2><p>{html.escape(blurbs.get(r['provider'], ''))}</p>{body}</section>")
    lyrics = []
    for s in song.sections:
        who = ", ".join(s.singers) or "All"
        lyrics.append(f"<h3>{html.escape(s.label)} <em>{html.escape(who)}</em></h3><p>" + "<br>".join(html.escape(l) for l in s.lines) + "</p>")
    page = f"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(song.title)} takes</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:760px;margin:2rem auto;padding:0 16px;background:#fbf7ef;color:#222}}
section{{border:1px solid #ddd;border-radius:10px;padding:12px 16px;margin:12px 0;background:#fff}}audio{{width:100%}}
h2{{margin:0;font-size:1.05rem}}p{{margin:.3rem 0}}small{{color:#777}}.err{{color:#a00;white-space:pre-wrap}}h3 em{{font-weight:normal;color:#888}}</style>
<h1>{html.escape(song.title)}</h1>
{''.join(rows)}
<h2 style="margin-top:2rem">Lyrics</h2>{''.join(lyrics)}
"""
    path = outdir / "index.html"
    path.write_text(page)
    return path
