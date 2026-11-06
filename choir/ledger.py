"""What was sung, by whom, and what it cost. One JSON line per clip.

The ledger enforces the daily budget and feeds `choir reel`.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from choir import config


def path() -> Path:
    return config.STATE_DIR / "ledger.jsonl"


def clips_dir() -> Path:
    d = config.STATE_DIR / "clips"
    d.mkdir(parents=True, exist_ok=True)
    return d


def record(**entry) -> dict:
    entry.setdefault("ts", time.time())
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def entries(since: float = 0.0) -> list[dict]:
    p = path()
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("ts", 0) >= since:
            out.append(e)
    return out


def spent_today(now: float | None = None) -> float:
    now = time.time() if now is None else now
    midnight = datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    return round(sum(e.get("cost", 0.0) for e in entries(midnight)), 4)
