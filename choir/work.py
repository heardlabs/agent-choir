"""Collect what the agents actually did.

Three sources, all producing the same shape (``list[Agent]``):

- Claude Code session transcripts (``~/.claude/projects/*/*.jsonl``): one agent
  per session, facts from the human's ask, files touched and commands run.
- git repos: one agent per repo, facts from commit subjects.
- a hand-written JSON file (``examples/work.json``), for staged takes.

Everything is passed through ``scrub`` before it leaves this machine, because
the lyrics end up in a public tweet.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from choir.cast import MAX_AGENTS

MAX_FACTS = 8
MAX_FACT_CHARS = 160


@dataclass
class Agent:
    id: str
    project: str
    facts: list[str] = field(default_factory=list)
    weight: int = 0  # how much it did; busiest agents get to sing

    def to_dict(self) -> dict:
        return asdict(self)


# --- scrubbing -----------------------------------------------------------

_SECRETS = [
    re.compile(r"\b(sk|pk|rk|ghp|gho|github_pat|xox[bpa]|AKIA)[-_A-Za-z0-9]{12,}\b"),
    re.compile(r"\b[A-Za-z0-9+/_-]{32,}\b"),  # long opaque tokens / hashes
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),  # emails
    re.compile(r"https?://\S+"),
]
_HOME = re.compile(r"(/home|/Users)/[^/\s]+")


def scrub(text: str) -> str:
    text = _HOME.sub("~", text)
    for pat in _SECRETS:
        text = pat.sub("[redacted]", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > MAX_FACT_CHARS:
        text = text[: MAX_FACT_CHARS - 1].rstrip() + "…"
    return text


def _clean(agent: Agent) -> Agent:
    seen, facts = set(), []
    for f in agent.facts:
        f = scrub(f)
        if f and f.lower() not in seen:
            seen.add(f.lower())
            facts.append(f)
    agent.facts = facts[:MAX_FACTS]
    return agent


def top_agents(agents: list[Agent], limit: int = MAX_AGENTS) -> list[Agent]:
    agents = [_clean(a) for a in agents if a.facts]
    agents.sort(key=lambda a: a.weight, reverse=True)
    return agents[:limit]


# --- Claude Code transcripts --------------------------------------------

def parse_since(since: str) -> float:
    """'24h' / '3d' / '90m' -> epoch seconds."""
    m = re.fullmatch(r"(\d+)\s*([mhd])", since.strip())
    if not m:
        raise ValueError(f"bad --since {since!r}; use e.g. 90m, 24h, 3d")
    n, unit = int(m.group(1)), m.group(2)
    return time.time() - n * {"m": 60, "h": 3600, "d": 86400}[unit]


_BORING = {"cd", "ls", "cat", "echo", "sed", "head", "tail", "grep", "rg", "find", "for", "while",
           "until", "if", "do", "then", "export", "set", "source", "true", "test", "sleep", "wc", "printf"}


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def from_claude_session(path: Path) -> Agent | None:
    asks: list[str] = []
    files: Counter[str] = Counter()
    commands: Counter[str] = Counter()
    commits: list[str] = []
    last_reply = ""
    cwd = ""
    tool_uses = 0
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return None
    for line in lines:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        cwd = rec.get("cwd") or cwd
        msg = rec.get("message") or {}
        if rec.get("type") == "user" and (rec.get("origin") or {}).get("kind") == "human":
            t = _text_of(msg.get("content")).strip()
            if t and not t.startswith("<"):
                asks.append(t.splitlines()[0])
        elif rec.get("type") == "assistant":
            for block in msg.get("content") or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and block.get("text", "").strip():
                    last_reply = block["text"].strip()
                if block.get("type") != "tool_use":
                    continue
                tool_uses += 1
                inp = block.get("input") or {}
                name = block.get("name", "")
                if name in ("Edit", "Write", "NotebookEdit") and inp.get("file_path"):
                    files[Path(inp["file_path"]).name] += 1
                elif name == "Bash" and inp.get("command"):
                    cmd = inp["command"]
                    m = re.search(r"git commit[^\n]*?-m\s+[\"']([^\"'\n]+)", cmd)
                    if m and "$" not in m.group(1):
                        commits.append(m.group(1))
                    first = next((t for t in cmd.split() if "=" not in t), "")
                    if re.fullmatch(r"[A-Za-z][\w.-]*", first) and first not in _BORING:
                        commands[first] += 1
    if not asks and not files and not commits:
        return None
    facts: list[str] = []
    facts += [f"asked to: {a}" for a in asks[:2]]
    facts += [f"committed: {c}" for c in commits[:3]]
    if files:
        facts.append("edited " + ", ".join(f for f, _ in files.most_common(4)))
    if commands:
        facts.append("ran " + ", ".join(c for c, _ in commands.most_common(4)))
    if last_reply:
        facts.append("wrapped up with: " + last_reply.splitlines()[0])
    project = Path(cwd).name if cwd else path.parent.name
    return Agent(id=path.stem[:8], project=project, facts=facts, weight=tool_uses + 5 * len(commits))


def from_claude(root: Path, since: float) -> list[Agent]:
    agents = []
    for p in sorted(root.glob("*/*.jsonl")):
        try:
            if p.stat().st_mtime < since:
                continue
        except OSError:
            continue
        a = from_claude_session(p)
        if a:
            agents.append(a)
    return agents


# --- git ----------------------------------------------------------------

def from_git(repo: Path, since: float) -> Agent | None:
    out = subprocess.run(
        ["git", "-C", str(repo), "log", f"--since=@{int(since)}", "--no-merges", "--format=%s"],
        capture_output=True, text=True,
    )
    subjects = [s for s in out.stdout.splitlines() if s.strip()]
    if out.returncode != 0 or not subjects:
        return None
    name = repo.resolve().name
    return Agent(id=name, project=name, facts=[f"committed: {s}" for s in subjects], weight=len(subjects))


# --- json ---------------------------------------------------------------

def from_json(path: Path) -> list[Agent]:
    data = json.loads(path.read_text())
    items = data["agents"] if isinstance(data, dict) else data
    return [
        Agent(id=str(d.get("id") or d["project"]), project=d["project"],
              facts=list(d.get("facts", [])), weight=int(d.get("weight", len(d.get("facts", [])))))
        for d in items
    ]


def save(agents: list[Agent], path: Path) -> None:
    path.write_text(json.dumps({"agents": [a.to_dict() for a in agents]}, indent=2) + "\n")
