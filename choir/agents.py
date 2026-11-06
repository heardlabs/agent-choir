"""Who is singing: turn a hook call into an agent, and give it a stable singer.

An agent is a terminal when we can tell (tmux pane, iTerm/Terminal session,
WezTerm, kitty, Windows Terminal, herdr), else the agent's session id. A
terminal keeps its singer until it has been quiet for ``RELEASE_S``; new
terminals take the singer that has been free the longest.
"""

from __future__ import annotations

import fcntl
import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from choir import config
from choir.cast import CAST, NAMES, Singer, by_name

RELEASE_S = 6 * 3600

_TERMINAL_VARS = (
    "TMUX_PANE", "HERDR_PANE_ID", "WEZTERM_PANE", "KITTY_WINDOW_ID",
    "ITERM_SESSION_ID", "TERM_SESSION_ID", "WT_SESSION", "ZELLIJ_PANE_ID",
)


@dataclass
class Turn:
    """One finished agent turn."""
    agent: str  # stable key for the terminal or session
    project: str  # folder name, for labels
    message: str  # the agent's final reply
    source: str  # claude | codex | cli


def terminal_key(env: dict[str, str] | None = None) -> str | None:
    env = os.environ if env is None else env
    for var in _TERMINAL_VARS:
        if env.get(var):
            return f"{var}:{env[var]}"
    return None


def from_claude_hook(payload: dict, env: dict[str, str] | None = None) -> Turn:
    cwd = payload.get("cwd") or os.getcwd()
    return Turn(
        agent=terminal_key(env) or f"claude:{payload.get('session_id', '?')}",
        project=Path(cwd).name,
        message=payload.get("last_assistant_message") or "",
        source="claude",
    )


def from_codex_notify(payload: dict, env: dict[str, str] | None = None) -> Turn | None:
    if payload.get("type") != "agent-turn-complete":
        return None
    cwd = payload.get("cwd") or os.getcwd()
    return Turn(
        agent=terminal_key(env) or f"codex:{payload.get('thread-id', '?')}",
        project=Path(cwd).name,
        message=payload.get("last-assistant-message") or "",
        source="codex",
    )


# --- singer assignment ----------------------------------------------------

def _seats_path() -> Path:
    return config.STATE_DIR / "seats.json"


@contextmanager
def _locked(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def singer_for(turn: Turn, pins: dict[str, str] | None = None, now: float | None = None) -> Singer:
    pins = pins or {}
    if turn.project in pins:
        return by_name(pins[turn.project])
    now = time.time() if now is None else now
    path = _seats_path()
    with _locked(path):
        seats: dict = json.loads(path.read_text()) if path.exists() else {}
        # Release quiet terminals.
        seats = {k: v for k, v in seats.items() if now - v["seen"] < RELEASE_S}
        if turn.agent in seats:
            name = seats[turn.agent]["singer"]
        else:
            taken = {v["singer"] for v in seats.values()}
            pinned = set(pins.values())
            free = [n for n in NAMES if n not in taken and n not in pinned]
            if free:
                name = free[0]
            else:  # more terminals than singers: reuse the quietest seat's singer
                name = min(seats.values(), key=lambda v: v["seen"])["singer"]
        seats[turn.agent] = {"singer": name, "project": turn.project, "seen": now}
        path.write_text(json.dumps(seats, indent=2))
    return by_name(name)


def seats() -> dict:
    p = _seats_path()
    return json.loads(p.read_text()) if p.exists() else {}


def reset_seats() -> None:
    _seats_path().unlink(missing_ok=True)


__all__ = ["Turn", "singer_for", "from_claude_hook", "from_codex_notify", "terminal_key", "CAST"]
