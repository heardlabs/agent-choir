"""The one path every sung line takes: turn -> line -> singer -> take -> play."""

from __future__ import annotations

import hashlib
import shutil
import time

from choir import agents, audio, config, ledger, providers, summarize
from choir.agents import Turn


def _log(msg: str) -> None:
    log = config.STATE_DIR / "choir.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as fh:
        fh.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")


def perform(turn: Turn, settings: config.Settings | None = None, play: bool = True,
            line: str | None = None, echo=print) -> dict | None:
    s = settings or config.load()
    if s.muted:
        return None
    if line is None:
        if len(turn.message.split()) < s.min_words:
            return None
        line = summarize.summarize(turn.message, s.summarizer, s.summarizer_model)
    if not line:
        return None
    singer = agents.singer_for(turn, s.voices)
    prov = providers.get(s.provider)
    if not prov.available():
        msg = f"{prov.key} needs {prov.needs} (env or {config.CONFIG_DIR / 'env'})"
        _log(msg)
        echo(f"agent-choir: {msg}")
        return None
    secs = providers.clip_seconds(line, s.max_seconds)
    cost = prov.cost(secs)
    if ledger.spent_today() + cost > s.daily_budget_usd:
        _log(f"budget: skip ({ledger.spent_today():.2f} spent of {s.daily_budget_usd:.2f})")
        return None

    clips = ledger.clips_dir()
    h = hashlib.sha1(f"{prov.key}|{singer.name}|{s.style}|{line}".encode()).hexdigest()[:16]
    raw = clips / f"{h}.raw"
    final = clips / f"{h}.wav"
    t0 = time.time()
    cached = final.exists()
    if not cached:
        try:
            prov.sing(line, singer, s.style, secs, raw)
            audio.finish(raw, final, singer.pan, s.max_seconds, s.volume)
        except Exception as e:
            _log(f"{prov.key} failed for {turn.project}: {e}")
            echo(f"agent-choir: {prov.key} failed: {e}")
            return None
        finally:
            raw.unlink(missing_ok=True)
    entry = ledger.record(
        agent=turn.agent, project=turn.project, source=turn.source, singer=singer.name,
        line=line, provider=prov.key, cost=0.0 if cached else cost, clip=final.name,
        render_s=round(time.time() - t0, 1),
    )
    _log(f"{singer.name} ({turn.project}) via {prov.key}: {line}")
    echo(f"♪ {singer.name} ({turn.project}): {line}")
    if play:
        audio.play(final, overlap=s.overlap)
    return entry


def clip_path(entry: dict):
    return ledger.clips_dir() / entry["clip"]


def have_ffmpeg() -> bool:
    try:
        return bool(audio.ffmpeg())
    except Exception:
        return bool(shutil.which("ffmpeg"))
