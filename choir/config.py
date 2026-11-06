"""Settings and keys.

Keys come from the environment, or from ``~/.config/agent-choir/env``
(``KEY=value`` lines). The file matters because Codex and some terminals do
not pass your shell environment to hook programs.

Settings live in ``~/.config/agent-choir/config.toml``; every key is optional.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("CHOIR_CONFIG_DIR", Path.home() / ".config" / "agent-choir"))
STATE_DIR = Path(os.environ.get("CHOIR_STATE_DIR", Path.home() / ".local" / "state" / "agent-choir"))

KEY_NAMES = ("FAL_KEY", "ELEVENLABS_API_KEY", "ANTHROPIC_API_KEY")


@dataclass
class Settings:
    # Which model sings. See `choir providers`.
    provider: str = "fal:lyria3"
    # Who writes the sung line: "anthropic" (needs ANTHROPIC_API_KEY), "claude-cli"
    # (your local `claude` login, slower), or "plain" (no LLM: first sentence, trimmed).
    summarizer: str = "auto"
    summarizer_model: str = "claude-opus-5-5"
    # Longest clip we play, in seconds (longer takes are trimmed with a fade).
    max_seconds: float = 12.0
    # Stop singing for the day after this much spend (USD, list prices).
    daily_budget_usd: float = 3.0
    # Let terminals sing over each other (a real choir), or take turns.
    overlap: bool = False
    # Volume, 0..1
    volume: float = 0.9
    # Extra words added to every style prompt, e.g. "barbershop" or "gospel".
    style: str = "a cappella, doo-wop, no instruments, upbeat, short jingle"
    # Pin a singer to a project folder name: {"heard-api": "Rebase"}
    voices: dict[str, str] = field(default_factory=dict)
    # Skip messages shorter than this many words (e.g. "Done.").
    min_words: int = 4
    muted: bool = False


def load_keys() -> None:
    env_file = CONFIG_DIR / "env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and not os.environ.get(k):
            os.environ[k] = v


def load() -> Settings:
    load_keys()
    s = Settings()
    path = CONFIG_DIR / "config.toml"
    if path.exists():
        data = tomllib.loads(path.read_text())
        known = {f.name for f in fields(Settings)}
        for k, v in data.items():
            if k in known:
                setattr(s, k, v)
    if (CONFIG_DIR / "mute").exists() or os.environ.get("CHOIR_MUTE"):
        s.muted = True
    return s


EXAMPLE = '''# agent-choir settings. Every line is optional.

# Who sings: fal:lyria3 (cheap, clear), fal:elevenlabs or elevenlabs (best, $$),
# fal:ace-step (pennies, slurred), fal:lyria3-pro, fal:minimax-2.6 (slow, minutes).
provider = "fal:lyria3"

# Who writes the line: auto | anthropic | claude-cli | plain
summarizer = "auto"

max_seconds = 12
daily_budget_usd = 3.0
overlap = false
style = "a cappella, doo-wop, no instruments, upbeat, short jingle"

# Pin singers to projects (folder names). Singers: Merge Rebase Deploy Lint Docs Patch Grep
[voices]
# my-api = "Rebase"
'''
