"""Turn an agent's final reply into one short line worth singing.

Same idea as Heard's narration: what got done, in plain words, not the whole
reply. "anthropic" uses your ANTHROPIC_API_KEY, "claude-cli" uses your local
`claude` login, "plain" needs nothing (first sentence, cleaned and trimmed).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

MAX_WORDS = 14

# The inspiration is a 1937 Disney song that is still under copyright: take
# the idea (a crew singing about their work), never the song.
BANNED = ("whistle while you work", "heigh-ho", "heigh ho", "hi-ho", "hi ho",
          "off to work we go", "snow white", "dwarf", "dwarves", "dwarfs", "disney")

PROMPT = """You turn a coding agent's final message into ONE short line the agent will SING to its human, like a crew member singing about the job they just finished.

Rules:
- One sentence, 6 to 14 words, first person, past tense ("I fixed...", "Tests are green...").
- Say what got done or what is needed, in plain words. The most important fact only.
- Singable: no code, no file paths, no symbols. Say "dot py", "two hundred" etc. if needed.
- If the agent is waiting on the human, sing that ("I need your okay to deploy").
- Never include secrets, emails, URLs or people's names. Never quote any existing song.
- Reply with the line only. No quotes, no preamble.

The agent's message:
"""


def _clean(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "", text)
    text = re.sub(r"[*_#>|]+", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(\w)\.(py|ts|tsx|js|md|json|rs|go|sh)\b", r"\1 dot \2", text)
    text = re.sub(r"[/\\]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def plain(message: str) -> str:
    """No-LLM line: the first sentence that fits, else the first sentence cut
    at its last clause break (comma, "so", "and", "because") that fits."""
    text = _clean(message)
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", text) if x.strip()]
    for sent in sentences[:2]:
        if 3 <= len(sent.split()) <= MAX_WORDS:
            return sent.rstrip(".")
    first = sentences[0] if sentences else text
    words = first.split()[:MAX_WORDS]
    breaks = [i for i, w in enumerate(words) if i >= 4 and (w.endswith(",") or w.lower() in ("so", "and", "because", "but", "which"))]
    if breaks:
        k = breaks[-1]
        words = words[: k + 1] if words[k].endswith(",") else words[:k]
    return " ".join(words).rstrip(",;:-. ")


def finish(line: str) -> str:
    line = _clean(line).strip().strip('"').strip("'")
    words = line.split()
    if len(words) > MAX_WORDS + 4:
        line = " ".join(words[:MAX_WORDS])
    low = line.lower()
    for b in BANNED:
        if re.search(rf"\b{re.escape(b)}\b", low):
            line = re.sub(re.escape(b), "", line, flags=re.I).strip()
    return line


def _anthropic(message: str, model: str) -> str:
    import anthropic

    client = anthropic.Anthropic()
    resp = client.beta.messages.create(
        model=model,
        max_tokens=2000,
        output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": PROMPT + message[:6000]}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("summarizer declined")
    return "".join(b.text for b in resp.content if b.type == "text")


def _claude_cli(message: str, model: str) -> str:
    claude = shutil.which("claude")
    if not claude:
        raise RuntimeError("no claude CLI")
    r = subprocess.run(
        [claude, "-p", "--model", model, "--output-format", "json", "--tools", ""],
        input=PROMPT + message[:6000], capture_output=True, text=True, timeout=120,
        # Never let our own summary call trigger agent-choir hooks recursively.
        env={**os.environ, "CHOIR_MUTE": "1"},
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr[:300])
    return json.loads(r.stdout).get("result", "")


def summarize(message: str, how: str = "auto", model: str = "claude-opus-5-5") -> str:
    if how == "auto":
        how = "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "plain"
    try:
        if how == "anthropic":
            return finish(_anthropic(message, model))
        if how == "claude-cli":
            return finish(_claude_cli(message, model))
    except Exception:
        pass  # a missed summary should never cost the agent its turn: fall back
    return finish(plain(message))
